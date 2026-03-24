#!/usr/bin/env python3
"""Local task runner: claims tasks, picks provider via Thompson Sampling, executes.

Provider selection is data-driven — SlotSelector("provider_{task_type}") picks
based on measured success rates. No hardcoded routing. New providers get
exploration boost, failures reduce selection probability.

OpenRouter free tier: 26 curated ``:free`` models; SlotSelector(
``openrouter_free_model_{task_type}``) chooses among them; rolling 20 RPM
limiter (``OPENROUTER_FREE_RPM``) before each HTTP call.

Available providers are auto-detected from installed CLIs.

Usage:
  python scripts/local_runner.py                    # run all pending tasks once
  python scripts/local_runner.py --task TASK_ID     # run one specific task
  python scripts/local_runner.py --loop --interval 30  # poll continuously
  python scripts/local_runner.py --dry-run          # show what would run
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Resolve paths
_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent
_REPO_DIR = _API_DIR.parent
_LOG_DIR = _API_DIR / "logs"

# Ensure the app package is importable
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

try:
    from app.services.slot_selection_service import SlotSelector
    from app.services.openrouter_free_tier import (
        OPENROUTER_FREE_MODELS,
        OPENROUTER_HEALTHCHECK_MODEL,
        wait_openrouter_rate_limit,
    )
    HAS_SERVICES = True
except ImportError:
    HAS_SERVICES = False
    OPENROUTER_HEALTHCHECK_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"
    OPENROUTER_FREE_MODELS = (OPENROUTER_HEALTHCHECK_MODEL,)

    def wait_openrouter_rate_limit() -> None:
        return

# Logging
_LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_DIR / "local_runner.log"),
    ],
)
log = logging.getLogger("local_runner")

# Config
try:
    from app.services.config_service import get_hub_url
    API_BASE = os.environ.get("AGENT_API_BASE") or get_hub_url()
except ImportError:
    API_BASE = os.environ.get("AGENT_API_BASE", os.environ.get("COHERENCE_HUB_URL", "https://api.coherencycoin.com"))
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_NODE_NAME = socket.gethostname()
# Persistent node ID — hash of hostname so it survives restarts
_NODE_ID = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16]
_TASK_TIMEOUT = [int(os.environ.get("AGENT_TASK_TIMEOUT", "300"))]
_RESUME_MODE = [False]
_SKIP_PERMISSIONS = [True]  # --dangerously-skip-permissions for claude; operators can disable
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
try:
    from app.services.config_service import get_hub_url as _get_hub
    _OPENROUTER_REFERER = os.environ.get("OPENROUTER_REFERER") or _get_hub().replace("://api.", "://").rstrip("/")
except ImportError:
    _OPENROUTER_REFERER = os.environ.get("OPENROUTER_REFERER", "https://coherencycoin.com")


# ── Provider registry (auto-detected) ───────────────────────────────

def _detect_providers() -> dict[str, dict]:
    """Auto-detect available providers on this machine.

    Every provider is equal — CLI or API, all treated the same by Thompson Sampling.
    CLIs are detected by binary presence; API providers by reachability.
    """
    providers = {}
    cli_specs = {
        # claude --print: non-interactive, prints output
        # --dangerously-skip-permissions: bypass all permission checks
        # --permission-mode bypassPermissions: belt-and-suspenders for auto mode
        # --bare: skip hooks/LSP/plugins that can cause interactive prompts
        "claude": {"cmd": ["claude", "--print", "--bare"], "append_prompt": True, "needs_skip_permissions": True},
        # codex exec --full-auto: non-interactive sandboxed execution
        "codex": {"cmd": ["codex", "exec", "--full-auto"], "append_prompt": True},
        # gemini -y -p <prompt>: yolo mode (auto-approve tools) + headless
        # -y is required: without it, tool calls block on approval (issue #12362)
        "gemini": {"cmd": ["gemini", "-y", "-p"], "append_prompt": True},
        # cursor agent -p: Cursor's headless agent mode
        "cursor": {"cmd": ["agent", "-p", "--force"], "append_prompt": True, "check_binary": "agent"},
        # ollama-local: local LLM via stdin (long prompts need stdin, not args)
        "ollama-local": {
            "cmd": ["ollama", "run"], "stdin_prompt": True,
            "check": _check_ollama_local, "model_select": _select_ollama_model,
        },
        # ollama-cloud: ollama cloud models (glm-5, etc.) via stdin
        "ollama-cloud": {
            "cmd": ["ollama", "run"], "stdin_prompt": True,
            "check": _check_ollama_cloud, "model_select": _select_ollama_cloud_model,
        },
    }
    for name, spec in cli_specs.items():
        binary = spec.pop("check_binary", None) or spec["cmd"][0]
        resolved = shutil.which(binary)
        if not resolved:
            log.debug("Provider not found: %s (%s)", name, binary)
            continue
        # Replace bare command with resolved path (Windows needs .CMD/.EXE path)
        spec["cmd"][0] = resolved
        # Add --dangerously-skip-permissions for providers that need it (e.g. claude)
        if spec.pop("needs_skip_permissions", False) and _SKIP_PERMISSIONS[0]:
            spec["cmd"].insert(1, "--dangerously-skip-permissions")
        # Optional health check
        checker = spec.pop("check", None)
        if checker and not checker():
            log.info("Provider skipped (not ready): %s", name)
            continue
        # Optional model selection (e.g., ollama picks best available model)
        model_selector = spec.pop("model_select", None)
        if model_selector:
            model = model_selector()
            if not model:
                log.info("Provider skipped (no model): %s", name)
                continue
            spec["cmd"].append(model)
            log.info("Provider detected: %s model=%s", name, model)
        else:
            log.info("Provider detected: %s (%s)", name, resolved)
        providers[name] = spec

    # API-based providers (no CLI binary needed)
    # OpenRouter free-tier provider (no API key required for :free models)
    if _check_openrouter():
        providers["openrouter"] = {
            "api": True,
            "models": list(OPENROUTER_FREE_MODELS),
            "tool_capable": False,
        }
        log.info(
            "Provider detected: openrouter (API free tier, %d models, Thompson Sampling per task_type)",
            len(OPENROUTER_FREE_MODELS),
        )

    return providers


def _check_ollama_local() -> bool:
    """Check if ollama server is running with local models."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        # At least one non-cloud model
        lines = result.stdout.strip().split("\n")[1:]  # skip header
        return any("cloud" not in line.split()[0] if line.strip() else False for line in lines)
    except Exception:
        return False


def _check_ollama_cloud() -> bool:
    """Check if ollama has cloud models available."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        return any("cloud" in line.split()[0] if line.strip() else False for line in result.stdout.split("\n"))
    except Exception:
        return False


def _select_ollama_model() -> str | None:
    """Select the best available local ollama model."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")[1:]  # skip header
        local_models = []
        for line in lines:
            name = line.split()[0] if line.strip() else ""
            if name and "cloud" not in name:
                local_models.append(name)
        # Prefer larger/newer models
        preferred = ["llama3.3:70b", "qwen2.5:72b", "deepseek-r1:32b", "dolphin-mixtral:8x22b-v2.9-q6_K"]
        for pref in preferred:
            if pref in local_models:
                return pref
        return local_models[0] if local_models else None
    except Exception:
        return None


def _select_ollama_cloud_model() -> str | None:
    """Select the best available ollama cloud model."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split("\n"):
            parts = line.split()
            if parts and "cloud" in parts[0]:
                return parts[0]
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cursor model selection — data-driven via SlotSelector
# ---------------------------------------------------------------------------

# Tiers: map complexity → Cursor model selection
# Use Cursor's own tier system: 'auto' (default), 'premium' (best available)
# Keep gpt models for codex, claude models for claude, and let Cursor
# handle its own model routing internally via auto/premium.
_CURSOR_MODEL_TIERS = {
    "simple": [
        "auto",                     # let Cursor pick — cheapest path
    ],
    "medium": [
        "auto",                     # let Cursor pick — balanced
    ],
    "complex": [
        "premium",                  # Cursor's best model tier
        "auto",                     # fallback if premium unavailable
    ],
}


def _select_cursor_model(task_type: str, complexity: str = "medium") -> str:
    """Select cursor model via SlotSelector — data determines which model wins.

    Each complexity tier has candidate models. SlotSelector("cursor_model_{tier}")
    picks based on measured success rates. New models get exploration boost.
    """
    tier = complexity if complexity in _CURSOR_MODEL_TIERS else "medium"
    candidates = _CURSOR_MODEL_TIERS[tier]

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app.services.slot_selection_service import SlotSelector
        selector = SlotSelector(f"cursor_model_{tier}")
        selected = selector.select(candidates)
        if selected:
            return selected
    except Exception:
        log.warning("SlotSelector failed for model selection", exc_info=True)

    # Fallback: first candidate in tier
    return candidates[0]


def _select_openrouter_model(task_type: str) -> str:
    """Pick a free OpenRouter model via SlotSelector — per task_type Thompson Sampling."""
    candidates = list(OPENROUTER_FREE_MODELS)
    if not candidates:
        return OPENROUTER_HEALTHCHECK_MODEL
    try:
        if HAS_SERVICES:
            selector = SlotSelector(f"openrouter_free_model_{task_type}")
            selected = selector.select(candidates)
            if selected:
                return selected
    except Exception:
        log.warning("SlotSelector failed for OpenRouter model selection", exc_info=True)
    return candidates[0]


def _check_openrouter() -> bool:
    """Check if OpenRouter free-tier API is reachable with a simple prompt."""
    try:
        content = _openrouter_chat_completion(
            "Reply with: ok",
            timeout_s=10.0,
            model=OPENROUTER_HEALTHCHECK_MODEL,
        )
        return bool(content)
    except Exception as e:
        log.debug("OpenRouter check failed: %s", e)
        return False


def _parse_openrouter_message_content(payload: dict[str, Any]) -> str:
    """Parse OpenRouter `choices[0].message.content` into plain text."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter response missing choices")
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    if not isinstance(message, dict):
        raise ValueError("OpenRouter response missing message")

    content = message.get("content")
    if isinstance(content, str):
        parsed = content.strip()
        if parsed:
            return parsed
        raise ValueError("OpenRouter response content is empty")

    # Some providers may return segmented content blocks.
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        if parts:
            return "\n".join(parts)

    raise ValueError("OpenRouter response content is missing or unsupported")


def _openrouter_chat_completion(
    prompt: str,
    timeout_s: float,
    *,
    model: str | None = None,
) -> str:
    """Call OpenRouter chat completions and return text content."""
    resolved_model = model or (OPENROUTER_FREE_MODELS[0] if OPENROUTER_FREE_MODELS else OPENROUTER_HEALTHCHECK_MODEL)
    wait_openrouter_rate_limit()
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": _OPENROUTER_REFERER,
    }
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    # Fall back to keystore (~/.coherence-network/keys.json)
    if not api_key:
        ks_path = os.path.join(os.path.expanduser("~"), ".coherence-network", "keys.json")
        if os.path.exists(ks_path):
            try:
                with open(ks_path) as _kf:
                    _ks = json.load(_kf)
                api_key = _ks.get("openrouter", {}).get("api_key", "")
            except Exception:
                pass
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = httpx.post(
        _OPENROUTER_URL,
        headers=headers,
        json=body,
        timeout=timeout_s,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter HTTP {response.status_code}: {response.text[:200]}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OpenRouter response is not a JSON object")
    return _parse_openrouter_message_content(payload)


def _run_openrouter(prompt: str, cwd: str, timeout: int, model: str) -> tuple[bool, str, float]:
    """Execute via OpenRouter API (free tier). Returns (success, output, duration)."""
    start = time.time()
    try:
        content = _openrouter_chat_completion(prompt, timeout_s=float(timeout), model=model)
        duration = time.time() - start
        return True, content, duration
    except Exception as e:
        duration = time.time() - start
        return False, f"OpenRouter error: {e}", duration


# Providers with tool/file access (can actually create/modify files)
_TOOL_PROVIDERS = {"claude", "codex", "gemini", "cursor"}
# Providers that are text-only (no file access — good for review, bad for impl/spec/test)
_TEXT_ONLY_PROVIDERS = {"ollama-local", "ollama-cloud", "openrouter"}

PROVIDERS: dict[str, dict] = {}  # populated at startup


def _provider_has_tools(provider: str) -> bool:
    """Does this provider have tool/file access?"""
    spec = PROVIDERS.get(provider) or {}
    if "tool_capable" in spec:
        return bool(spec.get("tool_capable"))
    return provider in _TOOL_PROVIDERS



# Provider tiers: which providers are strong enough for each task type
# spec + review need the strongest models (claude, codex, cursor)
# impl + test can use any tool-capable provider
# openrouter/free and ollama-local are only suitable for simple/draft tasks
_STRONG_PROVIDERS = {"claude", "codex", "cursor"}
_TOOL_PROVIDERS = {"claude", "codex", "cursor", "gemini"}  # can produce files


def select_provider(task_type: str) -> str:
    """Select provider via Thompson Sampling based on task outcome data.

    Spec and review tasks require strong providers (claude, codex, cursor).
    File-producing tasks (impl, test) require tool-capable providers.
    openrouter/free and ollama are only used when strong providers are unavailable.
    """
    available = list(PROVIDERS.keys())
    if not available:
        raise RuntimeError("No providers available")

    # Spec and review need strong models — not openrouter/free or ollama
    if task_type in ("spec", "review"):
        strong = [p for p in available if p in _STRONG_PROVIDERS]
        if strong:
            available = strong
            log.info("PROVIDER_TIER task=%s restricted to strong: %s", task_type, available)
        else:
            log.warning("No strong providers for %s task — falling back to all", task_type)

    # File-producing tasks need tool-capable providers
    elif task_type in ("impl", "test"):
        tool_available = [p for p in available if p in _TOOL_PROVIDERS or _provider_has_tools(p)]
        if tool_available:
            available = tool_available
            log.info("PROVIDER_FILTER task=%s restricted to tool-capable: %s", task_type, available)
        else:
            log.warning("No tool-capable providers available for %s task, using all", task_type)

    if len(available) == 1:
        return available[0]

    if HAS_SERVICES:
        try:
            selector = SlotSelector(f"provider_{task_type}")
            selected = selector.select(available)
            if selected:
                log.info("PROVIDER_SELECT task_type=%s selected=%s from=%s (Thompson Sampling)",
                         task_type, selected, available)
                return selected
        except Exception:
            log.warning("Thompson Sampling failed for provider selection, using fallback", exc_info=True)

    # Fallback: simple rotation based on time
    import hashlib
    h = int(hashlib.md5(f"{time.time()}".encode()).hexdigest(), 16)
    selected = available[h % len(available)]
    log.info("PROVIDER_SELECT task_type=%s selected=%s (fallback)", task_type, selected)
    return selected


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all its children. Required on Windows where .CMD wrappers
    spawn child processes that survive normal termination."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def classify_error(output: str) -> str:
    """Classify failure reason from output for root-cause analysis.

    Blind timeouts (zero output) are the highest priority — they cost
    everything and return nothing, not even diagnostic information.
    """
    lower = output.lower()
    if "blind timeout" in lower:
        return "blind_timeout"  # worst case: cost with zero value, zero diagnostics
    if "timeout" in lower:
        if "partial stdout" in lower or "partial stderr" in lower:
            return "timeout_with_output"  # at least we have something to diagnose
        return "timeout"
    if "unexpected argument" in lower or "unrecognized" in lower:
        return "cli_args"
    if "not found" in lower or "no such file" in lower:
        return "not_found"
    if "auth" in lower or "unauthorized" in lower or "forbidden" in lower:
        return "auth"
    if "rate limit" in lower or "429" in lower or "quota" in lower:
        return "rate_limit"
    if "connection" in lower or "network" in lower or "dns" in lower:
        return "network"
    if output.strip() == "" or output == "(no output)":
        return "empty_output"
    return "unknown"


def record_provider_outcome(
    task_type: str, provider: str, success: bool, duration: float, output: str = "",
):
    """Record provider outcome with error classification for root-cause analysis."""
    if not HAS_SERVICES:
        return

    error_class = None if success else classify_error(output)
    try:
        selector = SlotSelector(f"provider_{task_type}")
        selector.record(
            slot_id=provider,
            value_score=1.0 if success else 0.0,
            resource_cost=max(duration, 0.1),
            error_class=error_class,
            duration_s=duration,
        )
        log.info("RECORDED task_type=%s provider=%s success=%s duration=%.1fs error_class=%s",
                 task_type, provider, success, duration, error_class)

        # Record cursor model outcome for per-model learning
        if provider == "cursor":
            spec = PROVIDERS.get("cursor", {})
            model = spec.get("_selected_model")
            tier = spec.get("_model_tier", "medium")
            if model:
                model_selector = SlotSelector(f"cursor_model_{tier}")
                model_selector.record(
                    slot_id=model,
                    value_score=1.0 if success else 0.0,
                    resource_cost=max(duration, 0.1),
                    error_class=error_class,
                    duration_s=duration,
                )
                log.info("CURSOR_MODEL_RECORDED tier=%s model=%s success=%s duration=%.1fs",
                         tier, model, success, duration)

        # OpenRouter: free model per task_type (Thompson Sampling over OPENROUTER_FREE_MODELS)
        if provider == "openrouter":
            spec = PROVIDERS.get("openrouter", {})
            model = spec.get("_selected_model")
            if model:
                or_selector = SlotSelector(f"openrouter_free_model_{task_type}")
                or_selector.record(
                    slot_id=model,
                    value_score=1.0 if success else 0.0,
                    resource_cost=max(duration, 0.1),
                    error_class=error_class,
                    duration_s=duration,
                    raw_signals={"openrouter_model": model},
                )
                log.info(
                    "OPENROUTER_MODEL_RECORDED task_type=%s model=%s success=%s duration=%.1fs",
                    task_type,
                    model,
                    success,
                    duration,
                )
    except Exception:
        log.warning("Failed to record provider outcome", exc_info=True)


def get_provider_stats() -> dict:
    """Get current provider selection stats for all task types."""
    if not HAS_SERVICES:
        return {}
    try:
        available = list(PROVIDERS.keys())
        stats = {}
        for task_type in ["spec", "test", "impl", "review", "heal"]:
            selector = SlotSelector(f"provider_{task_type}")
            stats[task_type] = selector.stats(available)
        return stats
    except Exception:
        return {}


def get_openrouter_free_model_stats() -> dict:
    """Thompson Sampling stats for each task_type × free model (local runner telemetry).

    Proof path: JSON files under ``api/logs/slot_measurements/openrouter_free_model_<task_type>.json``.
    """
    if not HAS_SERVICES:
        return {}
    try:
        models = list(OPENROUTER_FREE_MODELS)
        out: dict[str, Any] = {}
        for task_type in ["spec", "test", "impl", "review", "heal"]:
            selector = SlotSelector(f"openrouter_free_model_{task_type}")
            out[task_type] = selector.stats(models)
        return out
    except Exception:
        return {}


# ── API calls ────────────────────────────────────────────────────────

_HTTP_CLIENT = httpx.Client(timeout=30.0)

_PHASE_SEQUENCE = ("spec", "impl", "test", "review")
_NEXT_PHASE: dict[str, str | None] = {
    "spec": "impl",
    "impl": "test",
    "test": "review",
    "review": None,
}

def api(method: str, path: str, body: dict | None = None, _retries: int = 0) -> dict | list | None:
    """Call the API via httpx. Auto-retries on 429 with backoff."""
    url = f"{API_BASE}{path}"
    headers = {"X-Api-Key": os.environ.get("AGENT_API_KEY", "dev-key")}
    try:
        if method == "GET":
            resp = _HTTP_CLIENT.get(url, headers=headers)
        elif method == "POST":
            resp = _HTTP_CLIENT.post(url, json=body, headers=headers)
        elif method == "PATCH":
            resp = _HTTP_CLIENT.patch(url, json=body, headers=headers)
        elif method == "PUT":
            resp = _HTTP_CLIENT.put(url, json=body, headers=headers)
        elif method == "DELETE":
            resp = _HTTP_CLIENT.delete(url, headers=headers)
        else:
            log.error("Unsupported API method: %s", method)
            return None

        # Retryable errors — back off and retry (up to 3 times)
        if resp.status_code in (429, 502, 503, 504) and _retries < 3:
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "5"))
                label = "RATE_LIMITED"
            else:
                wait = 3 * (_retries + 1)  # 3s, 6s, 9s exponential
                label = "TRANSIENT"
            log.warning("%s %s %s → %d — retrying in %ds (%d/3)",
                        label, method, path, resp.status_code, wait, _retries + 1)
            time.sleep(wait)
            return api(method, path, body, _retries + 1)

        if resp.status_code >= 400:
            # Log level by severity:
            # - 409: INFO (expected race condition)
            # - 404: WARNING (resource missing, not actionable by client)
            # - 500-599: WARNING (server issue, client can't fix, retry handled above)
            # - Other 4xx: ERROR (client bug — needs fixing)
            if resp.status_code == 409:
                log.info("API %s %s → 409 (already claimed, expected race)", method, path)
            elif resp.status_code == 404:
                log.warning("API %s %s → 404 (resource not found)", method, path)
            elif resp.status_code >= 500:
                log.warning("API %s %s → %d (server error, not retryable after %d attempts): %s",
                            method, path, resp.status_code, _retries, resp.text[:100])
            else:
                log.error("API %s %s → %d: %s", method, path, resp.status_code, resp.text[:200])
            return None

        if not resp.text.strip():
            return None

        return resp.json()
    except httpx.HTTPError as e:
        log.warning("API %s %s network error (transient): %s", method, path, e)
        return None
    except json.JSONDecodeError:
        log.warning("API %s %s → bad JSON response: %s", method, path, resp.text[:200])
        return None
    except Exception as e:
        log.error("API %s %s unexpected error: %s", method, path, e)
        return None


def _post_activity(task_id: str, event_type: str, data: dict):
    """Post activity event — log failures, never block execution."""
    try:
        resp = httpx.post(
            f"{API_BASE}/api/agent/tasks/{task_id}/activity",
            json={
                "node_id": _NODE_ID,
                "node_name": _NODE_NAME,
                "provider": data.get("provider", ""),
                "event_type": event_type,
                "data": data,
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            log.warning("ACTIVITY_FAIL task=%s event=%s status=%d body=%s",
                        task_id, event_type, resp.status_code, resp.text[:200])
    except Exception as exc:
        log.warning("ACTIVITY_ERROR task=%s event=%s error=%s", task_id, event_type, exc)


def list_pending() -> list[dict]:
    result = api("GET", "/api/agent/tasks?status=pending&limit=10")
    if result is None:
        return []
    if isinstance(result, dict):
        return result.get("tasks", [])
    return result


def claim_task(task_id: str) -> dict | None:
    result = api("PATCH", f"/api/agent/tasks/{task_id}", {
        "status": "running", "claimed_by": WORKER_ID,
    })
    if result and result.get("status") == "running":
        log.info("CLAIMED task=%s type=%s", task_id, result.get("task_type"))
        return result
    return None


def complete_task(task_id: str, output: str, success: bool, context_patch: dict | None = None) -> bool:
    status = "completed" if success else "failed"
    body: dict[str, Any] = {"status": status, "output": output[:50000]}
    if context_patch:
        body["context"] = context_patch
    if not success:
        body["error_summary"] = output[:500]
        body["error_category"] = "execution_error"
    result = api("PATCH", f"/api/agent/tasks/{task_id}", body)
    if result:
        log.info("REPORTED task=%s status=%s", task_id, status)
        return True
    log.error("REPORT FAILED task=%s", task_id)
    return False


def _complete_task_with_status(
    task_id: str,
    output: str,
    status: str,
    context_patch: dict | None = None,
    error_category: str = "execution_error",
) -> bool:
    body: dict[str, Any] = {"status": status, "output": output[:50000]}
    if context_patch:
        body["context"] = context_patch
    if status != "completed":
        body["error_summary"] = output[:500]
        body["error_category"] = error_category
    result = api("PATCH", f"/api/agent/tasks/{task_id}", body)
    if result:
        log.info("REPORTED task=%s status=%s", task_id, status)
        return True
    log.error("REPORT FAILED task=%s status=%s", task_id, status)
    return False


def _auto_record_contribution(task: dict[str, Any], provider: str, duration: float) -> None:
    """Auto-record a contribution when a task completes successfully.

    Maps task_type to contribution_type:
      spec → docs, test → code, impl → code, review → review, heal → code
    CC amount is based on task complexity and duration.
    """
    try:
        task_type = task.get("task_type", "unknown")
        idea_id = _idea_id_from_task(task)

        type_map = {"spec": "docs", "test": "code", "impl": "code", "review": "review", "heal": "code"}
        contribution_type = type_map.get(task_type, "other")

        # CC amount: base by type + duration bonus
        base_cc = {"spec": 3, "test": 5, "impl": 8, "review": 2, "heal": 3}.get(task_type, 2)
        duration_bonus = min(duration / 60, 5)  # up to 5 CC for long tasks
        amount_cc = round(base_cc + duration_bonus, 1)

        body = {
            "contributor_id": _NODE_ID,
            "type": contribution_type,
            "amount_cc": amount_cc,
            "metadata": {
                "description": f"Task {task.get('id', '?')[:20]} ({task_type}) completed by {provider} on {_NODE_NAME}",
                "task_id": task.get("id", ""),
                "task_type": task_type,
                "provider": provider,
                "duration_s": round(duration, 1),
                "auto_recorded": True,
            },
        }
        if idea_id:
            body["idea_id"] = idea_id

        result = api("POST", "/api/contributions/record", body)
        if result:
            log.info("AUTO_CONTRIBUTION recorded %.1f CC (%s) for task %s idea=%s",
                     amount_cc, contribution_type, task.get("id", "?")[:16], idea_id or "none")
        else:
            log.warning("AUTO_CONTRIBUTION failed for task %s", task.get("id", "?")[:16])
    except Exception as e:
        log.warning("AUTO_CONTRIBUTION error: %s", e)


def _idea_id_from_task(task: dict[str, Any]) -> str:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    for key in ("idea_id", "origin_idea_id", "primary_idea_id", "tracking_idea_id"):
        value = str(context.get(key) or "").strip()
        if value:
            return value
    for key in ("idea_ids", "tracked_idea_ids", "related_idea_ids"):
        values = context.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            value = str(item or "").strip()
            if value:
                return value
    return ""


def _task_group_for_phase(idea_tasks_payload: dict[str, Any], phase: str) -> dict[str, Any] | None:
    groups = idea_tasks_payload.get("groups")
    if not isinstance(groups, list):
        return None
    for group in groups:
        if not isinstance(group, dict):
            continue
        task_type = str(group.get("task_type") or "").strip().lower()
        if task_type == phase:
            return group
    return None


def _run_verification_probes(api_paths: list[str], api_base: str) -> list[dict]:
    """Run deep verification probes against claimed API endpoints.

    For each endpoint, checks:
    1. Exists (non-404)
    2. Returns valid JSON (not HTML error page)
    3. Response has meaningful content (not empty object/array with no useful fields)
    4. Schema sanity (response has expected top-level structure)
    5. Error handling (append /nonexistent-id, expect 404 not 500)

    Returns list of probe results: {path, checks: [{name, passed, detail}]}
    """
    results = []
    for path in api_paths[:5]:
        probes = []
        url = f"{api_base}{path}"

        # Probe 1: Exists
        try:
            resp = httpx.get(url, timeout=8)
            probes.append({
                "name": "exists",
                "passed": resp.status_code < 400,
                "detail": f"HTTP {resp.status_code}",
            })

            if resp.status_code >= 400:
                results.append({"path": path, "checks": probes})
                continue

            # Probe 2: Valid JSON
            try:
                body = resp.json()
                probes.append({"name": "valid_json", "passed": True, "detail": type(body).__name__})
            except Exception:
                probes.append({"name": "valid_json", "passed": False, "detail": "not JSON"})
                results.append({"path": path, "checks": probes})
                continue

            # Probe 3: Meaningful content
            if isinstance(body, dict):
                has_content = any(
                    v is not None and v != "" and v != [] and v != {}
                    for v in body.values()
                )
                probes.append({
                    "name": "has_content",
                    "passed": has_content,
                    "detail": f"{len(body)} fields, content={'yes' if has_content else 'empty'}",
                })
            elif isinstance(body, list):
                probes.append({
                    "name": "has_content",
                    "passed": True,  # list endpoints can be empty legitimately
                    "detail": f"{len(body)} items",
                })
            else:
                probes.append({"name": "has_content", "passed": True, "detail": str(type(body))})

            # Probe 4: Error handling — try a bogus sub-path
            try:
                err_resp = httpx.get(f"{url}/____nonexistent_test_id____", timeout=5)
                got_clean_error = err_resp.status_code in (404, 422)
                got_500 = err_resp.status_code >= 500
                probes.append({
                    "name": "error_handling",
                    "passed": got_clean_error and not got_500,
                    "detail": f"bogus ID → HTTP {err_resp.status_code}",
                })
            except Exception:
                probes.append({"name": "error_handling", "passed": True, "detail": "skipped"})

        except Exception as e:
            probes.append({"name": "exists", "passed": False, "detail": f"network error: {e}"})

        results.append({"path": path, "checks": probes})

    return results


def _classify_idea_validation(interfaces: list[str], desc: str) -> str:
    """Determine validation category from interfaces and description.

    Returns: 'network-api', 'network-web', 'network-cli', 'infrastructure',
             'external', 'research', 'community'
    """
    iface_set = set(interfaces or [])

    # Network ideas: have machine:api, human:web, machine:cli, machine:mcp
    has_api = any(i in iface_set for i in ("machine:api", "api"))
    has_web = any(i in iface_set for i in ("human:web", "web"))
    has_cli = any(i in iface_set for i in ("machine:cli", "cli"))
    has_ci = any(i in iface_set for i in ("machine:ci", "ci"))

    if has_api or has_web or has_cli:
        return "network"
    if has_ci:
        return "infrastructure"
    if any(i.startswith("external:") for i in iface_set):
        return "external"

    # No interfaces claimed — check description for clues
    desc_lower = desc.lower()
    if "/api/" in desc_lower or "endpoint" in desc_lower:
        return "network"
    if "web page" in desc_lower or "ui " in desc_lower or "page " in desc_lower:
        return "network"

    # Default: no specific production check needed
    return "general"


def _verify_production_interfaces(idea_id: str, idea_payload: dict) -> list[str]:
    """Check if an idea's claimed interfaces actually exist on production.

    Returns a list of failure descriptions. Empty list = all verified.

    Validation is category-aware:
    - network: check API endpoints (non-404) and web pages (non-404)
    - infrastructure: check CI workflow exists or health endpoint
    - external: no production check (contributor provides evidence)
    - general: no production check (spec completeness is sufficient)
    """
    import re
    desc = str(idea_payload.get("description") or "")
    interfaces = idea_payload.get("interfaces") or []

    category = _classify_idea_validation(interfaces, desc)

    if category not in ("network",):
        # Non-network ideas: no production endpoint check
        log.info("PRODUCTION_CHECK idea=%s category=%s — skipped (not network)", idea_id, category)
        return []

    failures = []

    # Extract API paths from description (e.g., /api/concepts, /api/edges)
    api_paths = re.findall(r'/api/[\w/{}]+', desc)
    api_paths = list(set(p.split("{")[0].rstrip("/") for p in api_paths))

    API_BASE = os.environ.get("PUBLIC_DEPLOY_API_BASE", "https://api.coherencycoin.com")

    if api_paths:
        # Deep verification: not just 404 check, but schema, content, error handling
        probe_results = _run_verification_probes(api_paths, API_BASE)
        for result in probe_results:
            path = result["path"]
            for check in result["checks"]:
                if not check["passed"]:
                    failures.append(f"API {path} [{check['name']}]: {check['detail']}")

    # Check web pages if human:web is in interfaces
    if any(i in set(interfaces) for i in ("human:web", "web")):
        web_paths = re.findall(r'Web:.*?/([\w-]+)\s', desc)
        WEB_BASE = os.environ.get("PUBLIC_DEPLOY_WEB_BASE", "https://coherencycoin.com")
        for page in web_paths[:3]:
            try:
                resp = httpx.get(f"{WEB_BASE}/{page}", timeout=5, follow_redirects=True)
                if resp.status_code == 404:
                    failures.append(f"Web /{page} → 404")
                elif resp.status_code >= 500:
                    failures.append(f"Web /{page} → {resp.status_code} (server error)")
            except Exception:
                pass

    if failures:
        log.warning("PROOF_CHECK idea=%s category=%s FAILED (%d issues): %s",
                     idea_id, category, len(failures), failures[:3])
    elif api_paths:
        log.info("PROOF_CHECK idea=%s category=%s PASSED (%d endpoints, all probes green)",
                  idea_id, category, len(api_paths))
    else:
        log.info("PROOF_CHECK idea=%s category=%s — no endpoints claimed, skipped",
                  idea_id, category)

    return failures


def _phase_fully_completed(idea_tasks_payload: dict[str, Any], phase: str) -> bool:
    group = _task_group_for_phase(idea_tasks_payload, phase)
    if not group:
        return False
    status_counts = group.get("status_counts")
    if not isinstance(status_counts, dict):
        status_counts = {}
    pending = int(status_counts.get("pending", 0) or 0)
    running = int(status_counts.get("running", 0) or 0)
    failed = int(status_counts.get("failed", 0) or 0)
    needs_decision = int(status_counts.get("needs_decision", 0) or 0)
    completed = int(status_counts.get("completed", 0) or 0)
    return completed > 0 and pending == 0 and running == 0 and failed == 0 and needs_decision == 0


def _has_any_tasks_for_phase(idea_tasks_payload: dict[str, Any], phase: str) -> bool:
    group = _task_group_for_phase(idea_tasks_payload, phase)
    if not group:
        return False
    return int(group.get("count", 0) or 0) > 0


def _run_phase_auto_advance_hook(task: dict[str, Any]) -> None:
    task_type = str(task.get("task_type") or "").strip().lower()
    if task_type not in _PHASE_SEQUENCE:
        return

    idea_id = _idea_id_from_task(task)
    if not idea_id:
        return

    idea_tasks_payload = api("GET", f"/api/ideas/{idea_id}/tasks")
    if not isinstance(idea_tasks_payload, dict):
        return
    if not _phase_fully_completed(idea_tasks_payload, task_type):
        return

    next_phase = _NEXT_PHASE.get(task_type)
    if next_phase and not _has_any_tasks_for_phase(idea_tasks_payload, next_phase):
        idea_payload = api("GET", f"/api/ideas/{idea_id}")
        idea_name = str((idea_payload or {}).get("name") or idea_id) if isinstance(idea_payload, dict) else idea_id
        idea_desc = str((idea_payload or {}).get("description") or "") if isinstance(idea_payload, dict) else ""

        # Phase-specific direction with quality requirements
        if next_phase == "review":
            direction = (
                f"Review and verify '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:500]}\n\n"
                f"REVIEW INSTRUCTIONS:\n"
                f"You are the final gate before this idea is marked as DONE.\n"
                f"Think of yourself as the person who decides whether to PAY for this work.\n\n"
                f"1. Find the spec for this idea (check specs/ directory or task history)\n"
                f"2. Find the 'Verification Scenarios' section in the spec\n"
                f"3. RUN each verification scenario against PRODUCTION:\n"
                f"   - API: curl https://api.coherencycoin.com/...\n"
                f"   - Web: check https://coherencycoin.com/...\n"
                f"   - CLI: run cc <command>\n"
                f"4. For EACH scenario, report:\n"
                f"   - PASS: the exact output matched expectations\n"
                f"   - FAIL: what was expected vs what actually happened\n\n"
                f"If the spec has no verification scenarios, output REVIEW_FAILED:\n"
                f"  'Spec missing verification scenarios — cannot verify without test criteria'\n\n"
                f"If ANY verification scenario fails, output REVIEW_FAILED with:\n"
                f"  - Which scenario failed\n"
                f"  - Expected output\n"
                f"  - Actual output\n"
                f"  - Suggested fix\n\n"
                f"If ALL scenarios pass, output REVIEW_PASSED with:\n"
                f"  - Each scenario and its actual output as evidence\n"
                f"  - Confirmation that the feature works on production\n\n"
                f"Do NOT pass a review based on code reading alone.\n"
                f"Do NOT pass a review if you cannot run the verification scenarios.\n"
                f"Do NOT pass a review if endpoints return 404 or 500."
            )
        elif next_phase == "test":
            direction = (
                f"Write tests for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Write actual test code (pytest) that verifies the feature works.\n"
                f"Tests must be runnable. Include both unit tests and an integration test\n"
                f"that hits the API endpoint if applicable.\n"
                f"Follow the project's CLAUDE.md conventions."
            )
        elif next_phase == "impl":
            direction = (
                f"Implement '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Write the actual code that makes this feature work.\n"
                f"Follow the project's CLAUDE.md conventions. Work in the repository.\n"
                f"The implementation must be complete enough to deploy and use."
            )
        else:
            direction = (
                f"Execute the '{next_phase}' phase for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Follow the project's CLAUDE.md conventions. Work in the repository."
            )
        created = api(
            "POST",
            "/api/agent/tasks",
            {
                "direction": direction,
                "task_type": next_phase,
                "context": {
                    "idea_id": idea_id,
                    "auto_phase_advanced_from": task_type,
                    "auto_phase_advance_source": "local_runner_post_task_hook",
                },
            },
        )
        if not isinstance(created, dict):
            log.warning(
                "AUTO_PHASE enqueue failed idea_id=%s from=%s to=%s",
                idea_id,
                task_type,
                next_phase,
            )

    # Determine manifestation status with validation gate
    if next_phase is None:
        # All phases should be complete — verify before marking validated
        # ALSO verify that completed tasks had meaningful output (not empty)
        required_phases = {"spec", "test", "impl", "review"}
        idea_tasks_check = api("GET", f"/api/ideas/{idea_id}/tasks")
        completed_phases = set()
        empty_phases = set()
        if isinstance(idea_tasks_check, dict):
            for g in (idea_tasks_check.get("groups") or []):
                if not isinstance(g, dict):
                    continue
                phase = g.get("task_type", "")
                sc = g.get("status_counts", {})
                if int(sc.get("completed", 0)) > 0:
                    completed_phases.add(phase)
                    # Check if the completed tasks actually had output
                    for t in (g.get("tasks") or []):
                        if t.get("status") == "completed":
                            t_output = (t.get("output") or "").strip()
                            if len(t_output) < 50:
                                empty_phases.add(phase)

        log.info("VALIDATION_GATE idea=%s completed_phases=%s empty_phases=%s",
                 idea_id, sorted(completed_phases), sorted(empty_phases))
        missing = required_phases - completed_phases
        if missing:
            log.warning(
                "VALIDATION_GATE idea=%s blocked: missing phases %s (completed: %s)",
                idea_id, sorted(missing), sorted(completed_phases),
            )
            manifestation_status = "partial"
        elif empty_phases:
            log.warning(
                "VALIDATION_GATE idea=%s blocked: phases with empty output %s — "
                "these need re-execution with meaningful results",
                idea_id, sorted(empty_phases),
            )
            manifestation_status = "partial"
        else:
            # Production verification: check if claimed interfaces actually exist
            prod_failures = _verify_production_interfaces(idea_id, idea_payload if isinstance(idea_payload, dict) else {})
            if prod_failures:
                log.warning(
                    "VALIDATION_GATE idea=%s blocked: production verification failed — %s",
                    idea_id, prod_failures,
                )
                manifestation_status = "partial"
            else:
                log.info(
                    "VALIDATION_GATE idea=%s VALIDATED: all phases complete, output verified, production checked %s",
                    idea_id, sorted(completed_phases),
                )
                manifestation_status = "validated"
    else:
        manifestation_status = "partial"

    updated = api(
        "PATCH",
        f"/api/ideas/{idea_id}",
        {"manifestation_status": manifestation_status},
    )
    if not isinstance(updated, dict):
        log.warning("AUTO_PHASE manifestation update failed idea_id=%s status=%s", idea_id, manifestation_status)


# ── Execution ────────────────────────────────────────────────────────

def build_prompt(task: dict) -> str:
    direction = task.get("direction", "")
    task_type = task.get("task_type", "unknown")
    context = task.get("context", {}) or {}
    agent = context.get("task_agent", "dev-engineer")

    prompt = f"""You are acting as a {agent} for the Coherence Network project.

Task type: {task_type}
Task ID: {task.get('id', 'unknown')}

Direction:
{direction}

Work in the repository at {_REPO_DIR}. Follow the project's CLAUDE.md conventions.

Output a summary: files created/modified, validation results, errors encountered."""
    # Resume from checkpoint — either from explicit resume mode or from reaper retry
    if isinstance(context, dict):
        resume_patch_path = str(context.get("resume_patch_path") or "").strip()
        checkpoint_summary = str(context.get("checkpoint_summary") or "").strip()
        retried_from = str(context.get("retried_from") or "").strip()
        failed_provider = str(context.get("failed_provider") or "").strip()

        if resume_patch_path:
            prompt += (
                "\n\nResume context:\n"
                f"- A partial patch from a timed-out run is available at `{resume_patch_path}`.\n"
                "- Apply this patch first with `git apply --reject \"<patch_path>\"` "
                "or `git apply \"<patch_path>\"`, then continue from that state."
            )
        if checkpoint_summary:
            prompt += (
                "\n\nCheckpoint from previous attempt:\n"
                f"{checkpoint_summary}\n"
                "Continue from this point. Do not redo work already completed."
            )
        if retried_from and not resume_patch_path and not checkpoint_summary:
            prompt += (
                f"\n\nThis is a retry of a previous task that timed out (provider: {failed_provider})."
                " The previous attempt may have made partial progress — check git status for any"
                " uncommitted changes before starting fresh."
            )

    # Instruct agent to write checkpoint files periodically
    prompt += (
        "\n\nIMPORTANT: Every 5-7 minutes of work, write a brief checkpoint to"
        " `.task-checkpoint.md` in the repo root with: (1) what you completed so far,"
        " (2) what remains, (3) any blockers. This allows work to be resumed if interrupted."
    )
    return prompt


def _git_status_lines() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(_REPO_DIR),
        )
    except Exception:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _status_line_path(line: str) -> str:
    if len(line) < 4:
        return ""
    path_part = line[3:]
    if " -> " in path_part:
        path_part = path_part.split(" -> ", 1)[1]
    return path_part.strip().strip('"')


def _status_paths(lines: list[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        path = _status_line_path(line)
        if path:
            paths.add(path)
    return paths


def _git_diff_for_paths(paths: set[str] | None = None) -> str:
    tracked_cmd = ["git", "diff", "--binary"]
    if paths:
        tracked_cmd.extend(["--", *sorted(paths)])
    try:
        tracked_result = subprocess.run(
            tracked_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(_REPO_DIR),
        )
        tracked_diff = tracked_result.stdout
    except Exception:
        tracked_diff = ""

    if not paths:
        return tracked_diff

    untracked_patches: list[str] = []
    for rel_path in sorted(paths):
        try:
            listed = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", rel_path],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(_REPO_DIR),
            )
            if not listed.stdout.strip():
                continue
            abs_path = _REPO_DIR / rel_path
            untracked = subprocess.run(
                ["git", "diff", "--binary", "--no-index", "--", "/dev/null", str(abs_path)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(_REPO_DIR),
            )
            if untracked.stdout.strip():
                untracked_patches.append(untracked.stdout)
        except Exception:
            continue
    if untracked_patches:
        return tracked_diff + "".join(untracked_patches)
    return tracked_diff


def _create_resume_task(task: dict[str, Any], patch_rel_path: str, timeout_output: str) -> str | None:
    task_id = str(task.get("id") or "").strip()
    task_type = str(task.get("task_type") or "impl").strip() or "impl"
    original_direction = str(task.get("direction") or "").strip()
    base_context = task.get("context") if isinstance(task.get("context"), dict) else {}
    resume_context = dict(base_context or {})
    resume_context.update(
        {
            "resume_from_task_id": task_id,
            "resume_patch_path": patch_rel_path,
            "resume_reason": "timed_out",
            "resume_source": "local_runner_timeout_resume",
            "timed_out_output": timeout_output[:4000],
        }
    )
    resume_direction = (
        f"Resume timed-out task {task_id}.\n"
        f"Apply patch at `{patch_rel_path}` and continue from where it left off.\n\n"
        f"Original direction:\n{original_direction}"
    )
    created = api(
        "POST",
        "/api/agent/tasks",
        {
            "direction": resume_direction,
            "task_type": task_type,
            "context": resume_context,
        },
    )
    if isinstance(created, dict):
        resume_id = str(created.get("id") or "").strip()
        if resume_id:
            return resume_id
    return None


def estimate_task_complexity(task: dict[str, Any]) -> dict[str, Any]:
    """Estimate task complexity from direction length, task type, and file mentions."""
    direction = str(task.get("direction") or "")
    task_type = str(task.get("task_type") or "unknown").strip().lower()
    normalized = " ".join(direction.split())
    direction_length = len(normalized)

    # Path-like references (supports backticked and plain paths).
    file_like_matches = re.findall(
        r"(?:`([^`]+)`|([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+))",
        direction,
    )
    file_mentions: set[str] = set()
    for quoted, plain in file_like_matches:
        candidate = (quoted or plain).strip()
        if "/" in candidate:
            file_mentions.add(candidate)
    file_mention_count = len(file_mentions)

    task_type_weight = {
        "review": 0,
        "spec": 1,
        "test": 1,
        "heal": 1,
        "impl": 2,
    }.get(task_type, 1)

    length_weight = 0
    if direction_length >= 600:
        length_weight = 2
    elif direction_length >= 220:
        length_weight = 1

    files_weight = 0
    if file_mention_count >= 5:
        files_weight = 2
    elif file_mention_count >= 2:
        files_weight = 1

    score = task_type_weight + length_weight + files_weight
    complexity = "complex" if score >= 4 else "simple"
    multiplier = 4.0 if complexity == "complex" else 2.0
    return {
        "level": complexity,
        "score": score,
        "timeout_multiplier": multiplier,
        "direction_length": direction_length,
        "task_type": task_type,
        "file_mentions": file_mention_count,
    }


def get_timeout_for(provider: str, task_type: str, complexity_estimate: dict[str, Any] | None = None) -> int:
    """Get data-driven timeout for a provider+task_type combination.

    Uses a complexity-adjusted multiplier over p90 duration:
    - simple tasks: 2x p90
    - complex tasks: 4x p90
    Falls back to the configured default if no p90 data exists.
    """
    multiplier = 2.0
    if isinstance(complexity_estimate, dict):
        raw_level = str(complexity_estimate.get("level") or "").strip().lower()
        if raw_level == "complex":
            multiplier = 4.0
        elif raw_level == "simple":
            multiplier = 2.0

    if HAS_SERVICES:
        try:
            selector = SlotSelector(f"provider_{task_type}")
            stats = selector.stats([provider])
            slot = stats.get("slots", {}).get(provider, {})
            p90_duration = float(slot.get("p90_duration_s", 0) or 0)
            if p90_duration > 5:  # Ignore suspiciously low p90 (likely from broken runs)
                timeout = int(max(120, min(600, p90_duration * multiplier)))
                log.info(
                    "TIMEOUT_DATA provider=%s task=%s complexity=%s timeout=%ds (%.1fx p90=%.0fs)",
                    provider,
                    task_type,
                    (complexity_estimate or {}).get("level", "simple"),
                    timeout,
                    multiplier,
                    p90_duration,
                )
                return timeout
        except Exception:
            pass
    return _TASK_TIMEOUT[0]


def execute_with_provider(
    provider: str,
    prompt: str,
    task_type: str = "unknown",
    complexity_estimate: dict[str, Any] | None = None,
) -> tuple[bool, str, float]:
    """Run prompt through a provider (CLI or API). Returns (success, output, duration)."""
    spec = PROVIDERS[provider]
    timeout = get_timeout_for(provider, task_type, complexity_estimate)

    # API-based providers (openrouter)
    if spec.get("api"):
        model = _select_openrouter_model(task_type)
        spec["_selected_model"] = model
        log.info("OPENROUTER_MODEL task=%s model=%s", task_type, model)
        return _run_openrouter(prompt, str(_REPO_DIR), timeout, model)

    cmd = list(spec["cmd"])
    stdin_input = None

    # Per-task model selection for cursor
    if provider == "cursor" and complexity_estimate:
        complexity = complexity_estimate.get("level", "medium")
        model = _select_cursor_model(task_type, complexity)
        agent_bin = shutil.which("agent") or "agent"
        cmd = [agent_bin, "--model", model, "-p"]
        log.info("CURSOR_MODEL task=%s complexity=%s model=%s", task_type, complexity, model)

        # Record model selection for SlotSelector learning
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from app.services.slot_selection_service import SlotSelector
            # Store selected model in spec for post-task recording
            spec["_selected_model"] = model
            spec["_model_tier"] = complexity
        except Exception:
            pass

    if spec.get("stdin_prompt"):
        # ollama-style: prompt via stdin
        stdin_input = prompt
    elif spec.get("append_prompt"):
        cmd.append(prompt)

    start = time.time()

    # On Windows, .CMD scripts spawn child processes that survive subprocess.run timeout.
    # Use Popen with CREATE_NEW_PROCESS_GROUP so we can kill the entire tree.
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdin_input else None,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(_REPO_DIR), creationflags=creation_flags,
        )
        try:
            stdout, stderr = proc.communicate(
                input=stdin_input, timeout=timeout,
            )
            duration = time.time() - start
            output = stdout or stderr or "(no output)"
            return proc.returncode == 0, output, duration
        except subprocess.TimeoutExpired:
            # Kill entire process tree on timeout
            log.warning("TIMEOUT provider=%s after %ds — killing process tree (pid=%d)",
                        provider, timeout, proc.pid)
            _kill_process_tree(proc.pid)

            # Try to collect partial output — but with a HARD deadline.
            # communicate() can hang forever if child processes keep pipe handles open
            # even after taskkill /F /T, so we use a watchdog thread.
            partial_stdout = ""
            partial_stderr = ""
            try:
                stdout, stderr = proc.communicate(timeout=10)
                partial_stdout = stdout or ""
                partial_stderr = stderr or ""
            except subprocess.TimeoutExpired:
                # communicate() itself timed out — pipes still held by orphan children.
                # Force-close our end and move on.
                log.warning("PIPE_HANG provider=%s — communicate() blocked 10s after kill, "
                            "force-closing pipes", provider)
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.stderr.close()
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
                # Second kill attempt — catch any stragglers
                _kill_process_tree(proc.pid)

            duration = time.time() - start
            diagnostic = f"TIMEOUT after {duration:.0f}s (limit={timeout}s)\n"
            if partial_stdout:
                diagnostic += f"--- partial stdout ({len(partial_stdout)} chars) ---\n{partial_stdout[-2000:]}\n"
            if partial_stderr:
                diagnostic += f"--- partial stderr ({len(partial_stderr)} chars) ---\n{partial_stderr[-2000:]}\n"
            if not partial_stdout and not partial_stderr:
                diagnostic += (
                    "BLIND TIMEOUT: no output captured. Priority gap — cannot root-cause.\n"
                    f"Provider: {provider}\n"
                    f"Cmd: {' '.join(str(c)[:50] for c in cmd)}\n"
                )
                log.error("BLIND_TIMEOUT provider=%s cmd=%s — needs investigation", provider, cmd[0])
            return False, diagnostic, duration

    except Exception as e:
        duration = time.time() - start
        return False, f"Error: {type(e).__name__}: {e}", duration


def run_one(task: dict, dry_run: bool = False) -> bool:
    """Full lifecycle: claim → select provider → execute → record → report."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")

    # Claim
    if not dry_run:
        claimed = claim_task(task_id)
        if not claimed:
            log.warning("SKIP task=%s (claim failed)", task_id)
            return False
        task = claimed
        _post_activity(task_id, "claimed", {"task_type": task_type})

    complexity_estimate = estimate_task_complexity(task)

    if not dry_run:
        updated = api(
            "PATCH",
            f"/api/agent/tasks/{task_id}",
            {"context": {"complexity_estimate": complexity_estimate}},
        )
        if isinstance(updated, dict):
            task = updated

    # Select provider (data-driven)
    provider = select_provider(task_type)

    if dry_run:
        log.info(
            "DRY RUN task=%s type=%s provider=%s complexity=%s files=%d length=%d",
            task_id,
            task_type,
            provider,
            complexity_estimate["level"],
            complexity_estimate["file_mentions"],
            complexity_estimate["direction_length"],
        )
        return True

    # Execute
    prompt = build_prompt(task)

    # Snapshot repo state before execution (to detect actual file changes)
    pre_status_lines = _git_status_lines()
    pre_patch = _git_diff_for_paths()

    log.info("EXECUTING task=%s type=%s provider=%s", task_id, task_type, provider)
    _post_activity(task_id, "executing", {"provider": provider, "task_type": task_type})

    success, output, duration = execute_with_provider(provider, prompt, task_type, complexity_estimate)

    # Post-execution validation: did file-producing tasks actually produce files?
    if success and task_type in ("spec", "impl", "test"):
        try:
            post_result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True,
                timeout=5, cwd=str(_REPO_DIR),
            )
            post_diff = post_result.stdout.strip()
            new_changes = set(post_diff.splitlines()) - set(pre_status_lines)
            has_tool_access = _provider_has_tools(provider)

            if not new_changes and not has_tool_access:
                # Provider without tools claimed success but produced no files
                success = False
                output = (
                    f"FALSE POSITIVE: {provider} has no tool/file access but reported "
                    f"success for {task_type} task. No file changes detected.\n"
                    f"Output was text-only (hallucinated implementation).\n---\n{output}"
                )
                log.warning(
                    "FALSE_POSITIVE task=%s provider=%s type=%s — no tools, no file changes",
                    task_id, provider, task_type,
                )
            elif new_changes:
                log.info("VERIFIED task=%s files_changed=%d", task_id, len(new_changes))
        except Exception as exc:
            log.warning("VALIDATION_ERROR task=%s error=%s", task_id, exc)

    # Save task log
    task_log = _LOG_DIR / f"task_{task_id}.log"
    task_log.write_text(
        f"=== Task {task_id} | Provider: {provider} | Type: {task_type} ===\n"
        f"Time: {datetime.now(timezone.utc).isoformat()}\n"
        f"Duration: {duration:.1f}s | Success: {success}\n"
        f"=== OUTPUT ===\n{output}\n"
    )

    # Record outcome for Thompson Sampling (with error classification)
    record_provider_outcome(task_type, provider, success, duration, output)

    # ── Quality gate: empty or trivially short output is NOT success ──
    _MIN_OUTPUT_CHARS = 50  # minimum chars for a meaningful response
    output_stripped = (output or "").strip()
    if success and len(output_stripped) < _MIN_OUTPUT_CHARS:
        log.warning(
            "QUALITY_GATE task=%s provider=%s — output too short (%d chars < %d min). "
            "Marking as failed, not completed.",
            task_id, provider, len(output_stripped), _MIN_OUTPUT_CHARS,
        )
        success = False

    completion_status = "completed" if success else "failed"
    completion_error_category = "execution_error"
    completion_context: dict[str, Any] = {
        "worker_id": WORKER_ID,
        "provider": provider,
        "duration_s": round(duration, 1),
        "complexity_estimate": complexity_estimate,
    }
    if provider == "openrouter":
        om = (PROVIDERS.get("openrouter") or {}).get("_selected_model")
        if om:
            completion_context["openrouter_model"] = om
            completion_context["openrouter_free_model_slots"] = len(OPENROUTER_FREE_MODELS)

    if not success:
        error_class = classify_error(output)
        completion_context["failure_reason_bucket"] = error_class
        completion_context["failure_summary"] = output[:500] if output else "No output captured"
        completion_context["failure_provider"] = provider
        if error_class in {"timeout", "timeout_with_output", "blind_timeout"}:
            completion_status = "timed_out"
            completion_error_category = "timeout"

            post_status_lines = _git_status_lines()
            post_patch = _git_diff_for_paths()
            new_status_lines = set(post_status_lines) - set(pre_status_lines)
            changed_paths = _status_paths(list(new_status_lines))

            if pre_patch != post_patch:
                if not changed_paths:
                    changed_paths = _status_paths(post_status_lines)
                patch_body = _git_diff_for_paths(changed_paths) if changed_paths else post_patch
                if patch_body and patch_body.strip():
                    partial_patch_path = _LOG_DIR / f"partial_task_{task_id}.patch"
                    partial_patch_path.write_text(patch_body)
                    try:
                        patch_rel_path = str(partial_patch_path.relative_to(_REPO_DIR))
                    except ValueError:
                        patch_rel_path = str(partial_patch_path)
                    completion_context["partial_patch_path"] = patch_rel_path
                    log.info("TIMEOUT partial patch saved task=%s path=%s", task_id, patch_rel_path)
                    if _RESUME_MODE[0]:
                        resume_task_id = _create_resume_task(task, patch_rel_path, output)
                        if resume_task_id:
                            completion_context["resume_task_id"] = resume_task_id
                            log.info("TIMEOUT resume task created source=%s resume=%s", task_id, resume_task_id)
                        else:
                            log.warning("TIMEOUT resume task create failed source=%s", task_id)

    # Report to API
    if completion_status == "completed":
        reported = complete_task(task_id, output, success, completion_context)
    else:
        reported = _complete_task_with_status(
            task_id,
            output,
            completion_status,
            completion_context,
            error_category=completion_error_category,
        )
    if success and reported:
        # Only advance phases if the task produced meaningful output
        if len(output_stripped) >= _MIN_OUTPUT_CHARS:
            _run_phase_auto_advance_hook(task)
            _auto_record_contribution(task, provider, duration)
        else:
            log.warning("SKIP_ADVANCE task=%s — output too short for phase advancement", task_id)

    # Post completion activity
    _post_activity(
        task_id,
        "completed" if success else ("timeout" if completion_status == "timed_out" else "failed"),
        {"provider": provider, "task_type": task_type, "duration_s": round(duration, 1), "output_preview": output[:200] if output else ""},
    )

    log.info("OUTCOME task=%s type=%s provider=%s success=%s duration=%.1fs",
             task_id, task_type, provider, success, duration)
    return success


_MAX_PENDING_TASKS = 5  # Capacity cap for seed generation
_SEED_TASK_TYPES = ("spec", "test", "impl", "review")


def _count_active_tasks() -> int:
    """Count pending + running tasks (capacity check for seed generation)."""
    pending = list_pending()
    running = api("GET", "/api/agent/tasks?status=running&limit=100")
    r_count = 0
    if isinstance(running, list):
        r_count = len(running)
    elif isinstance(running, dict):
        r_count = len(running.get("tasks", []))
    return len(pending) + r_count


_STALE_TASK_THRESHOLD_SECONDS = _TASK_TIMEOUT[0] * 2  # 2x timeout = definitely stuck


def _reap_stale_tasks() -> int:
    """Find and time-out tasks stuck in 'running' beyond the stale threshold.

    When a node crashes mid-task, the task stays 'running' forever.
    This reaper runs each cycle and cleans up orphaned tasks so they
    don't block capacity. Returns the number of tasks reaped.
    """
    running = api("GET", "/api/agent/tasks?status=running&limit=50")
    if not running:
        return 0
    tasks = running if isinstance(running, list) else running.get("tasks", [])
    if not tasks:
        return 0

    reaped = 0
    threshold = max(_STALE_TASK_THRESHOLD_SECONDS, 600)  # At least 10 minutes

    for task in tasks:
        created = task.get("created_at", "")
        if not created:
            continue
        try:
            from datetime import datetime as _dt, timezone as _tz
            dt = _dt.fromisoformat(created.replace("Z", "+00:00"))
            age_seconds = (_dt.now(_tz.utc) - dt).total_seconds()
        except Exception:
            continue

        if age_seconds < threshold:
            continue

        task_id = task.get("id", "")
        age_min = int(age_seconds / 60)
        log.warning("REAPER: task %s stuck running for %dm (threshold=%ds) — marking timed_out",
                     task_id[:20], age_min, threshold)

        result = api("PATCH", f"/api/agent/tasks/{task_id}", {
            "status": "timed_out",
            "output": f"Reaped by stale task reaper: running for {age_min}m with no heartbeat",
            "error_summary": f"Node went offline — task stuck running for {age_min} minutes",
            "error_category": "stale_task_reaped",
        })
        if result:
            reaped += 1
            log.info("REAPER: reaped %s → timed_out", task_id[:20])

    if reaped:
        log.info("REAPER: cleaned up %d stale tasks", reaped)
    return reaped


def _seed_task_from_open_idea() -> bool:
    """Generate a task from an open idea when the queue is empty.

    Smart seeding:
    1. Skip ideas that already have pending/running tasks
    2. Skip validated ideas
    3. Weighted random selection (not always highest FE) for diversity
    4. Check existing task history to determine correct next phase
    5. Always link idea_id for phase advancement
    """
    import random as _random

    # Capacity check
    active = _count_active_tasks()
    if active >= _MAX_PENDING_TASKS:
        log.info("SEED: at capacity (%d/%d) — skipping", active, _MAX_PENDING_TASKS)
        return False

    # Get open ideas
    all_ideas = api("GET", "/api/ideas?limit=200")
    if not all_ideas:
        return False
    ideas = all_ideas.get("ideas", all_ideas) if isinstance(all_ideas, dict) else all_ideas

    # Get active task idea_ids to avoid duplicates
    active_idea_ids: set[str] = set()
    for status_q in ("pending", "running"):
        tasks_data = api("GET", f"/api/agent/tasks?status={status_q}&limit=100")
        if tasks_data:
            task_list = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
            for t in task_list:
                ctx = t.get("context") if isinstance(t.get("context"), dict) else {}
                tid = str(ctx.get("idea_id") or "").strip()
                if tid:
                    active_idea_ids.add(tid)

    # Filter: open ideas without active tasks
    candidates = [
        i for i in ideas
        if i.get("manifestation_status") in ("none", "partial", None)
        and i.get("id", "") not in active_idea_ids
    ]
    if not candidates:
        log.info("SEED: no eligible ideas (all validated or already have active tasks)")
        return False

    # Weighted random selection from top 10 by free-energy (diversity)
    candidates.sort(key=lambda i: float(i.get("free_energy_score", 0) or 0), reverse=True)
    top = candidates[:10]
    weights = [max(float(i.get("free_energy_score", 0) or 0), 0.1) for i in top]
    idea = _random.choices(top, weights=weights, k=1)[0]
    idea_id = idea.get("id", "unknown")
    idea_name = idea.get("name", idea_id)

    # Check existing task history for this idea to determine next phase
    task_type = "spec"  # default
    idea_tasks = api("GET", f"/api/ideas/{idea_id}/tasks")
    if isinstance(idea_tasks, dict):
        total_tasks = idea_tasks.get("total", 0)
        groups = idea_tasks.get("groups", [])
        completed_phases: set[str] = set()
        phase_counts: dict[str, int] = {}
        for g in groups if isinstance(groups, list) else []:
            if not isinstance(g, dict):
                continue
            phase = g.get("task_type", "")
            status_counts = g.get("status_counts", {})
            completed = int(status_counts.get("completed", 0))
            total_for_phase = int(status_counts.get("pending", 0)) + int(status_counts.get("running", 0)) + completed + int(status_counts.get("failed", 0))
            phase_counts[phase] = total_for_phase
            if completed > 0:
                completed_phases.add(phase)

        # Cap: if any single phase has 3+ tasks, this idea is over-served — skip it
        max_phase_tasks = max(phase_counts.values()) if phase_counts else 0
        if max_phase_tasks >= 3:
            log.info("SEED: idea '%s' over-served (%d tasks in one phase) — marking validated",
                     idea_name[:30], max_phase_tasks)
            api("PATCH", f"/api/ideas/{idea_id}", {"manifestation_status": "validated"})
            return _seed_task_from_open_idea()  # retry with next idea

        if "review" in completed_phases:
            log.info("SEED: idea '%s' has completed review — marking validated", idea_name[:30])
            api("PATCH", f"/api/ideas/{idea_id}", {"manifestation_status": "validated"})
            return _seed_task_from_open_idea()  # retry with next idea
        elif "impl" in completed_phases:
            task_type = "review"
        elif "test" in completed_phases:
            task_type = "impl"
        elif "spec" in completed_phases:
            task_type = "test"

    # Build direction
    desc = idea.get("description", "")
    questions = idea.get("open_questions", [])
    q_text = ""
    if questions:
        q_lines = [f"- {(q.get('question', q) if isinstance(q, dict) else str(q))}" for q in questions[:3]]
        q_text = "\n\nOpen questions to address:\n" + "\n".join(q_lines)

    # Determine validation category for the spec
    ifaces = idea.get("interfaces") or []
    has_api = any(i in ifaces for i in ("machine:api", "api"))
    has_web = any(i in ifaces for i in ("human:web", "web"))
    has_cli = any(i in ifaces for i in ("machine:cli", "cli"))

    validation_guidance = (
        f"\n\nVERIFICATION CONTRACT:\n"
        f"Think of this spec as a contract. Someone will pay real money for the work.\n"
        f"The spec must include a 'Verification Scenarios' section with 3-5 specific,\n"
        f"concrete test scenarios that PROVE the feature works as described.\n\n"
        f"Each scenario must have:\n"
        f"- Setup: what state exists before the test\n"
        f"- Action: exact command or request (curl, cc command, browser action)\n"
        f"- Expected result: specific output, not vague ('returns data')\n"
        f"- Edge case: what happens with bad input, missing data, or duplicate request\n\n"
        f"Example of a GOOD verification scenario:\n"
        f"  Setup: No concepts exist yet\n"
        f"  Action: curl -s $API/api/concepts -X POST -d '{{\"id\":\"test\",\"name\":\"Test\"}}'\n"
        f"  Expected: HTTP 201, response contains {{\"id\":\"test\",\"name\":\"Test\"}}\n"
        f"  Then: curl -s $API/api/concepts/test returns the same concept\n"
        f"  Then: curl -s $API/api/concepts returns list containing 'test'\n"
        f"  Edge: POST same concept again returns 409 (conflict, not duplicate)\n"
        f"  Edge: GET /api/concepts/nonexistent returns 404 (not 500)\n\n"
        f"Example of a BAD verification scenario:\n"
        f"  'Test that the API works' — too vague, no specific input/output\n"
        f"  'Check the endpoint returns 200' — proves nothing about the feature\n\n"
        f"The reviewer will RUN these scenarios against production.\n"
        f"If any scenario fails, the work is not done.\n"
        f"If the scenarios are too vague to run, the spec is rejected.\n"
    )
    if has_api or has_web or has_cli or "/api/" in desc.lower():
        validation_guidance += (
            f"\nNETWORK-SPECIFIC:\n"
            f"- Include the exact API endpoints that must exist (e.g., GET /api/concepts)\n"
            f"- Include the exact web pages (e.g., /concepts) if web-facing\n"
            f"- Include the exact CLI commands (e.g., cc concepts) if CLI-facing\n"
            f"- At least one scenario must test the full create-read-update cycle\n"
            f"- At least one scenario must test error handling (bad input, missing resource)\n"
        )
    else:
        validation_guidance += (
            f"\nEXTERNAL/GENERAL:\n"
            f"- Include what evidence proves this idea is realized\n"
            f"- Evidence can be: URL to live feature, screenshot, contributor attestation\n"
            f"- The evidence must be independently verifiable by any party\n"
        )

    direction = (
        f"Write a {task_type} for: {idea_name}.\n\n{desc}{q_text}\n\n"
        f"REQUIREMENTS:\n"
        f"- Your output MUST be substantial (not empty or trivially short)\n"
        f"- For spec: write a detailed specification with goal, files, acceptance criteria\n"
        f"- For impl: write actual code that implements the feature\n"
        f"- For test: write runnable pytest tests\n"
        f"- For review: verify the feature exists, works, and is deployed\n"
        f"- Follow the project's CLAUDE.md conventions. Work in the repository.\n"
        f"- If you cannot complete the task, explain WHY in detail (don't return empty)."
        f"{validation_guidance}"
    )

    result = api("POST", "/api/agent/tasks", {
        "direction": direction,
        "task_type": task_type,
        "context": {
            "idea_id": idea_id,
            "idea_name": idea_name,
            "seed_generated": True,
            "seed_source": "local_runner_smart_seed",
        },
        "target_state": f"{task_type.title()} completed for: {idea_name}",
        "success_evidence": f"{task_type} artifact exists and meets quality criteria",
        "abort_evidence": f"Cannot make progress — blocked or unclear requirements",
    })

    if isinstance(result, dict) and result.get("id"):
        log.info("SEED: created %s task %s for idea '%s' (FE=%.2f, candidates=%d)",
                 task_type, result["id"][:16], idea_name[:40],
                 float(idea.get("free_energy_score", 0) or 0), len(candidates))
        return True

    log.warning("SEED: failed to create task for idea '%s'", idea_name)
    return False


def run_all_pending(dry_run: bool = False) -> dict:
    tasks = list_pending()
    if not tasks:
        log.info("No pending tasks")
        # Seed a new task from an open idea when the queue is empty
        if not dry_run:
            _seed_task_from_open_idea()
            # Re-check after seeding
            tasks = list_pending()
            if not tasks:
                return {"total": 0, "success": 0, "failed": 0}
            log.info("Seeded task — now have %d pending", len(tasks))
        else:
            return {"total": 0, "success": 0, "failed": 0}

    log.info("Found %d pending tasks", len(tasks))
    results = {"total": len(tasks), "success": 0, "failed": 0}

    for task in tasks:
        if run_one(task, dry_run=dry_run):
            results["success"] += 1
        else:
            results["failed"] += 1

    log.info("BATCH DONE: %s", results)

    # Show provider stats after batch
    stats = get_provider_stats()
    if stats:
        log.info("PROVIDER STATS: %s", json.dumps(stats, indent=2, default=str))

    # Surface blind spots — these are the highest priority issues
    all_blind_spots = []
    for task_type, st in stats.items():
        for bs in st.get("blind_spots", []):
            bs["task_type"] = task_type
            all_blind_spots.append(bs)

    if all_blind_spots:
        log.warning("=" * 60)
        log.warning("BLIND SPOTS — priority issues (cost with zero diagnostic value):")
        for bs in all_blind_spots:
            log.warning(
                "  [%s] %s/%s: %d blind failures out of %d total — %s",
                bs["priority"], bs["task_type"], bs["slot"],
                bs["blind_failures"], bs["total_failures"], bs["action"],
            )
        log.warning("=" * 60)

    return results


def _get_git_sha() -> tuple[str, str]:
    """Return (local_sha, origin_sha) or ('unknown', 'unknown')."""
    try:
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip() or "unknown"
    except Exception:
        local = "unknown"
    try:
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"], capture_output=True, text=True, timeout=5
        ).stdout.strip() or "unknown"
    except Exception:
        remote = "unknown"
    return local, remote


def _register_node() -> None:
    """Register this worker node with the federation API on startup."""
    providers = list(_detect_providers().keys())
    tools = []
    for tool in ["python", "python3", "node", "npm", "docker", "git", "pip", "cargo", "go"]:
        if shutil.which(tool):
            tools.append(tool)

    local_sha, origin_sha = _get_git_sha()

    payload = {
        "node_id": _NODE_ID,
        "hostname": _NODE_NAME,
        "os_type": "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux",
        "providers": providers,
        "capabilities": {
            "executors": providers,
            "tools": tools,
            "hardware": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python": platform.python_version(),
            },
            "git": {
                "local_sha": local_sha,
                "origin_sha": origin_sha,
                "in_sync": local_sha == origin_sha,
            },
        },
    }
    result = api("POST", "/api/federation/nodes", payload)
    if result:
        log.info("NODE_REGISTERED id=%s hostname=%s sha=%s providers=%s", _NODE_ID, _NODE_NAME, local_sha[:8], providers)
    else:
        log.warning("NODE_REGISTER_FAILED id=%s — will retry on next heartbeat", _NODE_ID)


def _send_heartbeat() -> None:
    """Update node liveness so other nodes and the UI can see we're active."""
    local_sha, origin_sha = _get_git_sha()
    result = api("PATCH", f"/api/federation/nodes/{_NODE_ID}", {
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "status": "online",
        "local_sha": local_sha,
        "origin_sha": origin_sha,
    })
    if result:
        log.debug("HEARTBEAT sent for node %s sha=%s", _NODE_ID, local_sha[:8])
    else:
        # PATCH might not exist — re-register (which includes SHA)
        _register_node()


def _poll_messages() -> None:
    """Check for inter-node messages and handle commands."""
    result = api("GET", f"/api/federation/nodes/{_NODE_ID}/messages?unread_only=true&limit=20")
    if not isinstance(result, dict):
        return
    messages = result.get("messages", [])
    if not messages:
        return

    for msg in messages:
        msg_type = msg.get("type", "text")
        from_node = msg.get("from_node", "?")[:16]
        text = msg.get("text", "")
        payload = msg.get("payload", {})

        if msg_type == "text":
            log.info("MSG from %s: %s", from_node, text[:200])

        elif msg_type == "command":
            cmd = payload.get("command", text)
            log.info("CMD from %s: %s", from_node, cmd)
            if cmd == "status":
                api("POST", f"/api/federation/nodes/{_NODE_ID}/messages", {
                    "from_node": _NODE_ID,
                    "to_node": from_node,
                    "type": "status_response",
                    "payload": {
                        "node_id": _NODE_ID,
                        "hostname": _NODE_NAME,
                        "os": platform.system(),
                        "providers": list(PROVIDERS.keys()) if PROVIDERS else [],
                    },
                    "text": f"Status from {_NODE_NAME}: online with {len(PROVIDERS or {})} providers",
                })
            elif cmd == "pull":
                log.info("CMD: remote pull request — will update on next cycle")
            else:
                log.info("CMD: unknown command '%s'", cmd)

        elif msg_type == "status_response":
            log.info("STATUS from %s: %s", from_node, text[:200])

        else:
            log.info("MSG [%s] from %s: %s", msg_type, from_node, text[:100])


def _check_for_updates_and_restart() -> bool:
    """Check if origin/main has new commits; if so, pull and re-exec.

    Returns True if the process is about to be replaced (caller should exit).
    Returns False if no update was needed.
    """
    try:
        # Fetch latest from origin (quiet, no merge)
        fetch = subprocess.run(
            ["git", "fetch", "origin", "main", "--quiet"],
            capture_output=True, text=True, timeout=15,
            cwd=str(_REPO_DIR),
        )
        if fetch.returncode != 0:
            log.debug("SELF-UPDATE: git fetch failed: %s", fetch.stderr.strip())
            return False

        # Compare local HEAD with origin/main
        local_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_REPO_DIR),
        ).stdout.strip()

        remote_sha = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_REPO_DIR),
        ).stdout.strip()

        if local_sha == remote_sha:
            return False

        log.info("SELF-UPDATE: new commits detected (local=%s remote=%s)", local_sha[:8], remote_sha[:8])

        # Check for uncommitted changes that would block pull
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_REPO_DIR),
        )
        if status.stdout.strip():
            log.warning("SELF-UPDATE: uncommitted changes — stashing before pull")
            subprocess.run(
                ["git", "stash", "--include-untracked"],
                capture_output=True, text=True, timeout=10,
                cwd=str(_REPO_DIR),
            )

        # Pull latest
        pull = subprocess.run(
            ["git", "pull", "origin", "main", "--ff-only"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_REPO_DIR),
        )
        if pull.returncode != 0:
            log.warning("SELF-UPDATE: git pull failed: %s", pull.stderr.strip())
            return False

        log.info("SELF-UPDATE: pulled latest → %s. Re-executing runner...", remote_sha[:8])

        # Re-exec this script with the same arguments
        os.execv(sys.executable, [sys.executable] + sys.argv)
        # This line is never reached — os.execv replaces the process
        return True

    except Exception as e:
        log.debug("SELF-UPDATE: check failed: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Task runner — data-driven provider selection")
    parser.add_argument("--task", help="Run a specific task ID")
    parser.add_argument("--loop", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--timeout", type=int, default=_TASK_TIMEOUT[0], help="Task timeout (seconds)")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Enable timed-out task resume flow (save patch + enqueue resume task)",
    )
    parser.add_argument("--stats", action="store_true", help="Show provider stats and exit")
    parser.add_argument(
        "--no-skip-permissions",
        action="store_true",
        help="Do not pass --dangerously-skip-permissions to claude (requires manual approval)",
    )
    parser.add_argument(
        "--no-self-update",
        action="store_true",
        help="Disable automatic git pull + re-exec on new commits",
    )
    args = parser.parse_args()

    _TASK_TIMEOUT[0] = args.timeout
    _RESUME_MODE[0] = bool(args.resume)
    _SKIP_PERMISSIONS[0] = not args.no_skip_permissions

    # Detect providers
    global PROVIDERS
    PROVIDERS = _detect_providers()
    if not PROVIDERS:
        log.error("No provider CLIs found. Install claude, codex, cursor, or gemini.")
        sys.exit(1)

    log.info("Runner starting: api=%s worker=%s timeout=%ds providers=%s self_update=%s",
             API_BASE, WORKER_ID, _TASK_TIMEOUT[0], list(PROVIDERS.keys()),
             "off" if args.no_self_update else "on")

    if args.stats:
        stats = get_provider_stats()
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.task:
        task = api("GET", f"/api/agent/tasks/{args.task}")
        if not task:
            log.error("Task %s not found", args.task)
            sys.exit(1)
        ok = run_one(task, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    if args.loop:
        log.info("Polling every %ds (Ctrl+C to stop)", args.interval)
        _register_node()
        _heartbeat_counter = [0]
        try:
            while True:
                # Self-update: check for new commits before each cycle
                if not args.no_self_update:
                    _check_for_updates_and_restart()
                _poll_messages()
                run_all_pending(dry_run=args.dry_run)
                # Heartbeat every 4 cycles (~60s at 15s interval)
                _heartbeat_counter[0] += 1
                if _heartbeat_counter[0] % 4 == 0:
                    _send_heartbeat()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Stopped")
    else:
        # Single run: check for updates first
        if not args.no_self_update:
            _check_for_updates_and_restart()
        results = run_all_pending(dry_run=args.dry_run)
        sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
