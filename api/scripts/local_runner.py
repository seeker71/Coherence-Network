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
import tarfile
import tempfile
import threading
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

# ── Runner config — single source of truth, no env vars ──────────────
_RUNNER_CONFIG: dict[str, Any] = {}


def _load_runner_config() -> dict[str, Any]:
    """Load runner config from api/config/runner.json.

    Falls back to defaults if file missing. Env vars are NOT read —
    all configuration comes from this file.
    """
    global _RUNNER_CONFIG
    config_path = _API_DIR / "config" / "runner.json"
    defaults = {
        "api": {"base_url": "https://api.coherencycoin.com", "api_key": "dev-key"},
        "execution": {"parallel": 2, "timeout_default_s": 300, "work_dir": None},
        "providers": {"paused": ["openrouter"], "openrouter_api_key": None, "openrouter_referer": "https://coherencycoin.com"},
        "heartbeat": {"url": None, "cmd": None},
        "diagnostics": {"level": "normal"},
        "deploy": {"api_base": "https://api.coherencycoin.com", "web_base": "https://coherencycoin.com"},
        "self_update": {"enabled": True},
    }
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            # Merge loaded into defaults (shallow per section)
            for section, section_defaults in defaults.items():
                if section in loaded and isinstance(loaded[section], dict):
                    section_defaults.update({k: v for k, v in loaded[section].items() if not k.startswith("_")})
            _RUNNER_CONFIG = defaults
        except Exception as e:
            print(f"WARNING: Failed to load {config_path}: {e}. Using defaults.", file=sys.stderr)
            _RUNNER_CONFIG = defaults
    else:
        _RUNNER_CONFIG = defaults
    return _RUNNER_CONFIG


def rc(section: str, key: str, default: Any = None) -> Any:
    """Read a runner config value. rc("api", "base_url") -> "https://..."."""
    if not _RUNNER_CONFIG:
        _load_runner_config()
    return _RUNNER_CONFIG.get(section, {}).get(key, default)

# Ensure the app package is importable
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

try:
    from app.services.slot_selection_service import SlotSelector
    HAS_SERVICES = True
except ImportError:
    HAS_SERVICES = False

# OpenRouter free tier config — doesn't depend on app services
OPENROUTER_HEALTHCHECK_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"
OPENROUTER_FREE_MODELS = (OPENROUTER_HEALTHCHECK_MODEL,)


def wait_openrouter_rate_limit() -> None:
    """Placeholder — no rate limiting needed for free tier."""
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
    API_BASE = rc("api", "base_url", "https://api.coherencycoin.com")
except ImportError:
    API_BASE = rc("api", "base_url", "https://api.coherencycoin.com")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_NODE_NAME = socket.gethostname()
# Persistent node ID — hash of hostname so it survives restarts
def _stable_node_id() -> str:
    """Generate a stable, persistent node ID.

    Uses hostname + OS type (same as outer runner). Persisted to
    ~/.coherence-network/node_id so it never changes even if hostname changes.
    """
    id_file = Path.home() / ".coherence-network" / "node_id"
    if id_file.exists():
        stored = id_file.read_text().strip()
        if stored:
            return stored

    # Generate from hostname + OS (matches scripts/local_runner.py)
    hostname = socket.gethostname()
    os_type = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
    raw = f"{hostname}:{os_type}"
    node_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    # Persist
    id_file.parent.mkdir(parents=True, exist_ok=True)
    id_file.write_text(node_id)
    return node_id


_NODE_ID = _stable_node_id()


def _completed_process_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value or "")


def _is_dubious_ownership_failure(proc: object) -> bool:
    stderr = _completed_process_text(getattr(proc, "stderr", ""))
    stdout = _completed_process_text(getattr(proc, "stdout", ""))
    detail = f"{stderr}\n{stdout}".lower()
    return "detected dubious ownership" in detail and "safe.directory" in detail


def _run_git_command(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    proc = subprocess.run(args, **kwargs)
    if proc.returncode == 0:
        return proc

    if any(str(arg).startswith("safe.directory=") for arg in args):
        return proc

    cwd = kwargs.get("cwd")
    if not cwd or not _is_dubious_ownership_failure(proc):
        return proc

    safe_dir = str(Path(cwd).resolve())
    retry_args = [args[0], "-c", f"safe.directory={safe_dir}", *args[1:]]
    log.info("GIT_SAFE_DIRECTORY_RETRY cwd=%s", safe_dir)
    return subprocess.run(retry_args, **kwargs)


def _get_git_info() -> dict[str, str]:
    """Get git version info for this node."""
    repo = str(_REPO_DIR)
    info = {"local_sha": "unknown", "origin_sha": "unknown", "branch": "unknown", "dirty": "unknown", "repo": repo}
    git = "/usr/bin/git"  # Use absolute path -- launchd may not have git on PATH
    if not os.path.exists(git):
        git = "git"  # Fallback
    try:
        r = _run_git_command([git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["local_sha"] = r.stdout.strip()
        _run_git_command([git, "fetch", "origin", "main", "--quiet"], capture_output=True, timeout=15, cwd=repo)
        r = _run_git_command([git, "rev-parse", "--short", "origin/main"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["origin_sha"] = r.stdout.strip()
        r = _run_git_command([git, "branch", "--show-current"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["branch"] = r.stdout.strip()
        r = _run_git_command([git, "status", "--porcelain"], capture_output=True, text=True, timeout=5, cwd=repo)
        info["dirty"] = "yes" if r.stdout.strip() else "no"
        info["up_to_date"] = "yes" if info["local_sha"] == info["origin_sha"] else "no"
    except Exception as e:
        info["error"] = str(e)
    # Debug: write git info to a temp file so we can diagnose launchd issues
    try:
        Path("/tmp/coherence-git-debug.txt").write_text(
            f"repo={info.get('repo')}\n"
            f"local_sha={info.get('local_sha')}\n"
            f"origin_sha={info.get('origin_sha')}\n"
            f"error={info.get('error','none')}\n"
            f"git_binary={git}\n"
            f"git_exists={os.path.exists(git) if isinstance(git, str) else 'N/A'}\n"
        )
    except Exception:
        pass
    return info


_NODE_GIT = _get_git_info()

_TASK_TIMEOUT = [rc("execution", "timeout_default_s", 300)]  # 10 min default — real code takes time
_RESUME_MODE = [False]
_SKIP_PERMISSIONS = [True]  # --dangerously-skip-permissions for claude; operators can disable
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
try:
    from app.services.config_service import get_hub_url as _get_hub
    _OPENROUTER_REFERER = rc("providers", "openrouter_referer", "https://coherencycoin.com")
except ImportError:
    _OPENROUTER_REFERER = rc("providers", "openrouter_referer", "https://coherencycoin.com")


# ── Provider registry (auto-detected) ───────────────────────────────

def _check_claude_auth() -> bool:
    """Verify Claude CLI is authenticated — not just installed."""
    # If running inside a Claude Code session, auth is inherited
    if os.environ.get("CLAUDECODE") == "1":
        log.info("Claude auth: running inside Claude Code session — auth inherited")
        return True
    # If ANTHROPIC_API_KEY is set, Claude CLI will use it
    if os.environ.get("ANTHROPIC_API_KEY"):
        log.info("Claude auth: ANTHROPIC_API_KEY set")
        return True
    try:
        claude_path = shutil.which("claude")
        if not claude_path:
            return False
        # Don't use --bare: it skips stored OAuth credentials
        result = subprocess.run(
            [claude_path, "-p", "reply with just OK", "--dangerously-skip-permissions", "--output-format", "text"],
            capture_output=True, text=True, timeout=15,
            stdin=subprocess.DEVNULL,
        )
        combined = (result.stdout + result.stderr).lower()
        if "not logged in" in combined or "please run /login" in combined:
            log.warning("Claude CLI not authenticated — run 'claude /login' to fix. Skipping provider.")
            return False
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception as exc:
        log.warning("Claude auth check failed: %s", exc)
        return False


def _detect_providers() -> dict[str, dict]:
    """Auto-detect available providers on this machine.

    Every provider is equal — CLI or API, all treated the same by Thompson Sampling.
    CLIs are detected by binary presence; API providers by reachability.
    """
    providers = {}
    cli_specs = {
        # claude -p: non-interactive prompt mode WITH tool access (can read/write files)
        # --dangerously-skip-permissions: bypass all permission checks
        # --output-format text: plain text output (no JSON wrapping)
        # NOTE: --print disables tools — never use it for impl/test tasks
        "claude": {"cmd": ["claude", "-p", "--dangerously-skip-permissions", "--allowedTools", "Bash,Read,Edit,Write,Glob,Grep,WebFetch", "--output-format", "text"], "append_prompt": True, "check": _check_claude_auth},
        # codex exec --full-auto: non-interactive sandboxed execution
        "codex": {"cmd": ["codex", "exec", "--full-auto"], "append_prompt": True},
        # gemini -y -p <prompt>: yolo mode (auto-approve tools) + headless
        # -y is required: without it, tool calls block on approval (issue #12362)
        "gemini": {"cmd": ["gemini", "-y", "-p"], "append_prompt": True},
        # cursor agent -p: Cursor's headless agent mode
        "cursor": {"cmd": ["agent", "--model", "auto", "--trust", "-p"], "append_prompt": True, "check_binary": "agent"},
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
        # Add extra flags (e.g. --output-format text for claude)
        for flag in spec.pop("extra_flags", []):
            spec["cmd"].append(flag)
        # Optional health check
        checker = spec.pop("check", None)
        if checker and not checker():
            log.info("Provider skipped (not ready): %s", name)
            continue
        # Detect provider version
        version = "unknown"
        try:
            version_flags = {"claude": "--version", "codex": "--version", "gemini": "--version", "agent": "--version", "ollama": "--version"}
            vflag = version_flags.get(binary.split("/")[-1] if "/" in binary else binary, "--version")
            vresult = subprocess.run([resolved, vflag], capture_output=True, text=True, timeout=5)
            vout = (vresult.stdout or vresult.stderr or "").strip()
            # Extract version string — first line, strip common prefixes
            if vout:
                vline = vout.split("\n")[0].strip()
                for prefix in ["claude ", "codex-cli ", "codex ", "gemini ", "ollama version is ", "ollama version ", "agent "]:
                    if vline.lower().startswith(prefix):
                        vline = vline[len(prefix):].strip()
                        break
                # Strip trailing parenthetical labels like "(Claude Code)"
                vline = re.sub(r"\s*\(.*?\)\s*$", "", vline).strip()
                version = vline[:40]  # cap at 40 chars
        except Exception:
            pass
        spec["_version"] = version

        # Optional model selection (e.g., ollama picks best available model)
        model_selector = spec.pop("model_select", None)
        if model_selector:
            model = model_selector()
            if not model:
                log.info("Provider skipped (no model): %s", name)
                continue
            spec["cmd"].append(model)
            log.info("Provider detected: %s model=%s version=%s", name, model, version)
        else:
            log.info("Provider detected: %s (%s) version=%s", name, resolved, version)
        providers[name] = spec

    # API-based providers (no CLI binary needed)
    # OpenRouter: DISABLED — cannot produce PRs, generates hollow completions.
    # Re-enable by removing "openrouter" from _PAUSED_PROVIDERS and uncommenting below.
    # if _check_openrouter():
    #     providers["openrouter"] = {
    #         "api": True,
    #         "models": list(OPENROUTER_FREE_MODELS),
    #         "tool_capable": False,
    #     }
    #     log.info("Provider detected: openrouter (API free tier)")
    log.info("Provider DISABLED: openrouter (paused — hollow completions, no PR capability)")

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
    api_key = rc("providers", "openrouter_api_key", "") or ""
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
# Text-only providers cannot create files, run tests, or push branches.
# They should NEVER be selected for impl, test, or code-producing tasks.
_TEXT_ONLY_PROVIDERS = {"ollama-local", "ollama-cloud", "openrouter"}
# Providers that are paused — detected but never selected
_PAUSED_PROVIDERS = {"openrouter"}  # Cannot produce PRs, generates hollow completions

PROVIDERS: dict[str, dict] = {}  # populated at startup


def _provider_has_tools(provider: str) -> bool:
    """Does this provider have tool/file access?"""
    spec = PROVIDERS.get(provider) or {}
    if "tool_capable" in spec:
        return bool(spec.get("tool_capable"))
    return provider in _TOOL_PROVIDERS



# Data-driven provider routing: auto-compute which providers work for each task type
# from Thompson Sampling measurements. No hardcoded tiers — the data decides.
_MIN_SUCCESS_RATE = 0.40   # providers below 40% success for a task type are excluded
_MIN_SAMPLES = 3           # need at least 3 samples before excluding
_ROUTING_CACHE: dict[str, tuple[list[str], float]] = {}  # task_type -> (eligible, timestamp)
_ROUTING_CACHE_TTL = 300   # refresh every 5 minutes


def _compute_eligible_providers(task_type: str, available: list[str]) -> list[str]:
    """Use Thompson Sampling measurements to filter out providers that consistently fail."""
    import time as _time
    now = _time.time()

    cache_key = task_type
    if cache_key in _ROUTING_CACHE:
        cached, ts = _ROUTING_CACHE[cache_key]
        if now - ts < _ROUTING_CACHE_TTL:
            result = [p for p in cached if p in available]
            if result:
                return result

    # Read measurement file for this task type
    measurement_file = Path("api/logs/slot_measurements") / f"provider_{task_type}.json"
    if not measurement_file.exists():
        # No data yet — allow all
        return available

    try:
        data = json.loads(measurement_file.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            return available

        # Aggregate by slot_id (provider name)
        from collections import defaultdict
        stats: dict[str, dict] = defaultdict(lambda: {"ok": 0, "fail": 0})
        for entry in data:
            slot = entry.get("slot_id", "")
            if not slot:
                continue
            if entry.get("value_score", 0) > 0.5:
                stats[slot]["ok"] += 1
            else:
                stats[slot]["fail"] += 1

        # Filter: exclude providers below threshold with enough samples
        eligible = []
        excluded = []
        for p in available:
            s = stats.get(p)
            if not s:
                eligible.append(p)  # no data = give it a chance
                continue
            total = s["ok"] + s["fail"]
            if total < _MIN_SAMPLES:
                eligible.append(p)  # not enough data = give it a chance
                continue
            rate = s["ok"] / total
            if rate >= _MIN_SUCCESS_RATE:
                eligible.append(p)
            else:
                excluded.append(f"{p}({rate:.0%})")

        if excluded:
            log.info("ROUTING_DATA task=%s excluded=%s (below %.0f%% with %d+ samples)",
                     task_type, excluded, _MIN_SUCCESS_RATE * 100, _MIN_SAMPLES)

        if not eligible:
            log.warning("ROUTING_DATA all providers below threshold for %s — using all", task_type)
            eligible = available

        _ROUTING_CACHE[cache_key] = (eligible, now)
        return [p for p in eligible if p in available]

    except Exception as e:
        log.debug("ROUTING_DATA failed to read measurements for %s: %s", task_type, e)
        return available


def select_provider(task_type: str, task: dict | None = None) -> str:
    """Select provider for a task using data-driven routing.

    Rules (all learned from Thompson Sampling measurements):
    - Paused providers are never selected
    - Providers below 40% success rate (with 3+ samples) are excluded for that task type
    - Remaining providers compete via Thompson Sampling
    - Respects exclude_provider from retry context
    """
    available = [p for p in PROVIDERS.keys() if p not in _PAUSED_PROVIDERS]
    if not available:
        raise RuntimeError("No providers available (all paused)")

    # Capability-based filtering: each task type needs specific provider capabilities
    # Providers without required capabilities are excluded BEFORE Thompson Sampling
    _CAPABILITIES = {
        # What each task type needs:
        "spec":        {"file_write", "git"},           # write spec files, commit
        "impl":        {"file_write", "git", "tools"},  # write code, commit, run commands
        "test":        {"file_write", "git", "tools"},  # write tests, run pytest, commit
        "review":      {"tools", "gh"},                 # read files, run gh pr review
        "code-review": {"tools", "gh"},
        "merge":       {"tools", "gh"},                 # run gh pr merge
        "deploy":      {"tools", "ssh"},                # ssh to VPS
        "verify":      {"tools"},                       # curl, check endpoints
    }
    # What each provider has:
    _PROVIDER_CAPS = {
        "claude":       {"file_write", "git", "tools", "gh", "ssh", "reasoning"},
        "codex":        {"file_write", "git", "tools", "gh", "reasoning"},
        "cursor":       {"file_write", "git", "tools", "gh", "reasoning"},  # v2026.03.25 + --trust fixes file editing
        "gemini":       {"file_write", "git", "tools", "gh", "reasoning"},
        "ollama-local": {"text_only"},                   # no tools, no file access
        "ollama-cloud": {"text_only"},                   # no tools, no file access
        "openrouter":   {"text_only"},                   # API only, no tools
    }

    required = _CAPABILITIES.get(task_type, set())
    if required:
        capable = [p for p in available if required.issubset(_PROVIDER_CAPS.get(p, set()))]
        if capable:
            if set(capable) != set(available):
                excluded = set(available) - set(capable)
                log.info("CAPABILITY_FILTER task=%s required=%s excluded=%s (missing capabilities)",
                         task_type, required, excluded)
            available = capable
        else:
            log.warning("CAPABILITY_FILTER task=%s needs %s but no provider has all — using all", task_type, required)

    # Respect exclude_provider from retry context
    if task:
        ctx = task.get("context") or {}
        exclude = ctx.get("exclude_provider", "")
        if exclude and exclude in available and len(available) > 1:
            available = [p for p in available if p != exclude]
            log.info("PROVIDER_EXCLUDE task=%s excluded=%s remaining=%s", task_type, exclude, available)

    # Data-driven filtering: exclude providers that fail too often for this task type
    available = _compute_eligible_providers(task_type, available)

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


_provider_streak: dict[str, list[dict]] = {}  # provider → list of {ok, task_type, duration}
_provider_streak_lock = threading.Lock()


def _record_provider_streak(provider: str, task_type: str, success: bool, duration: float):
    """Track per-provider outcome ring buffer (last 20) for streak display."""
    with _provider_streak_lock:
        if provider not in _provider_streak:
            _provider_streak[provider] = []
        ring = _provider_streak[provider]
        ring.append({"ok": success, "task_type": task_type, "duration": round(duration, 1)})
        if len(ring) > 20:
            _provider_streak[provider] = ring[-20:]


def get_provider_streaks() -> dict[str, dict]:
    """Return per-provider streak summaries for heartbeat/display."""
    with _provider_streak_lock:
        result = {}
        for provider, ring in _provider_streak.items():
            ok = sum(1 for r in ring if r["ok"])
            fail = len(ring) - ok
            last_10 = ["ok" if r["ok"] else "fail" for r in ring[-10:]]
            avg_dur = sum(r["duration"] for r in ring) / len(ring) if ring else 0
            result[provider] = {
                "completed": ok, "failed": fail, "total": len(ring),
                "success_rate": ok / len(ring) if ring else None,
                "avg_duration_s": round(avg_dur, 1),
                "last_10": last_10,
            }
        return result


def record_provider_outcome(
    task_type: str, provider: str, success: bool, duration: float, output: str = "",
):
    """Record provider outcome with error classification for root-cause analysis."""
    _record_provider_streak(provider, task_type, success, duration)
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

_PHASE_SEQUENCE = ("spec", "impl", "test", "code-review", "merge", "deploy", "verify", "reflect", "review")
_NEXT_PHASE: dict[str, str | None] = {
    "spec": "impl",
    "impl": "test",
    "test": "code-review",
    "code-review": "merge",
    "merge": "deploy",
    "deploy": "verify",
    "verify": "reflect",
    "reflect": None,
    # Backward compat: old "review" tasks map to code-review
    "review": None,
}

# Per-work_type phase sequences — determines which phases are skipped for each work type.
# Keys match IdeaWorkType values. None = default (full pipeline).
_PHASE_SEQUENCES_BY_WORK_TYPE: dict[str | None, tuple[str, ...]] = {
    "exploration": ("spec", "impl", "reflect"),
    "research":    ("spec", "impl", "reflect"),
    "prototype":   ("spec", "impl", "test", "reflect"),
    "feature":     ("spec", "impl", "test", "code-review", "merge", "deploy", "verify", "reflect"),
    "enhancement": ("spec", "impl", "test", "code-review", "merge", "deploy", "verify", "reflect"),
    "bug-fix":     ("impl", "test", "code-review", "merge", "deploy", "verify", "reflect"),
    "mvp":         ("spec", "impl", "test", "merge", "deploy", "verify", "reflect"),
    None:          ("spec", "impl", "test", "code-review", "merge", "deploy", "verify", "reflect"),
}


def _next_phase_for_work_type(current_phase: str, work_type: str | None) -> str | None:
    """Return the next phase for an idea given its work_type.

    Falls back to the global _NEXT_PHASE map if work_type is unknown.
    """
    seq = _PHASE_SEQUENCES_BY_WORK_TYPE.get(work_type, _PHASE_SEQUENCES_BY_WORK_TYPE[None])
    if current_phase in seq:
        idx = seq.index(current_phase)
        return seq[idx + 1] if idx + 1 < len(seq) else None
    # Phase not in this work_type's sequence — use global fallback
    return _NEXT_PHASE.get(current_phase)


def api(method: str, path: str, body: dict | None = None, _retries: int = 0) -> dict | list | None:
    """Call the API via httpx. Auto-retries on 429 with backoff."""
    url = f"{API_BASE}{path}"
    headers = {"X-Api-Key": rc("api", "api_key", "dev-key")}
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
        "status": "running", "worker_id": WORKER_ID,
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

    API_BASE = rc("deploy", "api_base", "https://api.coherencycoin.com")

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
        WEB_BASE = rc("deploy", "web_base", "https://coherencycoin.com")
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


def _check_existing_evidence(idea_id: str) -> tuple[str, str] | None:
    """Check if an idea is already implemented on main by searching merged PRs and commits.

    Returns (pr_or_sha, evidence_type) if found, None if not.
    """
    cwd = str(_REPO_DIR)

    # 1. Search for merged PRs mentioning this idea_id
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--search", idea_id,
             "--json", "number,mergedAt", "--limit", "5"],
            capture_output=True, text=True, timeout=15, cwd=cwd,
            shell=(sys.platform == "win32"),
        )
        if result.returncode == 0 and result.stdout.strip():
            prs = json.loads(result.stdout)
            if prs:
                # Pick most recently merged
                prs.sort(key=lambda p: p.get("mergedAt", ""), reverse=True)
                return (str(prs[0]["number"]), "merged" if len(prs) == 1 else f"merged({len(prs)})")
    except Exception as e:
        log.debug("EVIDENCE_CHECK gh pr failed for %s: %s", idea_id, e)

    # 2. Search for commits on main mentioning this idea_id
    try:
        result = subprocess.run(
            ["git", "log", "origin/main", "--oneline", "--grep", idea_id, "-3"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                sha = lines[0].split()[0]
                return (sha, f"commit({len(lines)})")
    except Exception as e:
        log.debug("EVIDENCE_CHECK git log failed for %s: %s", idea_id, e)

    return None


def _extract_pr_from_completed_tasks(idea_tasks: dict, phase: str) -> str:
    """Extract PR number from a completed task's output for a given phase."""
    tasks = idea_tasks.get("tasks", [])
    for t in reversed(tasks):
        if t.get("task_type") == phase and t.get("status") == "completed":
            output = str(t.get("output") or t.get("result") or "")
            # Look for PR_NUMBER: 123 or PR: .../pull/123
            import re
            m = re.search(r"PR_NUMBER:\s*(\d+)", output)
            if m:
                return m.group(1)
            m = re.search(r"pull/(\d+)", output)
            if m:
                return m.group(1)
            # Check context
            ctx = t.get("context") or {}
            if ctx.get("pr_number"):
                return str(ctx["pr_number"])
    return ""


def _extract_branch_from_completed_tasks(idea_tasks: dict, phase: str) -> str:
    """Extract impl branch name from a completed task's output."""
    tasks = idea_tasks.get("tasks", [])
    for t in reversed(tasks):
        if t.get("task_type") == phase and t.get("status") == "completed":
            output = str(t.get("output") or t.get("result") or "")
            import re
            m = re.search(r"IMPL_BRANCH:\s*(\S+)", output)
            if m:
                return m.group(1)
            # Check context
            ctx = t.get("context") or {}
            if ctx.get("impl_branch"):
                return str(ctx["impl_branch"])
    return ""


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

    # Fetch idea to get work_type for phase-ladder branching
    idea_payload: dict | None = api("GET", f"/api/ideas/{idea_id}")
    idea_work_type: str | None = None
    idea_workspace_git_url: str = ""
    if isinstance(idea_payload, dict):
        idea_work_type = idea_payload.get("work_type")
        idea_workspace_git_url = idea_payload.get("workspace_git_url") or ""
    next_phase = _next_phase_for_work_type(task_type, idea_work_type)
    if next_phase and not _has_any_tasks_for_phase(idea_tasks_payload, next_phase):
        idea_name = str((idea_payload or {}).get("name") or idea_id) if isinstance(idea_payload, dict) else idea_id
        idea_desc = str((idea_payload or {}).get("description") or "") if isinstance(idea_payload, dict) else ""

        extra_context: dict = {}  # PR/branch info passed to downstream phases
        if idea_workspace_git_url:
            extra_context["workspace_git_url"] = idea_workspace_git_url

        # Idea scope header prepended to every direction so providers know exactly what they're working on
        _workspace_line = f"workspace: {idea_workspace_git_url}\n" if idea_workspace_git_url else ""
        _idea_scope_header = (
            f"─── IDEA SCOPE ───\n"
            f"idea_id: {idea_id}\n"
            f"idea_name: {idea_name}\n"
            f"phase: {next_phase}\n"
            f"{_workspace_line}"
            f"───────────────────\n\n"
        )

        # Phase-specific direction with quality requirements
        if next_phase == "spec":
            direction = (
                f"Write a spec for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Write the spec in specs/ following the existing spec format. The spec MUST include:\n"
                f"1. A clear 'Verification' section with at least 3 concrete acceptance criteria\n"
                f"2. Test scenarios that prove the feature works (expected inputs → expected outputs)\n"
                f"3. Expected API responses or UI behaviors — not vague goals\n"
                f"4. Edge cases and error handling expectations\n"
                f"5. A 'Risks and Assumptions' section\n"
                f"6. A 'Known Gaps and Follow-up Tasks' section\n\n"
                f"The spec must be precise enough that an implementation task can verify against it.\n"
                f"If you cannot define concrete verification criteria, the idea is not ready for a spec — "
                f"say so and explain what question needs answering first.\n\n"
                f"Run `python3 scripts/validate_spec_quality.py` before finishing."
            )
        elif next_phase == "code-review":
            # Find open PRs for this idea
            pr_ref = ""
            try:
                pr_check = subprocess.run(
                    ["gh", "pr", "list", "--search", idea_id, "--json", "number,title,url", "--limit", "1"],
                    capture_output=True, text=True, timeout=10, cwd=str(_REPO_DIR),
                    shell=(sys.platform == "win32"),
                )
                if pr_check.returncode == 0:
                    import json as _json
                    prs = _json.loads(pr_check.stdout)
                    if prs:
                        pr_ref = f"\n\nOpen PR: {prs[0]['url']}\nReview the PR diff: gh pr diff {prs[0]['number']}\n"
            except Exception:
                pass

            direction = (
                f"Code review for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n"
                f"{pr_ref}\n"
                f"REVIEW CHECKLIST:\n"
                f"1. Read the spec (specs/ directory) — does the code match requirements?\n"
                f"2. Check git log for recent impl/test commits for this idea\n"
                f"3. Read the changed files — are there obvious bugs or missing error handling?\n"
                f"4. Are there tests? Do they cover the key scenarios from the spec?\n"
                f"5. Run the tests: python -m pytest api/tests/ -x -q 2>/dev/null\n"
                f"6. Check code follows project conventions (CLAUDE.md)\n\n"
                f"If there's an open PR, approve or request changes:\n"
                f"  gh pr review <number> --approve  (if code is good)\n"
                f"  gh pr review <number> --request-changes -b \"<issues>\"  (if not)\n\n"
                f"Output: CODE_REVIEW_PASSED or CODE_REVIEW_FAILED with specific issues."
            )
        elif next_phase == "deploy":
            direction = (
                f"Deploy '{idea_name}' ({idea_id}) to production.\n\n"
                f"1. Verify code is committed and pushed to main\n"
                f"2. Run: cc deploy (or SSH deploy if cc deploy unavailable)\n"
                f"3. Verify health check passes: curl https://api.coherencycoin.com/api/health\n"
                f"4. If deploy fails, report DEPLOY_FAILED with the error\n"
                f"5. If health check fails after deploy, report DEPLOY_FAILED — rollback needed\n\n"
                f"Output DEPLOY_PASSED with the deployed SHA or DEPLOY_FAILED with error details."
            )
        elif next_phase == "verify":
            direction = (
                f"Verify '{idea_name}' ({idea_id}) works on production.\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Run the spec's verification scenarios against PRODUCTION:\n"
                f"  - API: curl https://api.coherencycoin.com/...\n"
                f"  - Web: check https://coherencycoin.com/...\n"
                f"  - CLI: run cc <command>\n\n"
                f"For EACH scenario report PASS or FAIL with actual output.\n"
                f"If ANY scenario fails, output VERIFY_FAILED with details.\n"
                f"If ALL pass, output VERIFY_PASSED with evidence.\n\n"
                f"If the feature is publicly broken (404, 500, wrong data),\n"
                f"this is a HOTFIX priority — note what needs immediate fixing."
            )
        elif next_phase == "review":
            # Extract PR info from the completed impl task
            pr_number = _extract_pr_from_completed_tasks(idea_tasks_payload, "impl")
            impl_branch = _extract_branch_from_completed_tasks(idea_tasks_payload, "impl")
            pr_instruction = ""
            if pr_number:
                pr_instruction = (
                    f"\n\nThis review is for PR #{pr_number}.\n"
                    f"1. Read the PR diff: gh pr diff {pr_number}\n"
                    f"2. Review the code for correctness, security, completeness\n"
                    f"3. Post your review using GitHub's review feature:\n"
                    f"   gh pr review {pr_number} --approve --body 'LGTM: <summary>'\n"
                    f"   OR: gh pr review {pr_number} --request-changes --body 'Issues: <details>'\n"
                )
            direction = (
                f"Code review for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n"
                f"{pr_instruction}\n"
                f"Output REVIEW_PASSED or REVIEW_FAILED with specific issues."
            )
            extra_context["pr_number"] = pr_number
            extra_context["impl_branch"] = impl_branch
        elif next_phase == "test":
            # Extract PR branch from completed impl task so tests push to same PR
            impl_branch = _extract_branch_from_completed_tasks(idea_tasks_payload, "impl")
            pr_number = _extract_pr_from_completed_tasks(idea_tasks_payload, "impl")
            branch_instruction = ""
            if impl_branch:
                branch_instruction = (
                    f"\n\nIMPORTANT: The implementation is on branch '{impl_branch}'.\n"
                    f"First checkout that branch: git fetch origin {impl_branch} && git checkout {impl_branch}\n"
                    f"Write your tests on THIS branch so they go into the same PR.\n"
                )
            direction = (
                f"Write and run tests for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n"
                f"{branch_instruction}\n"
                f"INSTRUCTIONS:\n"
                f"1. Write pytest test files in api/tests/ that verify the feature works\n"
                f"2. Run the tests: cd api && python -m pytest tests/test_{idea_id.replace('-','_')}.py -v --timeout=60\n"
                f"3. If tests fail, fix the tests until they pass\n"
                f"4. Stage and commit: git add <test-files> && git commit -m \"test({idea_id}): <summary>\"\n"
                f"5. Do NOT push or create new PRs — the runner handles that\n\n"
                f"Tests must be RUNNABLE and PASSING.\n"
                f"Output: TESTS_FILE=<path>, TESTS_RUN=<count>, TESTS_PASSED=<count>, TESTS_FAILED=<count>"
            )
            extra_context["impl_branch"] = impl_branch
            extra_context["pr_number"] = pr_number
        elif next_phase == "impl":
            # Read the spec content directly to give the provider full context
            spec_ref = ""
            resolved_spec_path = ""
            try:
                import glob as _glob
                # Exact match first, then glob fallback
                exact = _REPO_DIR / "specs" / f"{idea_id}.md"
                if exact.exists():
                    spec_files = [str(exact)]
                else:
                    spec_files = _glob.glob(str(_REPO_DIR / "specs" / f"*{idea_id}*"))
                if spec_files:
                    resolved_spec_path = spec_files[0]
                    with open(resolved_spec_path, "r", encoding="utf-8", errors="replace") as sf:
                        spec_content = sf.read()[:3000]
                    spec_ref = f"\n\nSpec ({resolved_spec_path}):\n```\n{spec_content}\n```\n"
            except Exception:
                pass
            extra_context["spec_path"] = resolved_spec_path or "none"

            direction = (
                f"Implement '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:500]}\n"
                f"{spec_ref}\n"
                f"YOU MUST CREATE OR MODIFY ACTUAL FILES. This is not a planning task.\n\n"
                f"Where to put code:\n"
                f"- API endpoints: api/app/routers/<name>.py\n"
                f"- Services: api/app/services/<name>.py\n"
                f"- Models: api/app/models/<name>.py\n"
                f"- Web pages: web/app/<route>/page.tsx\n"
                f"- CLI: cli/bin/cc.mjs\n"
                f"- Specs: specs/<id>.md\n\n"
                f"MANDATORY: After writing each code file, verify it with DIF:\n"
                f"  curl -s -X POST https://dif.merly.ai/api/v2/dif/verify \\\n"
                f"    -H 'Content-Type: application/json' \\\n"
                f"    -d '{{\"language\": \"python\", \"code\": \"'\"$(cat <file>)\"'\"}}'\n"
                f"Read the DIF JSON response. Check:\n"
                f"  - trust_signal: 'positive' or 'review' = ok. 'concern' = MUST FIX before continuing.\n"
                f"  - scores.verification: >40 ok, <30 rethink approach\n"
                f"  - top_finding: read the excerpt, fix the flagged code if it's a real issue\n"
                f"If DIF flags concerns, fix the code and re-verify. Include in your output:\n"
                f"  DIF_EVENT=<eventId> DIF_TRUST=<trust_signal> DIF_SCORE=<verification>\n\n"
                f"After writing and verifying files:\n"
                f"  git add -A && git diff --cached --stat\n"
                f"  git commit -m \"impl({idea_id}): <summary>\"\n\n"
                f"If the spec doesn't exist or is too vague to implement, output:\n"
                f"  IMPL_BLOCKED: <what specific information is missing>\n\n"
                f"Output on success: FILES_CHANGED=<list>, COMMIT=<sha>, DIF_EVENT=<id>, DIF_TRUST=<signal>"
            )
        elif next_phase == "merge":
            direction = (
                f"Merge the PR for '{idea_name}' ({idea_id}).\n\n"
                f"1. Find the open PR: gh pr list --search '{idea_id}' --json number,title,url\n"
                f"2. Check PR status: gh pr checks <number>\n"
                f"3. If tests passed and review approved, merge: gh pr merge <number> --squash\n"
                f"4. If tests failed or review has requested changes, output MERGE_BLOCKED with reason\n"
                f"5. After merge, verify: git log origin/main --oneline -1\n\n"
                f"Output: MERGE_PASSED with merged SHA, or MERGE_BLOCKED with reason."
            )
        elif next_phase == "reflect":
            direction = (
                f"Reflect on the completed lifecycle for '{idea_name}' ({idea_id}).\n\n"
                f"1. Check what was built: git log --oneline -10 | grep '{idea_id}'\n"
                f"2. Verify it's on production: curl -s https://api.coherencycoin.com/api/health\n"
                f"3. Record a contribution:\n"
                f"   cc contribute --type code --idea {idea_id} --desc 'Full lifecycle: spec→impl→test→review→merge→deploy→verify'\n"
                f"4. Update the idea's coherence score if possible\n"
                f"5. Check if there are follow-up tasks or gaps identified during review\n\n"
                f"Output: REFLECT_COMPLETE with summary of what was delivered, coherence impact, "
                f"and any follow-up ideas that emerged."
            )
        else:
            direction = (
                f"Execute the '{next_phase}' phase for '{idea_name}' ({idea_id}).\n\n"
                f"Description: {idea_desc[:300]}\n\n"
                f"Follow the project's CLAUDE.md conventions. Work in the repository."
            )
        # Prepend idea scope header so every provider prompt starts with clear context
        direction = _idea_scope_header + direction

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
                    **extra_context,
                },
            },
        )
        if isinstance(created, dict):
            _append_idea_event(idea_id, "phase_advanced", {
                "from_phase": task_type,
                "to_phase": next_phase,
            })
        else:
            log.warning(
                "AUTO_PHASE enqueue failed idea_id=%s from=%s to=%s",
                idea_id,
                task_type,
                next_phase,
            )

    # Determine manifestation status with validation gate
    if idea_payload is None:
        idea_payload = api("GET", f"/api/ideas/{idea_id}")
    if next_phase is None:
        # All phases should be complete — verify before marking validated
        # ALSO verify that completed tasks had meaningful output (not empty)
        # Accept either old (review) or new (code-review + deploy + verify) phase set
        required_phases = {"spec", "test", "impl"}
        # Need at least one of: review, code-review, or verify
        review_phases = {"review", "code-review", "verify"}
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

        # Also check for REVIEW_FAILED in output — review must pass, not just complete
        failed_phases = set()
        if isinstance(idea_tasks_check, dict):
            for g in (idea_tasks_check.get("groups") or []):
                if not isinstance(g, dict):
                    continue
                phase = g.get("task_type", "")
                for t in (g.get("tasks") or []):
                    if t.get("status") == "completed":
                        t_output = (t.get("output") or "").strip().upper()
                        if "REVIEW_FAILED" in t_output or "SPEC_FAILED" in t_output or "TEST_FAILED" in t_output:
                            failed_phases.add(phase)

        log.info("VALIDATION_GATE idea=%s completed_phases=%s empty_phases=%s failed_phases=%s",
                 idea_id, sorted(completed_phases), sorted(empty_phases), sorted(failed_phases))
        missing = required_phases - completed_phases
        has_review = bool(completed_phases & review_phases)
        if missing or not has_review:
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
        elif failed_phases:
            log.warning(
                "VALIDATION_GATE idea=%s blocked: phases with FAILED output %s — "
                "these need re-execution with passing results",
                idea_id, sorted(failed_phases),
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

def _read_file_capped(path: "Path | str", cap: int = 3000) -> str:
    """Read a file and cap at `cap` chars. Returns '' if missing."""
    try:
        raw = Path(path).read_text(errors="replace")
        if len(raw) > cap:
            return raw[:cap] + f"\n…(truncated at {cap} chars)"
        return raw
    except Exception:
        return ""


def _resolve_related_files(spec_content: str, direction: str, repo_dir: "Path") -> list[str]:
    """Extract file paths mentioned in spec/direction and filter to ones that exist."""
    import re as _re
    combined = spec_content + "\n" + direction
    # Match path-like tokens: optional leading /, then word/word... ending with a known extension
    pattern = _re.compile(
        r"(?<![`\"\'])"           # not in a quote (avoid URLs)
        r"(?:[\w.-]+/)+[\w.-]+"   # path segments
        r"\.(?:py|tsx?|mjs|md|json|yaml|yml|sh|sql|toml)"
    )
    seen: dict[str, None] = {}
    for m in pattern.finditer(combined):
        token = m.group(0).lstrip("/")
        if token not in seen:
            seen[token] = None
    # Keep only paths that exist in the repo
    result = []
    for rel in seen:
        full = repo_dir / rel
        if full.exists():
            result.append(rel)
    return result[:20]  # cap list


def _module_tree(repo_dir: "Path", subdirs: list[str], max_files: int = 30) -> str:
    """Return a compact file listing for given subdirectories."""
    lines: list[str] = []
    for sub in subdirs:
        d = repo_dir / sub
        if not d.exists():
            continue
        files = sorted(d.rglob("*"))
        shown = [f for f in files if f.is_file() and f.suffix in (".py", ".tsx", ".mjs", ".ts", ".md")]
        for f in shown[:max_files]:
            lines.append("  " + str(f.relative_to(repo_dir)))
        if len(shown) > max_files:
            lines.append(f"  …({len(shown) - max_files} more)")
    return "\n".join(lines)


def _build_context_block(
    task_type: str,
    idea_id: str,
    spec_path: str,
    direction: str,
    repo_dir: "Path",
) -> str:
    """Assemble the ## CONTEXT block injected into every impl/test/review prompt."""
    parts: list[str] = []

    # 1. Spec file — actual content, not just the path
    if spec_path and spec_path != "none":
        # Try absolute first, then relative to repo_dir
        spec_file = Path(spec_path) if Path(spec_path).is_absolute() else repo_dir / spec_path
        spec_raw = _read_file_capped(spec_file, cap=4000)
        if spec_raw:
            parts.append(f"### Spec: {spec_path}\n```markdown\n{spec_raw}\n```")
        else:
            # Fallback: glob for idea_id in specs/
            import glob as _glob
            matches = _glob.glob(str(repo_dir / "specs" / f"*{idea_id}*"))
            if matches:
                spec_raw = _read_file_capped(matches[0], cap=4000)
                if spec_raw:
                    parts.append(f"### Spec: {matches[0]}\n```markdown\n{spec_raw}\n```")

    # 2. CLAUDE.md — project conventions, agent guardrails, workflow
    for claude_md_path in [repo_dir / "CLAUDE.md", repo_dir / ".claude" / "CLAUDE.md"]:
        if claude_md_path.exists():
            content = _read_file_capped(claude_md_path, cap=2500)
            if content:
                parts.append(f"### Project conventions (CLAUDE.md)\n```\n{content}\n```")
            break

    # 3. Repo runbook — operational guidance
    for runbook_path in [
        repo_dir / "docs" / "RUNBOOK.md",
        repo_dir / "RUNBOOK.md",
        repo_dir / "docs" / "runbook.md",
    ]:
        if runbook_path.exists():
            content = _read_file_capped(runbook_path, cap=1500)
            if content:
                parts.append(f"### Runbook\n```\n{content}\n```")
            break

    # 4. Related files — mentioned in spec or direction, confirmed to exist
    related = _resolve_related_files(
        parts[0] if parts else "",   # spec content already gathered above
        direction,
        repo_dir,
    )
    if related:
        parts.append("### Related files in this repo\n" + "\n".join(f"  {r}" for r in related))

    # 5. Module map — directory listing for impl/test tasks
    if task_type in ("impl", "test"):
        subdirs = ["api/app/routers", "api/app/services", "api/app/models",
                   "web/app", "cli/lib", "specs"]
        tree = _module_tree(repo_dir, subdirs, max_files=25)
        if tree:
            parts.append(f"### Module map (key directories)\n{tree}")

    if not parts:
        return ""

    # Include parent and sibling idea context
    try:
        if idea_id and idea_id != "unknown":
            idea_data = api("GET", f"/api/ideas/{idea_id}")
            if isinstance(idea_data, dict):
                parent_id = idea_data.get("parent_idea_id")
                idea_name = idea_data.get("name", idea_id)
                child_ids = idea_data.get("child_idea_ids", [])

                related_lines = [f"\n\nIDEA CONTEXT — {idea_name} ({idea_id})"]
                if parent_id:
                    parent_data = api("GET", f"/api/ideas/{parent_id}")
                    if isinstance(parent_data, dict):
                        related_lines.append(f"Parent: {parent_data.get('name', parent_id)} ({parent_id})")
                        # Get siblings (other children of same parent)
                        siblings = [c for c in (parent_data.get("child_idea_ids") or []) if c != idea_id]
                        if siblings:
                            related_lines.append(f"Sister ideas (same parent): {', '.join(siblings[:6])}")

                if related_lines:
                    context_block = "\n".join(related_lines) + "\n\n## CONTEXT\n\n" + "\n\n---\n\n".join(parts)
                    return context_block
    except Exception:
        pass  # context enrichment is best-effort

    return "\n\n## CONTEXT\n\n" + "\n\n---\n\n".join(parts)


def _build_requirements_checklist(task_type: str, direction: str, spec_content: str) -> str:
    """Generate a structured requirements checklist from spec content and task direction.

    Agents must check off each item before marking the task complete.
    Returns a formatted checklist block to append to the prompt.
    """
    lines = []
    lines.append("\n\n" + "─" * 60)
    lines.append("REQUIREMENTS TRACKING SHEET — fill this in as you work")
    lines.append("─" * 60)
    lines.append("Before finishing, ALL items below must be ✅. If any remain ❌, keep working.")
    lines.append("")

    if task_type == "spec":
        lines += [
            "[ ] spec file written at specs/<idea_id>.md (min 500 chars)",
            "[ ] ## Summary section present",
            "[ ] ## Requirements section with explicit acceptance criteria",
            "[ ] ## Files section listing exact file paths to modify",
            "[ ] ## Verification Scenarios section (min 3 scenarios)",
            "[ ] ## Risks and Assumptions section",
            "[ ] spec committed: git commit -m 'spec(<idea>): ...'",
        ]
    elif task_type == "impl":
        # Extract requirements from spec if available
        req_lines = []
        if spec_content:
            in_req = False
            for line in spec_content.splitlines():
                stripped = line.strip()
                if stripped.startswith("## Req") or stripped.startswith("### Req"):
                    in_req = True
                    continue
                if in_req and stripped.startswith("##"):
                    in_req = False
                if in_req and stripped.startswith(("- ", "* ", "1.", "2.", "3.")):
                    req_text = stripped.lstrip("- *0123456789.").strip()
                    if len(req_text) > 10:
                        req_lines.append(f"[ ] {req_text[:100]}")

        if req_lines:
            lines.append("Spec requirements to implement:")
            lines += req_lines[:12]  # cap at 12
            lines.append("")

        lines += [
            "[ ] all target files created/modified (not just described)",
            "[ ] code is syntactically valid (no SyntaxError on import)",
            "[ ] imports and dependencies are correct",
            "[ ] no TODO stubs left — all functions have real implementations",
            "[ ] git add + git commit -m 'impl(<idea>): ...' done",
        ]
    elif task_type == "test":
        lines += [
            "[ ] test file written at api/tests/test_<idea_id>.py",
            "[ ] tests cover the happy path",
            "[ ] tests cover at least 2 edge/error cases",
            "[ ] pytest run: all tests PASSED (0 failures, 0 errors)",
            "[ ] git add + git commit -m 'test(<idea>): ...' done",
            "[ ] output includes: TESTS_FILE=<path> TESTS_RUN=<N> TESTS_PASSED=<N>",
        ]
    elif task_type in ("review", "code-review"):
        lines += [
            "[ ] read full implementation files (not just diff)",
            "[ ] checked: implementation matches spec requirements",
            "[ ] checked: no obvious bugs or security issues",
            "[ ] checked: edge cases handled",
            "[ ] posted review on PR via: gh pr review <num> --approve/--request-changes",
            "[ ] output includes: REVIEW_PASSED or REVIEW_FAILED",
        ]
    else:
        lines += [
            "[ ] task direction fully addressed",
            "[ ] output is substantive (not a description of what you would do)",
            "[ ] changes committed if any files were modified",
        ]

    lines.append("")
    lines.append("DONE SIGNAL: When ALL items above show ✅, output 'TASK_COMPLETE' and stop.")
    lines.append("If you cannot complete an item, output 'BLOCKED: <reason>' — do NOT silently skip.")
    lines.append("─" * 60)
    return "\n".join(lines)


def build_prompt(task: dict) -> str:
    direction = task.get("direction", "")
    task_type = task.get("task_type", "unknown")
    context = task.get("context", {}) or {}
    agent = context.get("task_agent", "dev-engineer")

    # Task-type-specific instructions
    if task_type == "review":
        ctx = task.get("context", {}) or {}
        pr_number = ctx.get("pr_number", "")
        pr_instruction = ""
        if pr_number:
            pr_instruction = f"""
- Read the PR diff: gh pr diff {pr_number}
- Post your review on the PR: gh pr review {pr_number} --approve --body '<review summary>'
  OR: gh pr review {pr_number} --request-changes --body '<issues found>'"""
        type_instructions = f"""
REVIEW INSTRUCTIONS:
- Read the implementation files and evaluate for correctness, completeness, and quality.
- Check: Does the implementation match the spec? Are edge cases handled? Is the code clean?
- You CAN use tools to read files, run `gh pr diff`, and post reviews.{pr_instruction}
- Output REVIEW_PASSED or REVIEW_FAILED with specific issues.
- Minimum 300 chars of substantive review text."""
    elif task_type == "spec":
        type_instructions = """
SPEC INSTRUCTIONS:
- Write a detailed spec file at specs/<idea_id>.md
- Include: Summary, Requirements, API changes, Data model, Verification criteria, Risks
- Minimum 500 chars of spec content.
- For each requirement, name the exact file(s) that will change, e.g.:
    - `api/app/models/idea.py` — add X field
    - `api/app/services/idea_service.py` — add Y function
    - `web/app/ideas/page.tsx` — update Z component
  This file list is read by the impl task — the more precise, the faster impl runs.
- Include a ## Files section listing every file the impl agent should create or modify.

BEFORE FINISHING — you MUST run these commands:
  echo "*.pyc\n__pycache__/\n.task-*\ndata/coherence.db" >> .gitignore
  git add -A
  git diff --cached --stat
  git commit -m "spec(<idea>): <summary>"
Do NOT push or create PRs — the runner handles that."""
    elif task_type == "impl":
        type_instructions = f"""
IMPL INSTRUCTIONS:
- Write actual Python/TypeScript code files in the repository at {_REPO_DIR}
- You MUST create or modify real files, not just describe what you would do.
- If you cannot write files, output the FULL file contents inline (not summaries).
- Minimum 200 chars of real code or detailed inline output.

Where to put code:
- API endpoints: api/app/routers/<name>.py
- Services: api/app/services/<name>.py
- Models: api/app/models/<name>.py
- Web pages: web/app/<route>/page.tsx
- CLI: cli/bin/cc.mjs

BEFORE FINISHING — you MUST run these commands:
  echo "*.pyc\\n__pycache__/\\n.task-*\\ndata/coherence.db\\n.codex*" >> .gitignore
  git add -A
  git diff --cached --stat
  git commit -m "impl(<idea>): <summary>"
Do NOT push or create PRs — the runner handles that.
Do NOT just describe what you would do — WRITE THE FILES."""
    elif task_type == "test":
        type_instructions = f"""
TEST INSTRUCTIONS:
- Write pytest test files in the repository at {_REPO_DIR}
- Place tests in api/tests/ following existing patterns.
- Run tests after writing: cd api && python -m pytest <test_file> -v
- If tests fail, fix them until they pass.

BEFORE FINISHING — you MUST run these commands:
  echo "*.pyc\\n__pycache__/\\n.task-*\\ndata/coherence.db" >> .gitignore
  git add -A
  git diff --cached --stat
  git commit -m "test(<idea>): <summary>"
Do NOT push or create PRs — the runner handles that.
Output: TESTS_FILE=<path>, TESTS_RUN=<count>, TESTS_PASSED=<count>"""
    else:
        type_instructions = f"""
Work in the repository at {_REPO_DIR}. Follow the project's CLAUDE.md conventions.
Output a summary: files created/modified, validation results, errors encountered."""

    idea_id = context.get("idea_id", "unknown") if isinstance(context, dict) else "unknown"
    spec_path = context.get("spec_path", "none") if isinstance(context, dict) else "none"
    workspace_git_url = context.get("workspace_git_url", "") if isinstance(context, dict) else ""

    # Build rich context block — spec content, CLAUDE.md, runbook, related files, module map
    context_block = _build_context_block(
        task_type=task_type,
        idea_id=idea_id,
        spec_path=spec_path,
        direction=direction,
        repo_dir=_REPO_DIR,
    )

    prompt = f"""EXECUTE THIS TASK NOW. Do NOT ask what to do — the task is described below. Start working immediately.

Task type: {task_type}
Task ID: {task.get('id', 'unknown')}
Idea ID: {idea_id}
Spec file: {spec_path}
Workspace: {workspace_git_url or "(coherence-network default repo)"}
Role: {agent} for Coherence Network

SCOPE RULE: Only modify files related to idea '{idea_id}'. Do NOT work on any other idea.

TASK:
{direction}
{type_instructions}{context_block}

CRITICAL: Start executing immediately. Do NOT respond with "I'm ready" or "What should I do?" — the task is above. Do the work, write files, commit, and output results."""
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

    # Instruct agent to heartbeat and checkpoint
    task_id = task.get("id", "unknown")
    prompt += f"""

PROGRESS TRACKING — do these every 3-5 minutes of work:

1. Heartbeat via API (proves you are alive and working):
   curl -s -X POST {API_BASE}/api/agent/tasks/{task_id}/activity \\
     -H "Content-Type: application/json" \\
     -d '{{"event":"agent_heartbeat","data":{{"step":"<what you just did>","files_touched":"<list>","progress_pct":<0-100>}}}}'

2. Write checkpoint to `.task-checkpoint.md`:
   - What you completed so far
   - What remains
   - Any blockers

If the heartbeat curl fails, continue working — it's not critical. The checkpoint file IS critical for resume.

3. Update `.idea-progress.md` (carried across tasks for this idea):
   - This file tracks cumulative progress for the ENTIRE idea across all phases/tasks.
   - Read it first — it may contain work from previous tasks.
   - Update the "Current task" section with what you're doing now.
   - When done, move your work summary to "Completed phases".
   - Record any key decisions or architectural choices in "Key decisions".
   - List unresolved issues in "Blockers".
   - This file is NOT committed to git — it's extracted by the runner after your task."""

    # Build requirements checklist from spec content if available
    spec_content = ""
    if isinstance(context, dict) and context.get("spec_path"):
        sp = context.get("spec_path", "")
        try:
            import pathlib as _pl
            _spec_file = _pl.Path(sp)
            if _spec_file.exists():
                spec_content = _spec_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    checklist_block = _build_requirements_checklist(task_type, direction, spec_content)
    if checklist_block:
        prompt += checklist_block

    return prompt


def _push_and_pr(
    task: dict, task_id: str, task_type: str, provider: str,
    new_changes: set[str], output: str,
) -> str | None:
    """Push changes to a branch and create a PR for impl/test tasks.

    Returns the PR URL on success, None on failure.
    """
    context = task.get("context", {}) or {}
    idea_id = context.get("idea_id", "unknown")
    branch = f"worker/{task_type}/{idea_id}/{task_id[:8]}"

    try:
        cwd = str(_REPO_DIR)

        # Ensure all changes are committed (exclude control files from staging)
        _CONTROL_FILES = {".task-control", ".task-checkpoint.md", ".idea-progress.md", "data/coherence.db"}
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
            timeout=5, cwd=cwd,
        )
        code_files = []
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            # Untracked files show as "?? path" — these are NEW files from impl
            if line.startswith("??"):
                path = line[3:].strip().strip('"')
            else:
                path = line[3:].strip().strip('"').split(" -> ")[-1]
            if path not in _CONTROL_FILES and not any(path.startswith(p) for p in (".codex", "__pycache__", ".tmp", ".task")):
                code_files.append(path)

        if not code_files:
            log.info("PR_SKIP task=%s — no real code files changed (only control files)", task_id)
            # Reset working tree to clean state
            subprocess.run(["git", "checkout", "--", "."], capture_output=True, timeout=5, cwd=cwd)
            return None

        # Stage only code files, commit
        for f in code_files:
            subprocess.run(["git", "add", f], capture_output=True, timeout=5, cwd=cwd)
        subprocess.run(
            ["git", "commit", "-m", f"{task_type}({idea_id}): {task_id[:12]} via {provider}\n\nFiles: {', '.join(code_files[:5])}"],
            capture_output=True, timeout=10, cwd=cwd,
        )

        # Check if there are commits ahead of origin/main
        diff_check = subprocess.run(
            ["git", "log", "origin/main..HEAD", "--oneline"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if not diff_check.stdout.strip():
            log.info("PR_SKIP task=%s — no commits ahead of origin/main", task_id)
            return None

        # Create branch from current state
        subprocess.run(
            ["git", "checkout", "-b", branch], capture_output=True, timeout=5, cwd=cwd,
        )

        # Push
        push_result = subprocess.run(
            ["git", "push", "origin", branch],
            capture_output=True, text=True, timeout=30, cwd=cwd,
            shell=(sys.platform == "win32"),
        )
        if push_result.returncode != 0:
            log.warning("PR_PUSH_FAILED task=%s stderr=%s", task_id, push_result.stderr[:200])
            subprocess.run(["git", "checkout", "worker-main"], capture_output=True, timeout=5, cwd=cwd)
            subprocess.run(["git", "branch", "-D", branch], capture_output=True, timeout=5, cwd=cwd)
            return None

        # Create PR
        idea_name = task.get("direction", "")[:60]
        pr_title = f"{task_type}({idea_id}): {idea_name}"[:70]
        pr_body = (
            f"## Automated {task_type} by {_NODE_NAME} ({provider})\n\n"
            f"**Idea:** {idea_id}\n"
            f"**Task:** {task_id}\n"
            f"**Provider:** {provider}\n"
            f"**Files changed:** {len(new_changes)}\n\n"
            f"---\n{output[:500]}"
        )
        pr_result = subprocess.run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--base", "main"],
            capture_output=True, text=True, timeout=30, cwd=cwd,
            shell=(sys.platform == "win32"),
        )

        # Switch back to worker-main and clean up local branch
        subprocess.run(["git", "checkout", "worker-main"], capture_output=True, timeout=5, cwd=cwd)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True, timeout=5, cwd=cwd)
        # Reset worker-main to origin/main (clean slate for next task)
        subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True, timeout=5, cwd=cwd)

        if pr_result.returncode == 0:
            pr_url = pr_result.stdout.strip()
            return pr_url
        else:
            log.warning("PR_CREATE_FAILED task=%s stderr=%s", task_id, pr_result.stderr[:200])
            return None

    except Exception as exc:
        log.warning("PR_ERROR task=%s error=%s", task_id, exc)
        # Try to get back to clean state
        try:
            subprocess.run(["git", "checkout", "worker-main"], capture_output=True, timeout=5, cwd=str(_REPO_DIR))
            subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True, timeout=5, cwd=str(_REPO_DIR))
        except Exception:
            pass
        return None


def _push_to_existing_branch(
    task: dict, task_id: str, provider: str,
    branch: str, new_changes: set[str], output: str,
) -> str | None:
    """Push test/review changes to an existing impl branch (same PR)."""
    cwd = str(_REPO_DIR)
    try:
        # Checkout the impl branch
        subprocess.run(["git", "fetch", "origin", branch], capture_output=True, timeout=15, cwd=cwd)
        subprocess.run(["git", "checkout", branch], capture_output=True, timeout=5, cwd=cwd)

        # Stage and commit
        for f in new_changes:
            subprocess.run(["git", "add", f], capture_output=True, timeout=5, cwd=cwd)
        subprocess.run(
            ["git", "commit", "-m", f"test({task_id[:12]}): add tests via {provider}"],
            capture_output=True, timeout=10, cwd=cwd,
        )

        # Push to same branch
        push_result = subprocess.run(
            ["git", "push", "origin", branch],
            capture_output=True, text=True, timeout=30, cwd=cwd,
            shell=(sys.platform == "win32"),
        )

        # Switch back to worker-main
        subprocess.run(["git", "checkout", "worker-main"], capture_output=True, timeout=5, cwd=cwd)
        subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True, timeout=5, cwd=cwd)

        if push_result.returncode == 0:
            log.info("PUSH_EXISTING task=%s branch=%s", task_id, branch)
            return branch
        else:
            log.warning("PUSH_EXISTING_FAILED task=%s stderr=%s", task_id, push_result.stderr[:200])
            return None
    except Exception as exc:
        log.warning("PUSH_EXISTING_ERROR task=%s error=%s", task_id, exc)
        try:
            subprocess.run(["git", "checkout", "worker-main"], capture_output=True, timeout=5, cwd=cwd)
            subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True, timeout=5, cwd=cwd)
        except Exception:
            pass
        return None


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
    - simple tasks: 2.5x p90 (min 180s)
    - complex tasks: 4x p90 (min 300s)
    Falls back to the configured default if no p90 data exists.

    The range is 180-900s. Real code writing on strong providers typically
    takes 3-8 minutes. The 300s fixed timeout was causing productive
    providers to time out mid-work.
    """
    level = "simple"
    multiplier = 2.5
    min_timeout = 180
    if isinstance(complexity_estimate, dict):
        raw_level = str(complexity_estimate.get("level") or "").strip().lower()
        if raw_level == "complex":
            multiplier = 4.0
            min_timeout = 300
            level = "complex"

    if HAS_SERVICES:
        try:
            selector = SlotSelector(f"provider_{task_type}")
            stats = selector.stats([provider])
            slot = stats.get("slots", {}).get(provider, {})
            p90_duration = float(slot.get("p90_duration_s", 0) or 0)
            if p90_duration > 10:  # Need meaningful duration data (>10s rules out hollow runs)
                timeout = int(max(min_timeout, min(900, p90_duration * multiplier)))
                log.info(
                    "TIMEOUT_DATA provider=%s task=%s complexity=%s timeout=%ds (%.1fx p90=%.0fs)",
                    provider, task_type, level, timeout, multiplier, p90_duration,
                )
                return timeout
        except Exception:
            pass

    # No data yet — use generous defaults by task type
    # impl/test need more time (writing code), spec/review need less (writing text)
    defaults = {"impl": 600, "test": 600, "spec": 480, "review": 360, "code-review": 360}
    fallback = defaults.get(task_type, _TASK_TIMEOUT[0])
    if level == "complex":
        fallback = min(900, int(fallback * 1.5))
    return fallback


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

    # All providers use their default invocation with full tool access.
    # No special-casing per task type — the prompt guides behavior, not the CLI flags.
    # Codex: `codex exec --full-auto` for everything (full tool access)
    # Cursor: `agent --model <model>` (positional arg, full tool access)

    # Cursor: uses default config `agent --model auto --trust -p` (set in _detect_providers)
    # --trust skips workspace trust dialog, -p is non-interactive, --model auto lets cursor pick

    # Write prompt to file for debugging, deliver via stdin for all providers
    # stdin avoids shell arg length limits and is more reliable than CLI args
    _task_id = getattr(execute_with_provider, "_current_task_id", "unknown")
    prompt_file = os.path.join(str(_REPO_DIR), f".task-prompt-{_task_id[:12]}.md")
    try:
        with open(prompt_file, "w", encoding="utf-8") as pf:
            pf.write(prompt)
        log.info("PROMPT_FILE written: %s (%d chars)", prompt_file, len(prompt))
    except OSError as e:
        log.warning("Could not write prompt file: %s", e)

    # Prompt delivery: stdin for most, CLI arg for gemini (doesn't read stdin)
    _STDIN_PROVIDERS = {"claude", "codex", "cursor", "ollama-local", "ollama-cloud"}
    _CLI_ARG_PROVIDERS = {"gemini"}  # gemini -y -p <prompt> — must be positional arg

    if spec.get("stdin_prompt") or provider in _STDIN_PROVIDERS:
        stdin_input = prompt
    elif spec.get("append_prompt") or provider in _CLI_ARG_PROVIDERS:
        cmd.append(prompt)

    # ── Start heartbeat monitoring (works for both wrapper and raw subprocess) ──
    start = time.time()
    _current_task_id = getattr(execute_with_provider, "_current_task_id", "")
    _heartbeat_stop = threading.Event()
    # CC_DIAG_LEVEL: normal (10s, file list) | high (5s, file list + diff stats + process info)
    _diag_level = rc("diagnostics", "level", "normal")
    _HEARTBEAT_INTERVAL = 5 if _diag_level == "high" else 10

    def _heartbeat_loop(task_id: str, cwd: str, prov: str, ttype: str):
        last_status = ""
        while not _heartbeat_stop.is_set():
            _heartbeat_stop.wait(_HEARTBEAT_INTERVAL)
            if _heartbeat_stop.is_set():
                break
            elapsed = int(time.time() - start)
            git_status = ""
            files_changed = 0
            try:
                gs = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, timeout=5, cwd=cwd,
                )
                git_status = gs.stdout.strip()
                files_changed = len([l for l in git_status.splitlines() if l.strip()])
            except Exception:
                pass
            status_changed = git_status != last_status
            is_heartbeat = (elapsed % 30) < _HEARTBEAT_INTERVAL
            if status_changed or is_heartbeat:
                new_files = [l[3:].strip() for l in git_status.splitlines() if l.startswith("??")]
                modified_files = [l[3:].strip() for l in git_status.splitlines() if l.startswith(" M") or l.startswith("M ")]
                summary = ""
                if new_files:
                    summary += f"new: {', '.join(f.split('/')[-1] for f in new_files[:3])}"
                    if len(new_files) > 3:
                        summary += f" +{len(new_files)-3}"
                if modified_files:
                    if summary:
                        summary += " | "
                    summary += f"modified: {', '.join(f.split('/')[-1] for f in modified_files[:3])}"
                    if len(modified_files) > 3:
                        summary += f" +{len(modified_files)-3}"

                event_data = {
                    "provider": prov, "task_type": ttype, "elapsed_s": elapsed,
                    "files_changed": files_changed, "git_summary": summary or "no changes yet",
                    "new_files": len(new_files), "modified_files": len(modified_files),
                    "diag_level": _diag_level,
                }

                # High diag: add diff line count + process tree info
                if _diag_level == "high" and files_changed > 0:
                    try:
                        ds = subprocess.run(
                            ["git", "diff", "--stat"],
                            capture_output=True, text=True, timeout=5, cwd=cwd,
                        )
                        event_data["diff_stat"] = ds.stdout.strip()[-200:]
                    except Exception:
                        pass

                _post_activity(task_id, "heartbeat", event_data)

                # External heartbeat hook (runner-owned, not provider-owned)
                # CC_HEARTBEAT_URL: POST JSON to this URL on every heartbeat
                # CC_HEARTBEAT_CMD: shell command to run on every heartbeat (escape hatch)
                hb_url = rc("heartbeat", "url", "") or ""
                hb_cmd = rc("heartbeat", "cmd", "") or ""
                hb_payload = {
                    "node_id": _NODE_ID, "node_name": _NODE_NAME,
                    "task_id": task_id, "task_type": ttype, "provider": prov,
                    "elapsed_s": elapsed, "files_changed": files_changed,
                    "git_summary": summary or "no changes",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                if hb_url:
                    try:
                        import httpx
                        httpx.post(hb_url, json=hb_payload, timeout=5.0)
                    except Exception as he:
                        log.debug("HEARTBEAT_HOOK_HTTP failed: %s", he)
                if hb_cmd:
                    try:
                        env = dict(os.environ)
                        env.update({
                            "CC_TASK_ID": task_id, "CC_TASK_TYPE": ttype,
                            "CC_PROVIDER": prov, "CC_ELAPSED": str(elapsed),
                            "CC_FILES_CHANGED": str(files_changed),
                            "CC_GIT_SUMMARY": summary or "no changes",
                        })
                        subprocess.run(hb_cmd, shell=True, timeout=10, capture_output=True, env=env)
                    except Exception as he:
                        log.debug("HEARTBEAT_HOOK_CMD failed: %s", he)

                last_status = git_status

    heartbeat_thread = None
    if _current_task_id:
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(_current_task_id, str(_REPO_DIR), provider, task_type),
            daemon=True,
        )
        heartbeat_thread.start()

    # Use ProviderWrapper for process-level control (checkpoint, steer, abort)
    control_dir = Path(rc("execution", "work_dir") or str(_REPO_DIR))
    try:
        from provider_wrapper import ProviderWrapper
        wrapper = ProviderWrapper(
            cmd=cmd,
            cwd=str(_REPO_DIR),
            timeout=timeout,
            control_dir=control_dir,
            stdin_input=stdin_input,
        )
        log.info("WRAPPER executing %s (timeout=%ds)", provider, timeout)
        result = wrapper.run()
        _heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        # Post completion
        if _current_task_id:
            _post_activity(_current_task_id, "provider_done", {
                "provider": provider, "task_type": task_type,
                "duration_s": round(time.time() - start, 1),
                "output_chars": len(result[1]) if len(result) > 1 else 0,
                "success": result[0] if result else False,
            })
        return result
    except ImportError:
        pass  # wrapper not available — fall back to raw subprocess
    except Exception as e:
        log.warning("WRAPPER failed (falling back to raw subprocess): %s", e)

    # Fallback: raw subprocess with live progress reporting
    start = time.time()
    # task_id for progress reporting (set by caller context)
    _current_task_id = getattr(execute_with_provider, "_current_task_id", "")

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    # On Windows, .CMD/.BAT wrappers (npm-installed CLIs) need shell=True
    use_shell = sys.platform == "win32" and cmd and str(cmd[0]).lower().endswith((".cmd", ".bat"))

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdin_input else None,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(_REPO_DIR), creationflags=creation_flags,
            shell=use_shell,
            start_new_session=True,  # Own process group so killpg doesn't kill the runner
        )

        # Stream stdout line-by-line for live progress
        lines: list[str] = []
        last_progress_time = time.time()
        _PROGRESS_INTERVAL = 15  # Post progress every 15 seconds

        if stdin_input and proc.stdin:
            proc.stdin.write(stdin_input)
            proc.stdin.close()

        try:
            while True:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line and proc.poll() is not None:
                    break
                if line:
                    lines.append(line)
                    # Post progress at intervals
                    now = time.time()
                    if _current_task_id and (now - last_progress_time) >= _PROGRESS_INTERVAL:
                        elapsed = int(now - start)
                        preview = (lines[-1] if lines else "").strip()[:120]
                        _post_activity(_current_task_id, "progress", {
                            "provider": provider,
                            "task_type": task_type,
                            "elapsed_s": elapsed,
                            "lines": len(lines),
                            "preview": preview,
                        })
                        last_progress_time = now

                # Check timeout
                if (time.time() - start) > timeout:
                    raise subprocess.TimeoutExpired(cmd, timeout)

            # Collect any remaining stderr
            stderr_out = proc.stderr.read() if proc.stderr else ""
            duration = time.time() - start
            stdout_text = "".join(lines)
            output = stdout_text or stderr_out or "(no output)"

            # Post final progress
            if _current_task_id:
                _post_activity(_current_task_id, "provider_done", {
                    "provider": provider,
                    "task_type": task_type,
                    "duration_s": round(duration, 1),
                    "lines": len(lines),
                    "output_chars": len(output),
                    "success": proc.returncode == 0,
                })

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


def _run_operational_phase(task: dict, task_id: str, task_type: str) -> bool:
    """Run merge/deploy/verify/reflect directly — these are commands, not AI tasks."""
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = context.get("idea_id", "unknown")
    cwd = str(_REPO_DIR)
    start = time.time()
    log.info("OPERATIONAL task=%s type=%s idea=%s", task_id, task_type, idea_id)
    try:
        if task_type == "merge":
            pr_result = subprocess.run(
                ["gh", "pr", "list", "--search", idea_id, "--json", "number,title", "--limit", "1"],
                capture_output=True, text=True, timeout=15, cwd=cwd, shell=(sys.platform == "win32"),
            )
            prs = json.loads(pr_result.stdout) if pr_result.returncode == 0 else []
            if prs:
                pr_num = prs[0]["number"]
                merge_result = subprocess.run(
                    ["gh", "pr", "merge", str(pr_num), "--squash", "--admin"],
                    capture_output=True, text=True, timeout=30, cwd=cwd, shell=(sys.platform == "win32"),
                )
                output = (f"MERGE_PASSED: PR #{pr_num} merged." if merge_result.returncode == 0
                          else f"MERGE_FAILED: {merge_result.stderr.strip()[:200]}")
            else:
                output = f"MERGE_PASSED: No open PR for {idea_id} — code already on main."
        elif task_type == "deploy":
            ssh_key = os.path.expanduser("~/.ssh/hostinger-openclaw")
            if os.path.exists(ssh_key):
                deploy_result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", "-i", ssh_key, "root@187.77.152.42",
                     "cd /docker/coherence-network/repo && git pull origin main && cd /docker/coherence-network && docker compose build --no-cache api web && docker compose up -d api web"],
                    capture_output=True, text=True, timeout=300, cwd=cwd,
                )
                output = (f"DEPLOY_PASSED: VPS updated." if deploy_result.returncode == 0
                          else f"DEPLOY_FAILED: {deploy_result.stderr[-200:]}")
            else:
                output = "DEPLOY_SKIPPED: No SSH key for VPS."
        elif task_type == "verify":
            import httpx as _httpx
            results = []
            with _httpx.Client(timeout=10) as client:
                for ep in ["/api/health", "/api/ideas/count", "/api/coherence"]:
                    try:
                        r = client.get(f"https://api.coherencycoin.com{ep}")
                        results.append(f"{ep}:{r.status_code}")
                    except Exception as e:
                        results.append(f"{ep}:FAIL({e})")
                try:
                    r = client.get("https://coherencycoin.com/", follow_redirects=True)
                    results.append(f"web:{r.status_code}")
                except Exception as e:
                    results.append(f"web:FAIL({e})")
            all_ok = all("200" in r for r in results)
            output = ("VERIFY_PASSED: " if all_ok else "VERIFY_FAILED: ") + " | ".join(results)
        elif task_type == "reflect":
            # Count tasks to estimate actual cost (0.5 CC per task = rough provider call cost)
            idea_tasks_r = api("GET", f"/api/ideas/{idea_id}/tasks")
            task_count = 0
            if isinstance(idea_tasks_r, dict):
                task_count = idea_tasks_r.get("total", 0)
            actual_cost_estimate = round(task_count * 0.5, 1)
            # Mark idea as validated and record cost actuals
            patch_body: dict[str, Any] = {
                "manifestation_status": "validated",
                "actual_cost": max(actual_cost_estimate, 0.5),
            }
            patch_result = api("PATCH", f"/api/ideas/{idea_id}", patch_body)
            patched = isinstance(patch_result, dict)

            # Spawn follow-up ideas from unanswered open_questions
            spawned_ids: list[str] = []
            try:
                idea_payload_r = api("GET", f"/api/ideas/{idea_id}")
                if isinstance(idea_payload_r, dict):
                    open_qs = idea_payload_r.get("open_questions") or []
                    idea_name_r = str(idea_payload_r.get("name") or idea_id)
                    idea_desc_r = str(idea_payload_r.get("description") or "")[:300]
                    for q in open_qs:
                        if not isinstance(q, dict):
                            continue
                        if q.get("answer") is not None:
                            continue  # already answered — skip
                        q_text = str(q.get("question") or "").strip()
                        if not q_text:
                            continue
                        # Build a slug for the follow-up idea id
                        import re as _re
                        slug = _re.sub(r"[^a-z0-9]+", "-", q_text[:40].lower()).strip("-")
                        followup_id = f"{idea_id}-followup-{slug}"[:80]
                        followup_body: dict[str, Any] = {
                            "id": followup_id,
                            "name": f"Follow-up: {q_text[:80]}",
                            "description": (
                                f"This idea emerged from the completed implementation of "
                                f"'{idea_name_r}' ({idea_id}).\n\n"
                                f"Open question that was not resolved during implementation: "
                                f"{q_text}\n\n"
                                f"Original idea context: {idea_desc_r}"
                            ),
                            "potential_value": float(q.get("value_to_whole") or 20.0),
                            "estimated_cost": float(q.get("estimated_cost") or 3.0),
                            "confidence": 0.55,
                            "parent_idea_id": idea_id,
                            "idea_type": "child",
                            "work_type": "exploration",
                        }
                        created_q = api("POST", "/api/ideas", followup_body)
                        if isinstance(created_q, dict) and created_q.get("id"):
                            spawned_ids.append(followup_id)
                            log.info(
                                "REFLECT_SPAWN idea=%s spawned follow-up=%s from unanswered question",
                                idea_id, followup_id,
                            )
                        else:
                            log.debug("REFLECT_SPAWN_SKIP followup_id=%s (likely already exists)", followup_id)
            except Exception as _spawn_exc:
                log.warning("REFLECT_SPAWN_ERROR idea=%s error=%s", idea_id, _spawn_exc)

            _append_idea_event(idea_id, "reflected", {
                "task_count": task_count,
                "actual_cost": max(actual_cost_estimate, 0.5),
                "manifestation_status": "validated",
                "spawned_idea_ids": spawned_ids,
            })



            spawn_note = (
                f" Spawned {len(spawned_ids)} follow-up idea(s): {', '.join(spawned_ids)}."
                if spawned_ids else ""
            )
            output = (
                f"REFLECT_COMPLETE: {idea_id} lifecycle validated. "
                f"Tasks run: {task_count}, estimated actual cost: {actual_cost_estimate} CC. "
                f"Idea PATCH {'succeeded' if patched else 'failed — check API logs'}."
                f"{spawn_note}"
            )
        else:
            output = f"Unknown phase: {task_type}"

        duration = time.time() - start
        success = "PASSED" in output or "COMPLETE" in output
        log.info("OPERATIONAL_DONE task=%s type=%s success=%s dur=%.1fs output=%s",
                 task_id, task_type, success, duration, output[:100])
        complete_task(task_id, output, success, {"provider": "runner-direct", "duration_s": round(duration, 1)})
        if success:
            _run_phase_auto_advance_hook(task)
        return success
    except Exception as exc:
        duration = time.time() - start
        log.error("OPERATIONAL_ERROR task=%s type=%s error=%s", task_id, task_type, exc)
        complete_task(task_id, f"{task_type.upper()}_FAILED: {exc}", False,
                      {"provider": "runner-direct", "duration_s": round(duration, 1)})
        return False


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

    # Operational phases run directly — no AI provider needed
    if task_type in ("merge", "deploy", "verify", "reflect") and not dry_run:
        return _run_operational_phase(task, task_id, task_type)

    # Select provider (data-driven)
    provider = select_provider(task_type, task=task)

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

    # Attach control channel (SSE-based real-time steer/checkpoint/abort)
    control_channel = None
    task_work_dir = _REPO_DIR  # default; worktree overrides this
    try:
        from task_control_channel import TaskControlChannel, inject_control_instructions
        task_work_dir = Path(rc("execution", "work_dir") or str(_REPO_DIR))
        control_channel = TaskControlChannel(
            node_id=_NODE_ID,
            task_id=task_id,
            task_dir=task_work_dir,
            api_base=rc("api", "base_url", "https://api.coherencycoin.com"),
        )
        control_channel.start()
        prompt = inject_control_instructions(prompt, task_work_dir)
    except ImportError:
        pass  # control channel module not available — run without it
    except Exception as e:
        log.warning("CONTROL_CHANNEL setup failed (non-fatal): %s", e)

    # Snapshot repo state before execution (to detect actual file changes)
    pre_status_lines = _git_status_lines()
    pre_patch = _git_diff_for_paths()

    log.info("EXECUTING task=%s type=%s provider=%s", task_id, task_type, provider)
    _post_activity(task_id, "executing", {"provider": provider, "task_type": task_type})

    # Pass task_id to execute_with_provider for live progress reporting
    execute_with_provider._current_task_id = task_id
    success, output, duration = execute_with_provider(provider, prompt, task_type, complexity_estimate)
    execute_with_provider._current_task_id = ""

    # Stop control channel
    if control_channel:
        try:
            control_channel.stop()
        except Exception:
            pass

    # Post-execution validation: did file-producing tasks actually produce files?
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    has_code_changes = False
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
                # Filter out control/checkpoint files — only count real code
                code_changes = {c for c in new_changes if not any(
                    skip in _status_line_path(c) for skip in (
                        ".task-control", ".task-checkpoint", ".codex", ".tmp", "__pycache__",
                    )
                )}
                if code_changes:
                    has_code_changes = True
                    log.info("VERIFIED task=%s code_files=%d total_files=%d", task_id, len(code_changes), len(new_changes))

                    # DIF auto-verify: run DIF on each changed code file
                    dif_results = []
                    for changed_file in sorted(code_changes):
                        fpath = _status_line_path(changed_file)
                        # Detect language from extension
                        ext_to_lang = {
                            ".py": "python", ".js": "javascript", ".mjs": "javascript",
                            ".ts": "typescript", ".tsx": "typescript",
                            ".cpp": "cpp", ".c": "c", ".h": "cpp",
                            ".rs": "rust", ".go": "go", ".java": "java",
                        }
                        ext = os.path.splitext(fpath)[1].lower()
                        lang = ext_to_lang.get(ext)
                        if not lang:
                            continue
                        full_path = os.path.join(str(_REPO_DIR), fpath)
                        if not os.path.isfile(full_path):
                            continue
                        try:
                            code_content = open(full_path, "r", encoding="utf-8", errors="replace").read()
                            if len(code_content) < 20 or len(code_content) > 50000:
                                continue  # Skip trivial or huge files
                            import httpx
                            dif_resp = httpx.post(
                                "https://dif.merly.ai/api/v2/dif/verify",
                                json={"language": lang, "code": code_content},
                                timeout=30.0,
                            )
                            if dif_resp.status_code == 200:
                                dif_data = dif_resp.json()
                                dif_result = {
                                    "file": fpath,
                                    "language": lang,
                                    "event_id": dif_data.get("eventId", ""),
                                    "trust_signal": dif_data.get("trust_signal", "?"),
                                    "verification": dif_data.get("scores", {}).get("verification"),
                                    "semantic_support": dif_data.get("scores", {}).get("semantic_support"),
                                    "anomalies": dif_data.get("counts", {}).get("anomalies", 0),
                                    "blocks": dif_data.get("block_model", {}).get("blocks_analyzed", 0),
                                    "latency_ms": dif_data.get("latency_ms"),
                                }
                                dif_results.append(dif_result)
                                log.info(
                                    "DIF_VERIFY task=%s file=%s trust=%s verification=%s anomalies=%s event=%s",
                                    task_id[:12], fpath, dif_result["trust_signal"],
                                    dif_result["verification"], dif_result["anomalies"],
                                    dif_result["event_id"][:12] if dif_result["event_id"] else "?",
                                )
                                # Record DIF feedback to API
                                try:
                                    api("POST", "/api/dif/record", {
                                        "event_id": dif_result["event_id"],
                                        "task_id": task_id,
                                        "language": lang,
                                        "trust_signal": dif_result["trust_signal"],
                                        "verification_score": dif_result["verification"],
                                        "semantic_support": dif_result["semantic_support"],
                                        "anomaly_count": dif_result["anomalies"],
                                        "provider": provider,
                                        "idea_id": context.get("idea_id", ""),
                                        "file_path": fpath,
                                    })
                                except Exception:
                                    pass  # best-effort recording
                        except Exception as e:
                            log.debug("DIF_VERIFY_FAILED file=%s error=%s", fpath, e)
                    if dif_results:
                        output += f"\n\nDIF_RESULTS: {len(dif_results)} files verified"
                        for dr in dif_results:
                            output += f"\n  {dr['file']}: trust={dr['trust_signal']} verification={dr['verification']} anomalies={dr['anomalies']} event={dr['event_id'][:16]}"

                    # Runner stages and commits — don't rely on provider to do it
                    cwd = str(_REPO_DIR)
                    subprocess.run(["git", "add", "-A"], capture_output=True, timeout=10, cwd=cwd)
                    idea_id = context.get("idea_id", "unknown")
                    subprocess.run(
                        ["git", "commit", "-m", f"{task_type}({idea_id}): {task_id[:12]} via {provider}"],
                        capture_output=True, timeout=10, cwd=cwd,
                    )
                    log.info("RUNNER_COMMITTED task=%s type=%s files=%d", task_id, task_type, len(code_changes))

                    # Push changes and create PR for impl/test tasks
                    if task_type == "impl":
                        pr_url = _push_and_pr(task, task_id, task_type, provider, code_changes, output)
                        if pr_url:
                            # Extract PR number and branch for downstream phases
                            pr_number = pr_url.rstrip("/").split("/")[-1] if pr_url else ""
                            impl_branch = f"worker/{task_type}/{context.get('idea_id', 'unknown')}/{task_id[:8]}"
                            output += f"\n\nPR: {pr_url}\nPR_NUMBER: {pr_number}\nIMPL_BRANCH: {impl_branch}"
                            log.info("PR_CREATED task=%s url=%s pr=%s branch=%s files=%d",
                                     task_id, pr_url, pr_number, impl_branch, len(code_changes))
                    elif task_type == "test":
                        # Test pushes to the IMPL branch, not a new PR
                        impl_branch = context.get("impl_branch", "")
                        if impl_branch:
                            pr_url = _push_to_existing_branch(task, task_id, provider, impl_branch, code_changes, output)
                            if pr_url:
                                output += f"\n\nPushed to existing PR branch: {impl_branch}"
                                log.info("TEST_PUSHED task=%s branch=%s files=%d", task_id, impl_branch, len(code_changes))
                        else:
                            log.warning("TEST_NO_BRANCH task=%s — no impl_branch in context, creating standalone PR", task_id)
                            pr_url = _push_and_pr(task, task_id, task_type, provider, code_changes, output)
                            if pr_url:
                                output += f"\n\nPR: {pr_url}"
                else:
                    # Only control files changed — hollow impl
                    log.warning(
                        "HOLLOW_IMPL task=%s — only control files changed (%d), no real code. "
                        "Provider did not write implementation files.",
                        task_id, len(new_changes),
                    )
                    success = False
                    output = (
                        f"Hollow impl: {len(new_changes)} files changed but all are control/checkpoint files. "
                        f"No actual code written. Provider needs tool access to write files.\n---\n{output}"
                    )
        except Exception as exc:
            log.warning("VALIDATION_ERROR task=%s error=%s", task_id, exc)

    # Save task log
    task_log = _LOG_DIR / f"task_{task_id}.log"
    spec_info = PROVIDERS.get(provider, {})
    cmd_line = " ".join(str(c) for c in spec_info.get("cmd", []))
    model_info = spec_info.get("_selected_model", "default")
    task_log.write_text(
        f"=== Task {task_id} | Provider: {provider} | Type: {task_type} ===\n"
        f"Time: {datetime.now(timezone.utc).isoformat()}\n"
        f"Duration: {duration:.1f}s | Success: {success}\n"
        f"Model: {model_info}\n"
        f"Cmd: {cmd_line}\n"
        f"Timeout: {get_timeout_for(provider, task_type, complexity_estimate)}s\n"
        f"Complexity: {json.dumps(complexity_estimate) if complexity_estimate else 'none'}\n"
        f"Node: {_NODE_NAME} ({_NODE_ID[:8]})\n"
        f"=== OUTPUT ===\n{output}\n"
    )

    # Record outcome for Thompson Sampling (with error classification)
    record_provider_outcome(task_type, provider, success, duration, output)

    # ── Quality gate: phase-specific minimum output length ──
    _MIN_OUTPUT_BY_PHASE = {
        "spec": 200,    # A real spec has goals, files, acceptance criteria
        "impl": 200,    # A real impl describes files changed + evidence
        "test": 150,    # A real test shows test file + results
        "review": 80,   # A review at minimum says PASSED/FAILED with reasons
        "code-review": 80,
    }
    min_chars = _MIN_OUTPUT_BY_PHASE.get(task_type, 50)
    output_stripped = (output or "").strip()
    # If a PR was created, or real code file changes were detected, the provider did real work —
    # don't penalize for terse text output
    has_pr = "PR:" in output or "PR_CREATED" in output or "pull/" in output
    if success and len(output_stripped) < min_chars and not has_pr and not has_code_changes:
        log.warning(
            "QUALITY_GATE task=%s provider=%s type=%s — output too short (%d chars < %d min for %s). "
            "Marking as failed, not completed.",
            task_id, provider, task_type, len(output_stripped), min_chars, task_type,
        )
        success = False
    elif success and len(output_stripped) < min_chars and has_pr:
        log.info(
            "QUALITY_GATE task=%s — output short (%d chars) but PR exists, accepting",
            task_id, len(output_stripped),
        )

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
        if len(output_stripped) >= min_chars:
            # Fix 4: impl/test phase advance is deferred to _worker_loop (after push confirmation).
            # _worker_loop calls _run_phase_auto_advance_hook only after _push_branch_to_origin
            # returns True, preventing phantom phase advance when the push subsequently fails.
            if task_type not in ("impl", "test"):
                _run_phase_auto_advance_hook(task)
            _auto_record_contribution(task, provider, duration)
        else:
            log.warning("SKIP_ADVANCE task=%s — output too short (%d < %d) for phase advancement", task_id, len(output_stripped), min_chars)

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


_MAX_RETRIES_PER_IDEA_PHASE = 2


def _reap_stale_tasks(max_age_minutes: int = 15) -> int:
    """Smart reap: diagnose why tasks are stuck, capture partial work, resume from checkpoint.

    Spec 169 — replaces blind timed_out with diagnostic-first reaping:
    1. Query runner registry to check liveness before reaping
    2. Extend timeout for live runners (up to 2 times)
    3. Capture partial output from on-disk log if runner crashed
    4. Write structured reap_diagnosis into task context
    5. Create resume task when partial output >= 20%
    6. Track per-idea timeout count; flag needs_human_attention after 3 failures
    """
    import sys as _sys
    # Import smart_reap_service from the API package
    _api_dir = str(_API_DIR)
    if _api_dir not in _sys.path:
        _sys.path.insert(0, _api_dir)
    try:
        from app.services.smart_reap_service import smart_reap_task
    except ImportError as _e:
        log.warning("REAPER: could not import smart_reap_service (%s) — falling back to legacy reap", _e)
        return _legacy_reap_stale_tasks(max_age_minutes)

    tasks_data = api("GET", "/api/agent/tasks?status=running&limit=100")
    if not tasks_data:
        return 0
    task_list = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])

    # Filter to tasks that have exceeded the age threshold
    now = datetime.now(timezone.utc)
    stale_tasks = []
    for t in task_list:
        created = t.get("created_at", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                from datetime import timezone as _tz
                dt = dt.replace(tzinfo=_tz.utc)
            age_min = (now - dt).total_seconds() / 60
        except Exception:
            continue
        if age_min > max_age_minutes:
            stale_tasks.append(t)

    if not stale_tasks:
        return 0

    # Fetch runner registry for liveness checks
    runners: list[dict] = []
    try:
        runners_data = api("GET", "/api/agent/runners?limit=100")
        if runners_data:
            if isinstance(runners_data, list):
                runners = runners_data
            elif isinstance(runners_data, dict):
                runners = runners_data.get("runners", []) or runners_data.get("items", [])
    except Exception as _re:
        log.warning("REAPER: could not fetch runners for liveness check: %s", _re)

    # Fetch recent timed_out tasks for per-idea history (R6)
    timed_out_tasks: list[dict] = []
    try:
        to_data = api("GET", "/api/agent/tasks?status=timed_out&limit=200")
        if to_data:
            timed_out_tasks = to_data if isinstance(to_data, list) else to_data.get("tasks", [])
    except Exception:
        pass

    reaped = 0
    for t in stale_tasks:
        result = smart_reap_task(
            t,
            runners=runners,
            timed_out_tasks=timed_out_tasks,
            log_dir=_LOG_DIR / "tasks",
            max_age_minutes=max_age_minutes,
            api_fn=api,
            send_alert_fn=None,  # Telegram integration via existing runner alert path
        )
        action = result.get("action")
        if action == "reaped":
            reaped += 1
            # Also capture worktree checkpoint + progress sheet if available
            task_id = t.get("id", "")
            slug = task_id[:16]
            ctx = t.get("context", {}) or {}
            reap_idea_id = ctx.get("idea_id", "")
            wt_path = _WORKTREE_BASE / f"task-{slug}"
            if wt_path.exists():
                checkpoint_file = wt_path / ".task-checkpoint.md"
                if checkpoint_file.exists():
                    try:
                        cp = checkpoint_file.read_text(errors="replace")[:2000]
                        log.info("REAPER: captured checkpoint for %s (%d chars)", slug, len(cp))
                    except Exception:
                        pass
                # Persist progress sheet before worktree is cleaned up
                if reap_idea_id:
                    _persist_idea_progress(reap_idea_id, wt_path)
                try:
                    diff_result = subprocess.run(
                        ["git", "diff", "HEAD"],
                        capture_output=True, text=True, timeout=10, cwd=str(wt_path),
                    )
                    if diff_result.stdout.strip():
                        patch_dir = _REPO_DIR / "api" / "task_patches"
                        patch_dir.mkdir(parents=True, exist_ok=True)
                        patch_file = patch_dir / f"task_{task_id}.patch"
                        patch_file.write_text(diff_result.stdout)
                        log.info("REAPER: saved %d-byte patch for %s", len(diff_result.stdout), slug)
                except Exception:
                    pass

    if reaped:
        log.info("REAPER: smart-reaped %d stale tasks", reaped)
    return reaped


def _legacy_reap_stale_tasks(max_age_minutes: int = 15) -> int:
    """Fallback reaper used only if smart_reap_service fails to import."""
    tasks_data = api("GET", "/api/agent/tasks?status=running&limit=100")
    if not tasks_data:
        return 0

    task_list = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
    now = datetime.now(timezone.utc)
    reaped = 0

    for t in task_list:
        created = t.get("created_at", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_min = (now - dt).total_seconds() / 60
        except Exception:
            continue

        if age_min <= max_age_minutes:
            continue

        task_id = t.get("id", "")
        task_type = t.get("task_type", "spec")
        ctx = t.get("context", {}) or {}
        idea_id = ctx.get("idea_id", "")
        idea_name = ctx.get("idea_name", idea_id or task_id[:20])
        failed_provider = ctx.get("provider", "unknown")
        retry_count = int(ctx.get("retry_count", 0))

        diagnosis = f"Stuck running for {int(age_min)}m (threshold {max_age_minutes}m)"
        result = api("PATCH", f"/api/agent/tasks/{task_id}", {
            "status": "timed_out",
            "output": f"Reaped: {diagnosis}",
            "error_summary": diagnosis[:500],
            "error_category": "stale_task_reaped",
        })
        if not result:
            continue

        log.info("REAPER(legacy): timed out %s (%s, %dm, provider=%s, retries=%d) — %s",
                 task_id[:16], task_type, int(age_min), failed_provider, retry_count, idea_name[:40])
        reaped += 1

        if idea_id and retry_count < _MAX_RETRIES_PER_IDEA_PHASE:
            direction = t.get("direction", ctx.get("direction", ""))
            if not direction:
                direction = f"Retry: {task_type} for {idea_name}. Previous attempt timed out after {int(age_min)}m."
            retry_ctx = dict(ctx)
            retry_ctx["retry_count"] = retry_count + 1
            retry_ctx["retried_from"] = task_id
            retry_ctx["failed_provider"] = failed_provider
            retry_ctx["seed_source"] = "reaper_retry"
            retry_result = api("POST", "/api/agent/tasks", {
                "direction": direction,
                "task_type": task_type,
                "context": retry_ctx,
                "target_state": t.get("target_state", f"{task_type.title()} completed for: {idea_name}"),
            })
            if retry_result and retry_result.get("id"):
                log.info("REAPER(legacy): retried %s → %s (attempt %d/%d)",
                         task_id[:16], retry_result["id"][:16], retry_count + 1, _MAX_RETRIES_PER_IDEA_PHASE)
        elif idea_id:
            api("POST", "/api/friction/events", {
                "stage": task_type,
                "block_type": "repeated_timeout",
                "severity": "high",
                "owner": "reaper",
                "notes": f"Task for '{idea_name}' timed out {retry_count + 1} times. Last provider: {failed_provider}.",
            })

    if reaped:
        log.info("REAPER(legacy): cleaned %d stale tasks", reaped)
    return reaped


# Session-level skip cache: ideas we already marked stuck/partial this session.
# Prevents thrashing the API every 15s on the same stuck ideas.
_SEEDER_SKIP_CACHE: set[str] = set()


def _seed_task_from_open_idea() -> bool:
    """Generate a task from an open idea when the queue is empty.

    Smart seeding:
    1. Skip ideas that already have pending/running tasks
    2. Skip validated ideas
    3. Skip ideas already marked stuck this session (local cache)
    4. Weighted random selection (not always highest FE) for diversity
    5. Check existing task history to determine correct next phase
    6. Always link idea_id for phase advancement
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

    # Filter: open ideas without active tasks, not already skipped this session
    candidates = [
        i for i in ideas
        if i.get("manifestation_status") in ("none", "partial", None)
        and i.get("idea_type") != "super"   # SUPER ideas are strategic goals — never picked up
        and i.get("lifecycle", "active") not in ("archived", "retired")
        and i.get("id", "") not in active_idea_ids
        and i.get("id", "") not in _SEEDER_SKIP_CACHE
    ]
    if not candidates:
        skipped = len(_SEEDER_SKIP_CACHE)
        log.info("SEED: no eligible ideas (all validated, active, or skipped=%d this session)", skipped)
        return False

    # Weighted random selection from top 10 by free-energy (diversity)
    candidates.sort(key=lambda i: float(i.get("free_energy_score", 0) or 0), reverse=True)
    top = candidates[:10]
    weights = [max(float(i.get("free_energy_score", 0) or 0), 0.1) for i in top]
    idea = _random.choices(top, weights=weights, k=1)[0]
    idea_id = idea.get("id", "unknown")
    idea_name = idea.get("name", idea_id)

    # Before spending compute, check if this idea is already implemented on main
    # by searching for merged PRs or commits mentioning the idea_id
    already_done = _check_existing_evidence(idea_id)
    if already_done:
        pr_num, evidence_type = already_done
        api("PATCH", f"/api/ideas/{idea_id}", {"manifestation_status": "validated"})
        log.info("SEED_SKIP_IMPLEMENTED idea=%s already on main (%s PR #%s) — marked validated",
                 idea_id, evidence_type, pr_num)
        _SEEDER_SKIP_CACHE.add(idea_id)
        return _seed_task_from_open_idea()  # try next idea

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

        # Cap: if any single phase has 10+ tasks, truly stuck — skip for THIS cycle
        # but don't permanently orphan it. If all tasks are gone (reaper cleaned up),
        # reset to none so we can start fresh next cycle.
        max_phase_tasks = max(phase_counts.values()) if phase_counts else 0
        total_tasks = sum(phase_counts.values())
        if max_phase_tasks >= 10:
            log.info("SEED: idea '%s' truly stuck (%d tasks in one phase) — skipping this session",
                     idea_name[:30], max_phase_tasks)
            _SEEDER_SKIP_CACHE.add(idea_id)
            api("PATCH", f"/api/ideas/{idea_id}", {"manifestation_status": "partial"})
            return _seed_task_from_open_idea()  # retry with next idea
        if total_tasks == 0 and idea.get("manifestation_status") == "partial":
            # Orphaned: marked partial but no tasks exist — reset to none
            log.info("SEED: idea '%s' orphaned (partial with 0 tasks) — resetting to none", idea_name[:30])
            api("PATCH", f"/api/ideas/{idea_id}", {"manifestation_status": "none"})

        # Check if review/code-review phase completed AND passed
        review_phase = "code-review" if "code-review" in completed_phases else ("review" if "review" in completed_phases else "")
        if review_phase:
            # Check output for explicit FAILED keywords
            review_passed = False
            # Check groups format
            for g in (idea_tasks.get("groups") or []):
                if not isinstance(g, dict) or g.get("task_type") not in ("review", "code-review"):
                    continue
                for t in (g.get("tasks") or []):
                    if t.get("status") == "completed":
                        t_output = (t.get("output") or "").strip().upper()
                        if "REVIEW_FAILED" in t_output or "CODE_REVIEW_FAILED" in t_output:
                            continue  # explicitly failed
                        if len(t_output) >= 30:
                            review_passed = True
                            break
            # Scan recent tasks by context.idea_id (API doesn't store top-level idea_id,
            # and task list doesn't include output field — so completed = passed)
            if not review_passed:
                recent = api("GET", "/api/agent/tasks?limit=50")
                if isinstance(recent, dict):
                    for t in recent.get("tasks", []):
                        ctx = t.get("context") if isinstance(t.get("context"), dict) else {}
                        if (ctx.get("idea_id") == idea_id
                                and t.get("task_type") in ("review", "code-review")
                                and t.get("status") == "completed"):
                            review_passed = True
                            log.info("SEED: found passing review for '%s' via task scan (task %s)",
                                     idea_name[:30], t.get("id", "?")[:16])
                            break

            if review_passed:
                # Advance to merge phase, not straight to validated
                task_type = "merge"
                log.info("SEED: idea '%s' review PASSED — advancing to merge phase", idea_name[:30])
            else:
                log.info("SEED: idea '%s' review completed but FAILED — needs re-review", idea_name[:30])
                task_type = "review"  # re-run review
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
        f"- If you cannot complete the task, explain WHY in detail (don't return empty).\n"
        f"\n"
        f"CODE QUALITY — DIF (Deep Inspection Framework):\n"
        f"- After writing any code file, verify it with DIF via curl:\n"
        f"    curl -s -X POST https://dif.merly.ai/api/v2/dif/verify \\\n"
        f"      -H 'Content-Type: application/json' \\\n"
        f"      -d '{{\"language\": \"python\", \"code\": \"'\"$(cat <your_file.py>)\"'\"}}'\n"
        f"- Or if cc CLI is available: cc dif verify --language python --file <your_file.py> --json\n"
        f"- Check response: trust_signal (positive/review=ok, concern=fix), verification (>40=ok, <30=fix)\n"
        f"- Fix any DIF-flagged issues before finishing. Include final DIF scores in your output.\n"
        f"- Include the DIF event_id in your output for traceability.\n"
        f"\n"
        f"COMMUNICATION:\n"
        f"- Check `cc inbox` every 5-7 minutes for messages from other nodes\n"
        f"- Send status updates: `cc msg broadcast \"Working on X: progress...\"`\n"
        f"- When done: `cc contribute --type code --cc 5 --desc \"what you did\"`\n"
        f"- If blocked: `cc msg broadcast \"Blocked: reason\"`"
        f"{validation_guidance}"
    )

    workspace_git_url_seed = idea.get("workspace_git_url") or ""
    seed_ctx: dict = {
        "idea_id": idea_id,
        "idea_name": idea_name,
        "seed_generated": True,
        "seed_source": "local_runner_smart_seed",
    }
    if workspace_git_url_seed:
        seed_ctx["workspace_git_url"] = workspace_git_url_seed
    result = api("POST", "/api/agent/tasks", {
        "direction": direction,
        "task_type": task_type,
        "idea_id": idea_id,  # top-level for API linking
        "context": seed_ctx,
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
    """Return (local_sha, origin_sha) from cached _NODE_GIT info."""
    return _NODE_GIT.get("local_sha", "unknown"), _NODE_GIT.get("origin_sha", "unknown")


def _register_node() -> None:
    """Register this worker node with the federation API on startup."""
    providers = [p for p in (PROVIDERS.keys() if PROVIDERS else _detect_providers().keys()) if p not in _PAUSED_PROVIDERS]
    tools = _detect_tools()

    # Build provider version map
    provider_versions = {}
    for pname, pspec in (PROVIDERS or {}).items():
        if isinstance(pspec, dict):
            provider_versions[pname] = pspec.get("_version", "unknown")

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
            "git": _NODE_GIT,
            "provider_versions": provider_versions,
        },
    }
    result = api("POST", "/api/federation/nodes?refresh_capabilities=true", payload)
    if result:
        log.info("NODE_REGISTERED id=%s hostname=%s sha=%s origin=%s up_to_date=%s providers=%s",
                 _NODE_ID, _NODE_NAME, _NODE_GIT.get("local_sha"),
                 _NODE_GIT.get("origin_sha"), _NODE_GIT.get("up_to_date"), providers)
    else:
        log.warning("NODE_REGISTER_FAILED id=%s — will retry on next heartbeat", _NODE_ID)


def _collect_system_metrics() -> dict[str, Any]:
    """Collect CPU, memory, disk, process, and network metrics."""
    metrics: dict[str, Any] = {}
    try:
        import psutil
        # CPU
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        metrics["cpu_count"] = psutil.cpu_count()
        metrics["load_avg"] = list(os.getloadavg()) if hasattr(os, "getloadavg") else []

        # Memory
        mem = psutil.virtual_memory()
        metrics["memory_percent"] = mem.percent
        metrics["memory_total_gb"] = round(mem.total / (1024 ** 3), 1)
        metrics["memory_available_gb"] = round(mem.available / (1024 ** 3), 1)
        metrics["memory_used_gb"] = round((mem.total - mem.available) / (1024 ** 3), 1)
        # Windows: cached = standby list (reclaimable). macOS: inactive + wired split.
        if hasattr(mem, "cached"):
            metrics["memory_cached_gb"] = round(mem.cached / (1024 ** 3), 1)
        if hasattr(mem, "buffers"):
            metrics["memory_buffers_gb"] = round(mem.buffers / (1024 ** 3), 1)
        # Swap
        try:
            swap = psutil.swap_memory()
            metrics["swap_percent"] = swap.percent
            metrics["swap_used_gb"] = round(swap.used / (1024 ** 3), 1)
            metrics["swap_total_gb"] = round(swap.total / (1024 ** 3), 1)
        except Exception:
            pass

        # Disk
        try:
            disk = psutil.disk_usage("/")
            metrics["disk_percent"] = disk.percent
            metrics["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
        except Exception:
            pass

        # Disk I/O
        try:
            dio = psutil.disk_io_counters()
            if dio:
                metrics["disk_read_mb"] = round(dio.read_bytes / (1024 ** 2))
                metrics["disk_write_mb"] = round(dio.write_bytes / (1024 ** 2))
        except Exception:
            pass

        # Network I/O
        try:
            nio = psutil.net_io_counters()
            if nio:
                metrics["net_sent_mb"] = round(nio.bytes_sent / (1024 ** 2))
                metrics["net_recv_mb"] = round(nio.bytes_recv / (1024 ** 2))
        except Exception:
            pass

        # Process count
        metrics["process_count"] = len(psutil.pids())

        # Runner-specific: our process
        proc = psutil.Process()
        metrics["runner_cpu_percent"] = proc.cpu_percent()
        metrics["runner_memory_mb"] = round(proc.memory_info().rss / (1024 ** 2))
        metrics["runner_threads"] = proc.num_threads()

    except ImportError:
        metrics["psutil_available"] = False
    except Exception as e:
        metrics["error"] = str(e)

    return metrics


def _send_heartbeat() -> None:
    """Update node liveness with system metrics so the UI can monitor health."""
    git_info = _get_git_info()
    system_metrics = _collect_system_metrics()
    result = api("POST", f"/api/federation/nodes/{_NODE_ID}/heartbeat", {
        "capabilities": {
            "executors": list(PROVIDERS.keys()) if PROVIDERS else [],
            "tools": _detect_tools(),
            "provider_streaks": get_provider_streaks(),
        },
        "git_sha": git_info.get("local_sha", "unknown"),
        "system_metrics": system_metrics,
    })
    if result:
        log.debug("HEARTBEAT sent for node %s sha=%s cpu=%s%% mem=%s%%",
                   _NODE_ID, git_info.get("local_sha", "?")[:8],
                   system_metrics.get("cpu_percent", "?"), system_metrics.get("memory_percent", "?"))
    else:
        _register_node()


def _detect_tools() -> list[str]:
    """Detect installed dev tools on this machine."""
    tools = []
    for tool in ["python", "python3", "node", "npm", "docker", "git", "pip", "cargo", "go"]:
        if shutil.which(tool):
            tools.append(tool)
    return tools


# Track last-pushed sample counts per (decision_point, slot_id) to send deltas only.
_last_pushed_samples: dict[str, int] = {}


def push_measurements(node_id: str) -> int:
    """Push local slot measurements to the federation hub.

    Reads from api/logs/slot_measurements/ and aggregates into
    MeasurementSummary payloads per (decision_point, slot_id).

    Only sends deltas (new samples since last push) to avoid inflating
    cumulative counts on the stats endpoint.
    """
    measurements_dir = _API_DIR / "logs" / "slot_measurements"
    if not measurements_dir.exists():
        return 0

    now = datetime.now(timezone.utc)
    summaries = []

    for f in measurements_dir.glob("*.json"):
        decision_point = f.stem
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(data, list) or not data:
            continue

        # Group by slot_id
        by_slot: dict[str, list[dict]] = {}
        for entry in data:
            slot_id = entry.get("slot_id", "unknown")
            by_slot.setdefault(slot_id, []).append(entry)

        for slot_id, entries in by_slot.items():
            total_count = len(entries)
            tracker_key = f"{decision_point}|{slot_id}"
            last_count = _last_pushed_samples.get(tracker_key, 0)
            delta = total_count - last_count

            if delta <= 0:
                continue

            # Only compute stats over the new (delta) entries
            new_entries = entries[last_count:]
            successes = sum(1 for e in new_entries if e.get("value_score", 0) >= 0.5)
            failures = len(new_entries) - successes
            durations = [e["duration_s"] for e in new_entries if "duration_s" in e]
            mean_duration = sum(durations) / len(durations) if durations else None
            value_scores = [e.get("value_score", 0) for e in new_entries]
            mean_value = sum(value_scores) / len(value_scores) if value_scores else 0.0

            error_classes: dict[str, int] = {}
            for e in new_entries:
                ec = e.get("error_class")
                if ec:
                    error_classes[ec] = error_classes.get(ec, 0) + 1

            timestamps = []
            for e in new_entries:
                ts = e.get("timestamp")
                if ts:
                    try:
                        timestamps.append(datetime.fromisoformat(ts))
                    except Exception:
                        pass

            period_start = min(timestamps) if timestamps else now
            period_end = max(timestamps) if timestamps else now

            summaries.append({
                "node_id": node_id,
                "decision_point": decision_point,
                "slot_id": slot_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "sample_count": delta,
                "successes": successes,
                "failures": failures,
                "mean_duration_s": mean_duration,
                "mean_value_score": round(mean_value, 4),
                "error_classes_json": error_classes,
                "_total_count": total_count,  # internal: for updating tracker on success
                "_tracker_key": tracker_key,  # internal: for updating tracker on success
            })

    if not summaries:
        return 0

    # Strip internal keys before sending
    payload_summaries = [
        {k: v for k, v in s.items() if not k.startswith("_")}
        for s in summaries
    ]

    result = api("POST", f"/api/federation/nodes/{node_id}/measurements", {
        "summaries": payload_summaries,
    })
    if result:
        # Update tracker only after successful push
        for s in summaries:
            _last_pushed_samples[s["_tracker_key"]] = s["_total_count"]
        stored = result.get("stored", len(payload_summaries))
        log.info("MEASUREMENTS PUSHED node_id=%s count=%d stored=%d", node_id, len(payload_summaries), stored)
        return stored
    log.warning("MEASUREMENT PUSH FAILED node_id=%s", node_id)
    return 0


# ── Remote node messaging ────────────────────────────────────────────

# Safe commands that can be executed remotely without confirmation.
_SAFE_COMMANDS = {
    "update": "git pull origin main",
    "status": None,  # handled inline
    "diagnose": None,  # handled inline
    "restart": None,  # handled inline
    "ping": None,  # handled inline
    "deploy": None,  # handled by _deploy_to_vps()
}


def _process_node_messages(node_id: str) -> int:
    """Check for messages addressed to this node and execute safe commands.

    Returns number of messages processed.
    """
    data = api("GET", f"/api/federation/nodes/{node_id}/messages?unread_only=true&limit=10")
    if not data:
        return 0
    messages = data.get("messages", []) if isinstance(data, dict) else []
    if not messages:
        return 0

    processed = 0
    for msg in messages:
        msg_id = msg.get("id", "?")
        msg_type = msg.get("type", "text")
        from_node = msg.get("from_node", "?")[:16]
        text = msg.get("text", "")
        payload = msg.get("payload", {}) or {}

        log.info("MSG_RECEIVED id=%s type=%s from=%s text=%s",
                 msg_id[:16], msg_type, from_node, text[:80])

        # Note: GET /messages already marks them as read -- no separate PATCH needed

        if msg_type == "command":
            response = _execute_node_command(node_id, payload, text)
            # Send response back
            api("POST", f"/api/federation/nodes/{node_id}/messages", {
                "from_node": node_id,
                "to_node": from_node,
                "type": "command_response",
                "text": response,
                "payload": {"in_reply_to": msg_id},
            })
            processed += 1
        elif msg_type == "text":
            log.info("MSG_TEXT from=%s: %s", from_node, text[:200])
            # Send ack back
            api("POST", f"/api/federation/nodes/{node_id}/messages", {
                "from_node": node_id,
                "to_node": from_node,
                "type": "ack",
                "text": f"Received: {text[:80]}",
                "payload": {"in_reply_to": msg_id, "ack": True},
            })
            processed += 1
        elif msg_type == "ack":
            # Don't ack an ack
            log.info("MSG_ACK from=%s: %s", from_node, text[:100])
            processed += 1
        elif msg_type == "command_response":
            log.info("MSG_REPLY from=%s: %s", from_node, text[:200])
            processed += 1
        else:
            log.info("MSG_UNKNOWN type=%s from=%s", msg_type, from_node)

    if processed:
        log.info("MSG_PROCESSED %d messages", processed)
    return processed


def _execute_node_command(node_id: str, payload: dict, text: str) -> str:
    """Execute a safe command received from another node.

    Returns a response string describing the result.
    """
    command = payload.get("command", "").strip().lower()

    if command in ("update", "checkout-main"):
        # Switch to main and pull latest — handles nodes stuck on worktree branches
        try:
            steps = []
            # First: stash any local changes
            stash = subprocess.run(
                ["git", "stash"], capture_output=True, text=True, timeout=15, cwd=str(_REPO_DIR),
            )
            if "Saved" in stash.stdout:
                steps.append("stashed local changes")
            # Switch to main if not already there
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5, cwd=str(_REPO_DIR),
            ).stdout.strip()
            if branch != "main":
                checkout = subprocess.run(
                    ["git", "checkout", "main"],
                    capture_output=True, text=True, timeout=15, cwd=str(_REPO_DIR),
                )
                if checkout.returncode == 0:
                    steps.append(f"switched from {branch} to main")
                else:
                    return f"Checkout main failed: {checkout.stderr.strip()[:200]}"
            # Pull latest
            pull = subprocess.run(
                ["git", "pull", "origin", "main", "--ff-only"],
                capture_output=True, text=True, timeout=60, cwd=str(_REPO_DIR),
            )
            if pull.returncode != 0:
                # Try reset if ff-only fails
                subprocess.run(
                    ["git", "reset", "--hard", "origin/main"],
                    capture_output=True, text=True, timeout=15, cwd=str(_REPO_DIR),
                )
                steps.append("reset to origin/main (ff-only failed)")
            else:
                steps.append("pulled latest main")
            new_sha = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5, cwd=str(_REPO_DIR),
            ).stdout.strip()
            steps.append(f"now at {new_sha}")
            summary = " → ".join(steps)
            log.info("CMD_UPDATE: %s", summary)
            return f"Update successful: {summary}"
        except Exception as e:
            return f"Update error: {e}"

    elif command == "status":
        # Collect node status
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            status_lines = [
                f"Node: {_NODE_NAME} ({sys.platform})",
                f"CPU: {cpu}% | RAM: {mem.percent}% ({mem.available // (1024**3)}GB free)",
                f"Disk: {disk.percent}% ({disk.free // (1024**3)}GB free)",
                f"Python: {sys.version.split()[0]}",
                f"Providers: {list(PROVIDERS.keys()) if PROVIDERS else []}",
                f"PID: {os.getpid()}",
            ]
            return "\n".join(status_lines)
        except ImportError:
            return f"Node: {_NODE_NAME} ({sys.platform}), PID: {os.getpid()}"

    elif command == "diagnose":
        # Run diagnostics: check git status, runner health, recent errors
        lines = [f"=== Diagnostics for {_NODE_NAME} ==="]
        try:
            git_status = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=10,
                cwd=str(_REPO_DIR),
            )
            lines.append(f"Git status: {git_status.stdout.strip()[:200] or 'clean'}")

            git_log = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True, text=True, timeout=10,
                cwd=str(_REPO_DIR),
            )
            lines.append(f"Recent commits:\n{git_log.stdout.strip()}")

            # Check for recent errors in runner log
            err_log = Path("/tmp/coherence-runner.err")
            if err_log.exists():
                recent_errors = [
                    line for line in err_log.read_text().splitlines()[-50:]
                    if "ERROR" in line or "WARNING" in line
                ][-5:]
                if recent_errors:
                    lines.append("Recent errors:\n" + "\n".join(recent_errors))
                else:
                    lines.append("No recent errors")
        except Exception as e:
            lines.append(f"Diagnostic error: {e}")
        return "\n".join(lines)

    elif command == "restart":
        log.info("CMD_RESTART: received restart command -- will exit for launchd/systemd to restart")
        # Reply first, then exit -- the service manager restarts us
        response = "Restart acknowledged. Exiting for service manager to restart."
        # Schedule exit after a short delay so the response gets sent
        threading.Timer(2.0, lambda: os._exit(0)).start()
        return response

    elif command == "deploy":
        return _deploy_to_vps()

    elif command == "ping":
        return f"pong from {_NODE_NAME} at {datetime.now(timezone.utc).isoformat()}"

    else:
        log.warning("CMD_UNKNOWN: %s (not in safe command list)", command)
        return f"Unknown command: {command}. Safe commands: {', '.join(_SAFE_COMMANDS.keys())}"


def _deploy_to_vps() -> str:
    """Deploy latest main to VPS with health gate and automatic rollback.

    Steps:
    1. SSH to VPS, capture current deployed SHA
    2. Git pull on VPS
    3. Docker compose build + up
    4. Wait 30s for startup
    5. Health check -- if fails, rollback to previous SHA
    6. Return result
    """
    SSH_KEY = os.path.expanduser("~/.ssh/hostinger-openclaw")
    VPS_HOST = "root@187.77.152.42"
    VPS_REPO_DIR = "/docker/coherence-network/repo"
    COMPOSE_DIR = "/docker/coherence-network"

    if not os.path.exists(SSH_KEY):
        return "Deploy skipped: SSH key not found at ~/.ssh/hostinger-openclaw"

    def _ssh(cmd: str, timeout: int = 120) -> tuple[int, str]:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, "-o", "LogLevel=QUIET", "-o", "StrictHostKeyChecking=no",
             VPS_HOST, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()

    log.info("DEPLOY: starting VPS deployment")

    # 1. Capture current SHA for rollback
    rc, prev_sha = _ssh(f"cd {VPS_REPO_DIR} && git rev-parse --short HEAD", timeout=15)
    if rc != 0:
        return f"Deploy failed: could not get current VPS SHA: {prev_sha}"
    prev_sha = prev_sha.strip()[:10]
    log.info("DEPLOY: current VPS SHA: %s", prev_sha)

    # 2. Git pull
    rc, pull_output = _ssh(f"cd {VPS_REPO_DIR} && git pull origin main --ff-only", timeout=30)
    if rc != 0:
        return f"Deploy failed: git pull failed: {pull_output[:200]}"

    new_sha_rc, new_sha = _ssh(f"cd {VPS_REPO_DIR} && git rev-parse --short HEAD", timeout=15)
    new_sha = new_sha.strip()[:10]

    if new_sha == prev_sha:
        log.info("DEPLOY: VPS already up to date at %s", new_sha)
        return f"VPS already up to date at {new_sha}"

    log.info("DEPLOY: pulled %s -> %s", prev_sha, new_sha)

    # 3. Docker build + up
    rc, build_output = _ssh(
        f"cd {COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web",
        timeout=300,
    )
    if rc != 0:
        # Rollback
        log.warning("DEPLOY: build/up failed, rolling back to %s", prev_sha)
        _ssh(f"cd {VPS_REPO_DIR} && git checkout {prev_sha} && cd {COMPOSE_DIR} && docker compose up -d api web", timeout=120)
        return f"Deploy failed: build error (rolled back to {prev_sha}): {build_output[-200:]}"

    log.info("DEPLOY: containers started, waiting 30s for health check")

    # 4. Wait for startup
    time.sleep(30)

    # 5. Health check
    try:
        health = httpx.get("https://api.coherencycoin.com/api/health", timeout=15)
        if health.status_code == 200:
            data = health.json()
            deployed_sha = str(data.get("deployed_sha", ""))[:10]
            schema_ok = data.get("schema_ok", False)
            if schema_ok:
                log.info("DEPLOY: health check passed -- SHA=%s schema_ok=%s", deployed_sha, schema_ok)
                return f"Deploy successful: {prev_sha} -> {new_sha}. Health: OK, schema: OK"
            else:
                log.warning("DEPLOY: schema_ok=False, rolling back")
        else:
            log.warning("DEPLOY: health check returned %d, rolling back", health.status_code)
    except Exception as e:
        log.warning("DEPLOY: health check failed: %s, rolling back", e)

    # 6. Rollback
    log.warning("DEPLOY: rolling back to %s", prev_sha)
    _ssh(f"cd {VPS_REPO_DIR} && git checkout {prev_sha} && cd {COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web", timeout=300)
    return f"Deploy failed health check -- rolled back to {prev_sha}"


# ── Parallel worktree execution ───────────────────────────────────────

_MAX_PARALLEL = rc("execution", "parallel", 2)
_WORKTREE_BASE = _REPO_DIR / ".worktrees"
_PROGRESS_DIR = _REPO_DIR / ".idea-progress"
# Mirror cache for external workspace repos — one clone per remote, shared across tasks.
_WORKSPACE_REPOS_DIR = Path.home() / ".coherence-network" / "repos"


def _get_or_update_workspace_repo(git_url: str) -> "Path | None":
    """Clone or update a local mirror of an external git repo.

    Returns the local clone path, or None on failure.
    Path convention: ~/.coherence-network/repos/{host}/{org}/{repo}/
    Multiple tasks against the same remote reuse the same clone.
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(git_url)
        host = parsed.hostname or "unknown"
        path_segment = parsed.path.strip("/")
        if path_segment.endswith(".git"):
            path_segment = path_segment[:-4]
        local_path = _WORKSPACE_REPOS_DIR / host / path_segment

        if local_path.exists():
            log.info("WORKSPACE_REPO_UPDATE url=%s path=%s", git_url, local_path)
            fetch = _run_git_command(
                ["git", "fetch", "--all", "--prune", "--quiet"],
                capture_output=True, text=True, timeout=60, cwd=str(local_path),
            )
            if fetch.returncode != 0:
                log.warning("WORKSPACE_REPO_FETCH_FAILED url=%s: %s", git_url,
                            (fetch.stderr or fetch.stdout or "").strip())
        else:
            log.info("WORKSPACE_REPO_CLONE url=%s → %s", git_url, local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            clone = _run_git_command(
                ["git", "clone", "--quiet", git_url, str(local_path)],
                capture_output=True, text=True, timeout=120,
            )
            if clone.returncode != 0:
                log.error("WORKSPACE_REPO_CLONE_FAILED url=%s: %s", git_url,
                          (clone.stderr or clone.stdout or "").strip())
                return None

        return local_path
    except Exception as exc:
        log.error("WORKSPACE_REPO_ERROR url=%s: %s", git_url, exc)
        return None


def _inject_idea_progress(idea_id: str, wt_path: Path) -> None:
    """Copy persisted progress sheet into a worktree so the provider can read/update it."""
    src = _PROGRESS_DIR / f"{idea_id}.md"
    dst = wt_path / ".idea-progress.md"
    try:
        if src.exists():
            shutil.copy2(str(src), str(dst))
            log.info("PROGRESS_INJECTED idea=%s (%d bytes)", idea_id, dst.stat().st_size)
        else:
            # Create empty progress sheet with header
            dst.write_text(
                f"# Progress — {idea_id}\n\n"
                f"## Completed phases\n\n(none yet)\n\n"
                f"## Current task\n\n(starting)\n\n"
                f"## Key decisions\n\n(none yet)\n\n"
                f"## Blockers\n\n(none)\n",
                encoding="utf-8",
            )
            log.info("PROGRESS_CREATED idea=%s", idea_id)
    except Exception as e:
        log.warning("PROGRESS_INJECT_FAILED idea=%s error=%s", idea_id, e)


def _persist_idea_progress(idea_id: str, wt_path: Path) -> None:
    """Copy progress sheet from worktree back to persistent storage."""
    src = wt_path / ".idea-progress.md"
    if not src.exists():
        return
    try:
        _PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        dst = _PROGRESS_DIR / f"{idea_id}.md"
        shutil.copy2(str(src), str(dst))
        log.info("PROGRESS_PERSISTED idea=%s (%d bytes)", idea_id, dst.stat().st_size)
    except Exception as e:
        log.warning("PROGRESS_PERSIST_FAILED idea=%s error=%s", idea_id, e)


_EVENTS_DIR = _REPO_DIR / ".idea-events"


def _append_idea_event(idea_id: str, event_type: str, payload: dict) -> None:
    """Append a versioned event to .idea-events/{idea_id}.jsonl (local, not committed)."""
    import json as _json_ev
    _EVENTS_DIR.mkdir(exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **payload,
    }
    path = _EVENTS_DIR / f"{idea_id}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_json_ev.dumps(entry) + "\n")


def _repo_is_linked_worktree(repo_root: str) -> bool:
    git_marker = Path(repo_root) / ".git"
    if not git_marker.exists() or git_marker.is_dir() or not git_marker.is_file():
        return False
    try:
        gitdir_line = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not gitdir_line.startswith("gitdir:"):
        return False
    gitdir = Path(gitdir_line.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = (git_marker.parent / gitdir).resolve()
    return "/.git/worktrees/" in gitdir.as_posix().lower()


def _resolve_available_ref(repo_root: str, refs: list[str]) -> str | None:
    seen: set[str] = set()
    for ref in refs:
        ref = str(ref or "").strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        proc = _run_git_command(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True, text=True, timeout=10, cwd=repo_root,
        )
        if proc.returncode == 0:
            return ref
    return None


def _get_origin_remote_url(repo_root: str) -> str:
    proc = _run_git_command(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, timeout=10, cwd=repo_root,
    )
    if proc.returncode == 0:
        return (proc.stdout or "").strip()
    return ""


def _extract_git_archive(archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        for member in members:
            member_path = (destination_root / member.name).resolve()
            if not member_path.is_relative_to(destination_root):
                raise ValueError(f"unsafe archive member: {member.name}")
        archive.extractall(destination)


def _create_standalone_task_repo(
    task_id: str,
    wt_path: Path,
    branch: str,
    *,
    base_branch: str | None = None,
    idea_id: str = "",
) -> Path | None:
    """Create an isolated task repo when nested git worktrees are not writable.

    Linked worktrees share a parent gitdir. In restricted environments that makes
    ``git worktree add`` write through to the parent repo's refs/FETCH_HEAD, which
    can fail with Permission denied. This fallback keeps task execution isolated
    inside a standalone git repo rooted under ``.worktrees/``.
    """
    slug = task_id[:16]
    repo_root = str(_REPO_DIR)
    archive_candidates = []
    if base_branch:
        archive_candidates.extend([f"origin/{base_branch}", base_branch])
    archive_candidates.extend(["origin/main", "main", "HEAD"])
    archive_ref = _resolve_available_ref(repo_root, archive_candidates)
    origin_url = _get_origin_remote_url(repo_root)
    archive_path: Path | None = None

    try:
        wt_path.mkdir(parents=True, exist_ok=True)
        init = _run_git_command(
            ["git", "init", "--quiet"],
            capture_output=True, text=True, timeout=30, cwd=str(wt_path),
        )
        if init.returncode != 0:
            detail = (init.stderr or init.stdout or "unknown failure").strip()
            log.warning("WORKTREE_STANDALONE_INIT_FAILED task=%s path=%s error=%s", slug, wt_path, detail)
            return None

        for key, value in (
            ("user.name", "Coherence Task Runner"),
            ("user.email", "runner@coherence.local"),
        ):
            _run_git_command(
                ["git", "config", key, value],
                capture_output=True, text=True, timeout=10, cwd=str(wt_path),
            )

        if origin_url:
            _run_git_command(
                ["git", "remote", "add", "origin", origin_url],
                capture_output=True, text=True, timeout=10, cwd=str(wt_path),
            )

        if archive_ref:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f"-{slug}.tar",
                dir=str(_WORKTREE_BASE),
            ) as tmp:
                archive_path = Path(tmp.name)

            archive = _run_git_command(
                ["git", "archive", "--format=tar", f"--output={archive_path}", archive_ref],
                capture_output=True, text=True, timeout=120, cwd=repo_root,
            )
            if archive.returncode != 0:
                detail = (archive.stderr or archive.stdout or "unknown failure").strip()
                log.warning("WORKTREE_ARCHIVE_FAILED task=%s ref=%s error=%s", slug, archive_ref, detail)
                return None

            _extract_git_archive(archive_path, wt_path)

            checkout = _run_git_command(
                ["git", "checkout", "-b", branch],
                capture_output=True, text=True, timeout=10, cwd=str(wt_path),
            )
            if checkout.returncode != 0:
                detail = (checkout.stderr or checkout.stdout or "unknown failure").strip()
                log.warning("WORKTREE_STANDALONE_BRANCH_FAILED task=%s branch=%s error=%s", slug, branch, detail)
                return None

            stage = _run_git_command(
                ["git", "add", "-A"],
                capture_output=True, text=True, timeout=30, cwd=str(wt_path),
            )
            if stage.returncode != 0:
                detail = (stage.stderr or stage.stdout or "unknown failure").strip()
                log.warning("WORKTREE_STANDALONE_STAGE_FAILED task=%s error=%s", slug, detail)
                return None

            commit = _run_git_command(
                ["git", "commit", "--quiet", "-m", f"Task {slug}: base snapshot ({archive_ref})"],
                capture_output=True, text=True, timeout=30, cwd=str(wt_path),
            )
            if commit.returncode != 0:
                detail = (commit.stderr or commit.stdout or "unknown failure").strip()
                log.warning("WORKTREE_STANDALONE_COMMIT_FAILED task=%s error=%s", slug, detail)
                return None

            log.info("WORKTREE_STANDALONE_CREATED task=%s base=%s path=%s", slug, archive_ref, wt_path)
        else:
            remote_ref = base_branch or "main"
            if not origin_url:
                log.warning("WORKTREE_STANDALONE_REF_MISSING task=%s ref=%s (no origin remote)", slug, remote_ref)
                return None

            fetch = _run_git_command(
                ["git", "fetch", "--quiet", "origin", remote_ref],
                capture_output=True, text=True, timeout=60, cwd=str(wt_path),
            )
            if fetch.returncode != 0:
                detail = (fetch.stderr or fetch.stdout or "unknown failure").strip()
                log.warning("WORKTREE_STANDALONE_FETCH_FAILED task=%s ref=%s error=%s", slug, remote_ref, detail)
                return None

            checkout = _run_git_command(
                ["git", "checkout", "-b", branch, "FETCH_HEAD"],
                capture_output=True, text=True, timeout=30, cwd=str(wt_path),
            )
            if checkout.returncode != 0:
                detail = (checkout.stderr or checkout.stdout or "unknown failure").strip()
                log.warning("WORKTREE_STANDALONE_CHECKOUT_FAILED task=%s branch=%s error=%s", slug, branch, detail)
                return None

            log.info("WORKTREE_STANDALONE_FETCH_CREATED task=%s base=%s path=%s", slug, remote_ref, wt_path)

        if idea_id:
            _inject_idea_progress(idea_id, wt_path)
        return wt_path
    except Exception as e:
        log.warning("WORKTREE_STANDALONE_FAILED task=%s error=%s", slug, e)
        shutil.rmtree(wt_path, ignore_errors=True)
    finally:
        if archive_path and archive_path.exists():
            try:
                archive_path.unlink()
            except OSError:
                pass
    return None


def _branch_exists(repo_root: str, branch: str) -> bool:
    proc = _run_git_command(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True, text=True, timeout=5, cwd=repo_root,
    )
    return proc.returncode == 0


def _tracked_worktree_paths(repo_root: str) -> set[Path]:
    proc = _run_git_command(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=10, cwd=repo_root,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown failure").strip()
        log.warning("WORKTREE_LIST_FAILED repo=%s error=%s", repo_root, detail)
        return set()

    paths: set[Path] = set()
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line.split(" ", 1)[1].strip()).resolve())
    return paths


def _reclaim_worktree_slot(repo_root: str, wt_path: Path, branch: str) -> bool:
    branch_present = _branch_exists(repo_root, branch)
    if not wt_path.exists() and not branch_present:
        return True

    _run_git_command(
        ["git", "worktree", "prune"],
        capture_output=True, text=True, timeout=10, cwd=repo_root,
    )

    tracked_paths = _tracked_worktree_paths(repo_root)
    if wt_path.resolve() in tracked_paths:
        remove = _run_git_command(
            ["git", "worktree", "remove", "--force", str(wt_path)],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        if remove.returncode != 0:
            detail = (remove.stderr or remove.stdout or "unknown failure").strip()
            log.warning("WORKTREE_SLOT_REMOVE_FAILED path=%s error=%s", wt_path, detail)

    if wt_path.exists():
        try:
            shutil.rmtree(wt_path)
            log.info("WORKTREE_SLOT_ORPHAN_REMOVED path=%s", wt_path)
        except Exception as e:
            log.warning("WORKTREE_SLOT_ORPHAN_REMOVE_FAILED path=%s error=%s", wt_path, e)

    if branch_present:
        delete = _run_git_command(
            ["git", "branch", "-D", branch],
            capture_output=True, text=True, timeout=10, cwd=repo_root,
        )
        if delete.returncode != 0:
            detail = (delete.stderr or delete.stdout or "unknown failure").strip()
            log.warning("WORKTREE_BRANCH_DELETE_FAILED branch=%s error=%s", branch, detail)
            branch_present = _branch_exists(repo_root, branch)
        else:
            branch_present = False

    slot_clear = not wt_path.exists() and not branch_present
    if not slot_clear:
        log.warning(
            "WORKTREE_SLOT_RECLAIM_FAILED path=%s branch=%s path_exists=%s branch_exists=%s",
            wt_path,
            branch,
            wt_path.exists(),
            branch_present,
        )
    return slot_clear


def _create_worktree(
    task_id: str,
    base_branch: str | None = None,
    *,
    idea_id: str = "",
    workspace_git_url: str = "",
) -> "Path | None":
    """Create a git worktree for isolated task execution.

    base_branch: optional remote branch to base on (e.g. 'worker/impl/idea/task_abc').
    If None, defaults to origin/main. Used by test/review/code-review phases
    to checkout the impl PR branch so the provider can see the actual code.
    idea_id: if provided, injects the persisted .idea-progress.md into the worktree.
    workspace_git_url: if provided, worktree is created inside a local mirror of
    that remote repo instead of the default _REPO_DIR. Enables multi-repo pipeline.
    """
    slug = task_id[:16]

    # Determine which repo and worktree base to use
    if workspace_git_url:
        workspace_repo = _get_or_update_workspace_repo(workspace_git_url)
        if workspace_repo is None:
            log.error("WORKTREE_WORKSPACE_REPO_FAILED task=%s url=%s", slug, workspace_git_url)
            return None
        repo_root = str(workspace_repo)
        worktree_base = workspace_repo / ".worktrees"
    else:
        repo_root = str(_REPO_DIR)
        worktree_base = _WORKTREE_BASE

    wt_path = worktree_base / f"task-{slug}"
    branch = f"task/{slug}"
    try:
        worktree_base.mkdir(parents=True, exist_ok=True)
        if not _reclaim_worktree_slot(repo_root, wt_path, branch):
            return None
        if _repo_is_linked_worktree(repo_root):
            log.info(
                "WORKTREE_LINKED_REPO task=%s repo=%s -- using standalone task repo fallback",
                slug,
                repo_root,
            )
            standalone = _create_standalone_task_repo(
                task_id,
                wt_path,
                branch,
                base_branch=base_branch,
                idea_id=idea_id,
            )
            if standalone is not None:
                return standalone
            log.info(
                "WORKTREE_STANDALONE_FALLBACK task=%s -- retrying with git worktree add",
                slug,
            )
            # Standalone may have left a partial directory; clear slot before normal add.
            if not _reclaim_worktree_slot(repo_root, wt_path, branch):
                log.warning(
                    "WORKTREE_STANDALONE_FALLBACK_RECLAIM_FAILED task=%s path=%s",
                    slug,
                    wt_path,
                )
                return None
        # Fetch latest remote refs
        fetch = _run_git_command(
            ["git", "fetch", "origin", "--quiet"],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        if fetch.returncode != 0:
            detail = (fetch.stderr or fetch.stdout or "unknown failure").strip()
            log.warning("WORKTREE_FETCH_FAILED task=%s error=%s", slug, detail)
        # Determine base ref: PR branch if specified, else origin/main
        base_ref = "origin/main"
        if base_branch:
            # Check if the remote branch exists
            check = _run_git_command(
                ["git", "rev-parse", "--verify", f"origin/{base_branch}"],
                capture_output=True, text=True, timeout=5, cwd=repo_root,
            )
            if check.returncode == 0:
                base_ref = f"origin/{base_branch}"
                log.info("WORKTREE_FROM_PR task=%s branch=%s", slug, base_branch)
            else:
                log.info("WORKTREE_PR_BRANCH_NOT_FOUND task=%s branch=%s — falling back to origin/main", slug, base_branch)

        create = _run_git_command(
            ["git", "worktree", "add", "-b", branch, str(wt_path), base_ref],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        if create.returncode != 0:
            detail = (create.stderr or create.stdout or "unknown failure").strip()
            log.warning(
                "WORKTREE_CREATE_FAILED task=%s base=%s path=%s error=%s",
                slug,
                base_ref,
                wt_path,
                detail,
            )
            return None
        if wt_path.exists():
            log.info("WORKTREE_CREATED task=%s base=%s path=%s", slug, base_ref, wt_path)
            # Inject persisted idea progress sheet if available
            if idea_id:
                _inject_idea_progress(idea_id, wt_path)
            return wt_path
    except Exception as e:
        log.warning("WORKTREE_FAILED task=%s error=%s", slug, e)
    return None


def _capture_worktree_diff(task_id: str, wt_path: Path) -> str:
    """Capture git diff from worktree after provider execution.

    Returns the full diff content (up to 10KB) — this is the actual code
    that was written, suitable for carrying forward to a retry task.
    """
    slug = task_id[:16]
    try:
        # Stage everything so diff captures new files too
        _run_git_command(
            ["git", "add", "-A"], capture_output=True, timeout=10, cwd=str(wt_path),
        )
        diff = _run_git_command(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, timeout=10, cwd=str(wt_path),
        )
        full_diff = _run_git_command(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10, cwd=str(wt_path),
        )
        if diff.stdout.strip():
            log.info("WORKTREE_DIFF task=%s files_changed:\n%s", slug, diff.stdout.strip()[:500])
            return full_diff.stdout[:10000]
    except Exception as e:
        log.warning("WORKTREE_DIFF_FAILED task=%s error=%s", slug, e)
    return ""


def _sweep_stale_worktrees(max_age_hours: int = 2) -> int:
    """Remove worktrees older than max_age_hours. Called periodically from the loop."""
    wt_base = _REPO_DIR / ".worktrees"
    if not wt_base.exists():
        return 0
    cleaned = 0
    now = time.time()
    for wt_dir in wt_base.iterdir():
        if not wt_dir.is_dir() or not wt_dir.name.startswith("task-"):
            continue
        try:
            age_hours = (now - wt_dir.stat().st_mtime) / 3600
            if age_hours < max_age_hours:
                continue
            task_slug = wt_dir.name.replace("task-", "")
            if _reclaim_worktree_slot(str(_REPO_DIR), wt_dir, f"task/{task_slug}"):
                cleaned += 1
        except Exception:
            pass
    if cleaned:
        _run_git_command(["git", "worktree", "prune"], capture_output=True, timeout=10, cwd=str(_REPO_DIR))
        log.info("SWEEP_WORKTREES cleaned %d stale worktrees", cleaned)
    return cleaned


def _cleanup_worktree(task_id: str) -> None:
    """Remove a worktree after task completion.

    Fix 5: only called AFTER push is confirmed (or task failed).
    """
    slug = task_id[:16]
    wt_path = _WORKTREE_BASE / f"task-{slug}"
    branch = f"task/{slug}"
    try:
        if _reclaim_worktree_slot(str(_REPO_DIR), wt_path, branch):
            log.info("WORKTREE_CLEANED task=%s", slug)
    except Exception as e:
        log.warning("WORKTREE_CLEANUP_FAILED task=%s error=%s", slug, e)


def _push_branch_to_origin(task_id: str, wt_path: Path) -> bool:
    """Push the task branch to origin so other nodes can see the code.

    After impl/test: push branch (NOT main) — code stays on branch until
    code-review passes. Other nodes fetch this branch for subsequent phases.
    """
    slug = task_id[:16]
    branch = f"task/{slug}"
    try:
        # Commit any uncommitted changes in the worktree
        _run_git_command(
            ["git", "add", "-A"],
            capture_output=True, timeout=10, cwd=str(wt_path),
        )
        # Check if there's anything to commit
        status = _run_git_command(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, cwd=str(wt_path),
        )
        if status.stdout.strip():
            _run_git_command(
                ["git", "commit", "-m", f"Task {slug}: provider output"],
                capture_output=True, text=True, timeout=30, cwd=str(wt_path),
            )

        # Push BRANCH to origin using direct HTTPS URL with token
        # This avoids git remote-https helper issues in worktrees
        gh_token = ""
        # Use seeker71 profile for push access (ghx.sh resolves this from workspace)
        gh_env = dict(os.environ)
        config_base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        seeker71_config = os.path.join(config_base, "gh-seeker71")
        if os.path.isdir(seeker71_config):
            gh_env["GH_CONFIG_DIR"] = seeker71_config
        for gh_cmd in ["gh"]:
            try:
                gh_result = subprocess.run(
                    [gh_cmd, "auth", "token"],
                    capture_output=True, text=True, timeout=10,
                    env=gh_env,
                )
                if gh_result.returncode == 0 and gh_result.stdout.strip():
                    gh_token = gh_result.stdout.strip()
                    break
            except FileNotFoundError:
                continue
            except Exception:
                continue

        # Get the repo URL from git remote
        remote_url = ""
        try:
            remote_result = _run_git_command(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=str(wt_path),
            )
            remote_url = remote_result.stdout.strip()
        except Exception:
            pass

        push_env = dict(os.environ)
        push_env["SKIP_PR_GUARD"] = "1"

        if gh_token and "github.com" in remote_url:
            # Extract owner/repo from remote URL
            import re as _re
            match = _re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote_url)
            if match:
                repo_path = match.group(1).rstrip(".git")
                token_url = f"https://x-access-token:{gh_token}@github.com/{repo_path}.git"
                push_cmd = ["git", "push", token_url, f"HEAD:refs/heads/{branch}"]
            else:
                push_cmd = [
                    "git", "-c", f"url.https://x-access-token:{gh_token}@github.com/.insteadOf=https://github.com/",
                    "push", "origin", branch,
                ]
        else:
            push_cmd = ["git", "push", "origin", branch]

        push = _run_git_command(
            push_cmd,
            capture_output=True, text=True, timeout=60, cwd=str(wt_path),
            env=push_env,
        )
        if push.returncode == 0:
            log.info("BRANCH_PUSHED task=%s branch=%s", slug, branch)
            return True
        else:
            log.warning("BRANCH_PUSH_FAILED task=%s error=%s", slug, push.stderr.strip()[:200])
            return False
    except Exception as e:
        log.warning("BRANCH_PUSH_FAILED task=%s error=%s", slug, e)
        return False


def _merge_branch_to_main(task_id: str) -> bool:
    """Merge task branch to main AND push. Only called after code-review passes.

    This is the gate — code only reaches main after review.
    """
    slug = task_id[:16]
    branch = f"task/{slug}"
    repo_root = str(_REPO_DIR)
    try:
        # Fetch latest
        _run_git_command(
            ["git", "fetch", "origin"],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        # Check if branch exists on origin
        check = _run_git_command(
            ["git", "rev-parse", "--verify", f"origin/{branch}"],
            capture_output=True, text=True, timeout=10, cwd=repo_root,
        )
        if check.returncode != 0:
            log.info("MERGE_SKIP task=%s — branch not on origin (no code changes)", slug)
            return True

        # Merge origin/branch into local main
        _run_git_command(
            ["git", "checkout", "main"],
            capture_output=True, text=True, timeout=10, cwd=repo_root,
        )
        merge = _run_git_command(
            ["git", "merge", "--no-ff", f"origin/{branch}", "-m", f"Merge reviewed task {slug}"],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        if merge.returncode != 0:
            _run_git_command(["git", "merge", "--abort"], capture_output=True, timeout=10, cwd=repo_root)
            log.warning("MERGE_CONFLICT task=%s", slug)
            return False

        # Push main to origin
        push = _run_git_command(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, timeout=60, cwd=repo_root,
        )
        if push.returncode == 0:
            log.info("MERGED_TO_MAIN task=%s", slug)
            # Clean up remote branch
            _run_git_command(
                ["git", "push", "origin", "--delete", branch],
                capture_output=True, text=True, timeout=30, cwd=repo_root,
            )
            return True
        else:
            log.warning("MAIN_PUSH_FAILED task=%s error=%s", slug, push.stderr.strip()[:200])
            return False
    except Exception as e:
        log.warning("MERGE_TO_MAIN_FAILED task=%s error=%s", slug, e)
        return False


def _run_task_in_worktree(task: dict, wt_path: Path) -> tuple[bool, str]:
    """Execute a task inside a worktree directory.

    Fix 2: returns (success, git_diff) — diff captured after provider runs.
    """
    task_id = task["id"]
    global _REPO_DIR
    original_repo = _REPO_DIR
    try:
        _REPO_DIR = wt_path
        ok = run_one(task, dry_run=False)
        # Fix 2: capture what the provider actually wrote
        diff = _capture_worktree_diff(task_id, wt_path)
        return ok, diff
    except Exception as e:
        log.error("WORKTREE_EXEC_FAILED task=%s error=%s", task_id[:16], e)
        return False, ""
    finally:
        _REPO_DIR = original_repo


_active_idea_ids: set[str] = set()
_active_lock = threading.Lock()
_shutdown_event = threading.Event()
_update_pending = threading.Event()  # Set when origin/main has new commits


def _runner_deploy_phase(task: dict) -> bool:
    """Fix 6: deploy is a RUNNER action — SSH to VPS, build, health check.

    The provider can't SSH. The runner has the key and the env.
    """
    task_id = task["id"]
    log.info("DEPLOY_PHASE task=%s — runner executing deploy", task_id[:16])
    try:
        result = _deploy_to_vps()
        if "successful" in str(result).lower():
            complete_task(task_id, f"Deploy passed: {result}", True)
            return True
        else:
            complete_task(task_id, f"Deploy failed: {result}", False)
            return False
    except Exception as e:
        log.error("DEPLOY_PHASE_ERROR task=%s: %s", task_id[:16], e)
        complete_task(task_id, f"Deploy error: {e}", False)
        return False


def _runner_verify_phase(task: dict) -> bool:
    """Fix 7: verify runs spec scenarios against production — runner action.

    Runner makes HTTP calls and compares actual vs expected. No provider needed.
    """
    task_id = task["id"]
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = ctx.get("idea_id", "")
    log.info("VERIFY_PHASE task=%s idea=%s — runner verifying production", task_id[:16], idea_id[:20])

    results = []
    passed = 0
    failed = 0

    # Basic endpoint existence checks
    api_base = rc("api", "base_url", "https://api.coherencycoin.com")
    checks = [
        (f"{api_base}/api/health", 200, "API health"),
        (f"{api_base}/api/ideas/count", 200, "Ideas count"),
    ]

    for url, expected_status, label in checks:
        try:
            import httpx
            resp = httpx.get(url, timeout=10)
            if resp.status_code == expected_status:
                results.append(f"PASS: {label} -> HTTP {resp.status_code}")
                passed += 1
            else:
                results.append(f"FAIL: {label} -> HTTP {resp.status_code} (expected {expected_status})")
                failed += 1
        except Exception as e:
            results.append(f"FAIL: {label} -> {e}")
            failed += 1

    output = f"Verify: {passed} passed, {failed} failed\n" + "\n".join(results)
    success = failed == 0
    complete_task(task_id, output, success)
    log.info("VERIFY_PHASE task=%s passed=%d failed=%d", task_id[:16], passed, failed)
    return success


def _worker_loop(worker_id: int, dry_run: bool = False) -> None:
    """Independent worker thread: claim one task, execute, repeat."""
    while not _shutdown_event.is_set():
        try:
            # Don't claim new tasks if an update is pending — finish current, then update
            if _update_pending.is_set():
                log.info("WORKER[%d] update pending — not claiming new tasks", worker_id)
                _shutdown_event.wait(10)
                continue

            # Get a pending task
            pending = api("GET", "/api/agent/tasks?status=pending&limit=5")
            if not pending:
                _shutdown_event.wait(10)
                continue

            task_list = pending if isinstance(pending, list) else pending.get("tasks", [])
            if not task_list:
                _shutdown_event.wait(10)
                continue

            # Respect parallel cap: don't claim if at capacity
            with _active_lock:
                if len(_active_idea_ids) >= _MAX_PARALLEL:
                    _shutdown_event.wait(15)
                    continue

            # Find a task for an idea we're not already working on
            task = None
            for candidate in task_list:
                ctx = candidate.get("context") if isinstance(candidate.get("context"), dict) else {}
                idea_id = ctx.get("idea_id", "")
                with _active_lock:
                    if len(_active_idea_ids) >= _MAX_PARALLEL:
                        break  # At capacity
                    if idea_id and idea_id in _active_idea_ids:
                        continue
                    # Try to claim
                    result = api("PATCH", f"/api/agent/tasks/{candidate['id']}", {
                        "status": "running", "worker_id": WORKER_ID,
                    })
                    if result and result.get("status") == "running":
                        if idea_id:
                            _active_idea_ids.add(idea_id)
                        task = result
                        break

            if not task:
                _shutdown_event.wait(15)
                continue

            task_id = task["id"]
            ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
            idea_id = ctx.get("idea_id", "")
            log.info("WORKER[%d] CLAIMED task=%s type=%s idea=%s",
                     worker_id, task_id[:16], task.get("task_type"), (idea_id or "?")[:20])

            # Create worktree — for test/review phases, checkout the impl PR branch
            task_type = task.get("task_type", "spec")
            impl_branch = ctx.get("impl_branch", "")
            workspace_git_url = ctx.get("workspace_git_url", "")
            base_branch = impl_branch if task_type in ("test", "code-review", "review") and impl_branch else None
            wt = _create_worktree(task_id, base_branch=base_branch, idea_id=idea_id,
                                  workspace_git_url=workspace_git_url)
            pushed = False
            try:
                # Fix 6+7: deploy and verify are RUNNER actions, not provider
                if task_type == "deploy":
                    ok = _runner_deploy_phase(task)
                    pushed = True  # deploy pushes main itself
                elif task_type == "verify":
                    ok = _runner_verify_phase(task)
                    pushed = True  # verify is read-only
                elif wt:
                    ok, diff = _run_task_in_worktree(task, wt)
                    # Guard: reject destructive diffs for impl/test (not cleanup/heal)
                    if diff and task_type in ("impl", "test"):
                        add_lines = diff.count("\n+") - diff.count("\n+++")
                        del_lines = diff.count("\n-") - diff.count("\n---")
                        if del_lines > add_lines * 3 and del_lines > 50:
                            log.warning("WORKER[%d] DESTRUCTIVE_DIFF task=%s +%d -%d — rejecting",
                                        worker_id, task_id[:16], add_lines, del_lines)
                            diff = ""  # Treat as no code produced
                            ok = False
                            complete_task(task_id, f"Rejected: diff deletes {del_lines} lines but only adds {add_lines}. Impl must add, not delete.", False)
                    if ok and diff:
                        # Push BRANCH (not main) — code stays on branch until code-review
                        pushed = _push_branch_to_origin(task_id, wt)
                        if not pushed:
                            log.warning("WORKER[%d] BRANCH_PUSH_FAILED task=%s — phase will NOT advance", worker_id, task_id[:16])
                            # Fix 7: tag the task record with push_failed so operators can
                            # distinguish push failures from provider execution errors.
                            _complete_task_with_status(
                                task_id,
                                "Branch push failed after provider completed. Code preserved in worktree.",
                                "failed",
                                {"push_failed": True, "worker_id": WORKER_ID},
                                error_category="push_failed",
                            )
                        else:
                            # Fix 4: phase advance only fires after push is confirmed for impl/test
                            if task_type in ("impl", "test"):
                                _run_phase_auto_advance_hook(task)
                    elif not ok and diff and task_type in ("impl", "test"):
                        # Timed out but produced real code — save the work, push branch
                        log.info("WORKER[%d] TIMEOUT_WITH_CODE task=%s type=%s diff=%d bytes — pushing partial work",
                                 worker_id, task_id[:16], task_type, len(diff))
                        pushed = _push_branch_to_origin(task_id, wt)
                        if pushed:
                            # Record as timed_out (not failed) so retry carries the branch forward
                            complete_task(
                                task_id,
                                f"Timed out but produced code changes (branch pushed). Retry should continue from this branch.",
                                False,
                                context_patch={
                                    "branch_pushed": True,
                                    "diff_size": len(diff),
                                    "diff_content": diff[:5000],  # Actual code for retry carry-over
                                    "partial_timeout": True,
                                },
                            )
                        else:
                            complete_task(
                                task_id,
                                f"Timed out with {len(diff)} bytes of code, but branch push failed.",
                                False,
                                context_patch={"diff_content": diff[:5000], "diff_size": len(diff)},
                            )
                    elif ok and task_type in ("spec", "review", "code-review"):
                        pushed = True  # Text-only phases don't need a diff
                    elif ok and task_type in ("impl", "test"):
                        # impl/test MUST produce code — no diff means provider didn't actually write anything
                        log.warning("WORKER[%d] NO_CODE_PRODUCED task=%s type=%s — marking failed (provider claimed success but wrote no files)",
                                    worker_id, task_id[:16], task_type)
                        ok = False
                        complete_task(task_id, "Provider claimed success but produced no code changes. No git diff detected in worktree.", False)
                    elif ok:
                        pushed = True  # Other phases (heal, etc)

                    # After code-review passes, merge branch to main
                    if ok and pushed and task_type == "code-review":
                        merged = _merge_branch_to_main(task_id)
                        if not merged:
                            log.warning("WORKER[%d] MERGE_TO_MAIN_FAILED task=%s", worker_id, task_id[:16])
                            pushed = False  # Don't advance to deploy if merge failed
                else:
                    if task_type in ("impl", "test"):
                        # impl/test MUST run in worktree — no fallback allowed
                        log.error("WORKER[%d] WORKTREE_REQUIRED task=%s type=%s — cannot run impl/test without worktree, marking failed",
                                  worker_id, task_id[:16], task_type)
                        complete_task(task_id, f"Worktree creation failed. impl/test tasks require an isolated worktree to produce code.", False)
                        ok = False
                    else:
                        log.warning("WORKER[%d] FALLBACK task=%s type=%s (no worktree, text-only OK)", worker_id, task_id[:16], task_type)
                        ok = run_one(task, dry_run=dry_run)
                        pushed = True

                status = "completed" if ok else "failed"
                log.info("WORKER[%d] %s task=%s pushed=%s", worker_id, status.upper(), task_id[:16], pushed)
            except Exception as e:
                log.error("WORKER[%d] ERROR task=%s: %s", worker_id, task_id[:16], e)
            finally:
                # Persist progress sheet before cleanup
                if wt and idea_id:
                    _persist_idea_progress(idea_id, wt)
                # Fix 5: keep worktree if push failed (recovery copy)
                if wt and (pushed or not ok):
                    _cleanup_worktree(task_id)
                elif wt and not pushed:
                    log.warning("WORKER[%d] KEEPING_WORKTREE task=%s (push failed)", worker_id, task_id[:16])
                with _active_lock:
                    _active_idea_ids.discard(idea_id)

        except Exception as e:
            log.error("WORKER[%d] LOOP_ERROR: %s", worker_id, e)
            _shutdown_event.wait(30)


def _recover_in_flight_tasks() -> int:
    """On startup, find tasks already running on this node and track them.

    When the runner restarts (self-update, crash, manual restart), the API
    still shows tasks as 'running' for this node. We must count them toward
    our parallel cap so we don't over-claim.

    Returns the number of recovered in-flight tasks.
    """
    try:
        running = api("GET", "/api/agent/tasks?status=running&limit=100")
        if not running:
            return 0
        task_list = running if isinstance(running, list) else running.get("tasks", [])
        recovered = 0
        for t in task_list:
            claimed = str(t.get("claimed_by") or t.get("worker_id") or "")
            # Match tasks claimed by this node (hostname or node_id prefix)
            if _NODE_ID[:8] not in claimed and _NODE_NAME not in claimed:
                continue
            ctx = t.get("context") if isinstance(t.get("context"), dict) else {}
            idea_id = ctx.get("idea_id", "")
            with _active_lock:
                if idea_id:
                    _active_idea_ids.add(idea_id)
            recovered += 1
            task_type = t.get("task_type", "?")
            if hasattr(task_type, "value"):
                task_type = task_type.value
            log.info("RECOVERED in-flight task=%s type=%s idea=%s",
                     t.get("id", "?")[:16], task_type, (idea_id or "?")[:25])
        return recovered
    except Exception as e:
        log.warning("RECOVER_IN_FLIGHT failed: %s", e)
        return 0


def run_parallel_workers(num_workers: int, dry_run: bool = False) -> list:
    """Start N independent worker threads that each claim and execute tasks.

    Before starting workers, recovers in-flight tasks from the API so the
    parallel cap accounts for tasks left running by a previous instance.
    """
    recovered = _recover_in_flight_tasks()
    available_slots = max(0, num_workers - recovered)
    log.info("PARALLEL_WORKERS recovered=%d in-flight, starting %d workers (cap=%d)",
             recovered, available_slots, num_workers)

    if available_slots == 0:
        log.info("PARALLEL_WORKERS all slots occupied by in-flight tasks — waiting for them to finish")

    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=_worker_loop, args=(i, dry_run), daemon=True, name=f"worker-{i}")
        t.start()
        threads.append(t)
        log.info("WORKER[%d] started", i)

    return threads


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
        _update_pending.set()  # Signal workers to stop claiming new tasks

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

        # Ensure we're on main — worktree branches can't ff-only pull main
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_REPO_DIR),
        ).stdout.strip()
        if current_branch != "main":
            log.info("SELF-UPDATE: on branch '%s', switching to main first", current_branch)
            checkout = subprocess.run(
                ["git", "checkout", "main"],
                capture_output=True, text=True, timeout=15,
                cwd=str(_REPO_DIR),
            )
            if checkout.returncode != 0:
                log.warning("SELF-UPDATE: checkout main failed: %s — trying reset", checkout.stderr.strip())
                subprocess.run(
                    ["git", "checkout", "-B", "main", "origin/main"],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(_REPO_DIR),
                )

        # Pull latest
        pull = subprocess.run(
            ["git", "pull", "origin", "main", "--ff-only"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_REPO_DIR),
        )
        if pull.returncode != 0:
            # ff-only failed — force reset to origin/main
            log.warning("SELF-UPDATE: ff-only pull failed, resetting to origin/main")
            subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                capture_output=True, text=True, timeout=15,
                cwd=str(_REPO_DIR),
            )

        log.info("SELF-UPDATE: pulled latest → %s. Restarting (workers are idle).", remote_sha[:8])

        # Signal workers to stop claiming new tasks during restart
        _shutdown_event.set()

        # Notify the network about the update
        try:
            api("POST", f"/api/federation/nodes/{_NODE_ID}/heartbeat", {
                "status": "updating",
                "local_sha": remote_sha[:10],
                "message": f"Self-update: {local_sha[:8]} → {remote_sha[:8]}. Restarting.",
            })
        except Exception:
            pass  # best-effort notification

        # Kill any remaining child subprocesses (codex, claude, cursor, etc.)
        import signal
        try:
            import psutil
            current = psutil.Process()
            children = current.children(recursive=True)
            for child in children:
                try:
                    child.send_signal(signal.SIGTERM)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Wait briefly for graceful shutdown
            gone, alive = psutil.wait_procs(children, timeout=10)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            log.info("SELF-UPDATE: killed %d child processes (%d graceful, %d forced)",
                     len(children), len(gone), len(alive))
        except ImportError:
            log.warning("SELF-UPDATE: psutil not available — child processes may be orphaned")
        except Exception as e:
            log.warning("SELF-UPDATE: child cleanup error: %s", e)

        # Spawn new process BEFORE exiting, so there's no gap
        new_proc = subprocess.Popen(
            [sys.executable] + sys.argv,
            start_new_session=True,  # Detach from our process group
        )
        log.info("SELF-UPDATE: spawned new runner PID=%d. Exiting old process.", new_proc.pid)

        # Exit cleanly — don't use os.execv which kills daemon threads abruptly
        os._exit(0)

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
    parser.add_argument("--parallel", type=int, default=0,
                        help="Max parallel tasks via worktrees (0=sequential)")
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

    provider_names = list(PROVIDERS.keys())

    log.info("=" * 60)
    log.info("Coherence Network — Node Runner")
    log.info("  node_id:   %s", _NODE_ID)
    log.info("  hostname:  %s", _NODE_NAME)
    log.info("  sha:       %s (origin/main: %s) %s",
             _NODE_GIT.get("local_sha"), _NODE_GIT.get("origin_sha"),
             "up-to-date" if _NODE_GIT.get("up_to_date") == "yes" else "BEHIND origin/main")
    log.info("  providers: %s", provider_names)
    log.info("  api:       %s", API_BASE)
    log.info("  timeout:   %ds", _TASK_TIMEOUT[0])
    log.info("  self_update: %s", "off" if args.no_self_update else "on")
    log.info("  parallel:  %d", args.parallel)
    log.info("=" * 60)

    try:
        from app.services.config_service import resolve_cli_contributor_id

        _rcid, _rsrc = resolve_cli_contributor_id()
        if _rcid:
            log.info("[runner] identity resolved: %s (source: %s)", _rcid, _rsrc)
        else:
            log.warning(
                "[runner] WARNING: no contributor identity configured — all contributions will be anonymous",
            )
            log.warning(
                "[runner] Fix: cc identity set <your_id>  or  export COHERENCE_CONTRIBUTOR_ID=<your_id>",
            )
    except Exception as exc:
        log.debug("Runner identity resolution skipped: %s", exc)

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
        if not args.dry_run:
            push_measurements(_NODE_ID)
        sys.exit(0 if ok else 1)

    if args.loop:
        log.info("Polling every %ds (Ctrl+C to stop)", args.interval)
        _register_node()
        heartbeat_interval = 300  # heartbeat every 5 minutes
        last_heartbeat = 0.0
        reap_interval = 600  # reap stale tasks every 10 minutes
        last_reap = 0.0
        msg_interval = 120  # check messages every 2 minutes
        last_msg_check = 0.0
        cleanup_interval = 1800  # clean stale worktrees every 30 minutes
        last_cleanup = 0.0

        # Reap own stale tasks from previous process
        try:
            stale = api("GET", f"/api/agent/tasks?status=running&limit=50")
            if isinstance(stale, dict):
                own_stale = [
                    t for t in stale.get("tasks", [])
                    if WORKER_ID.split(":")[0] in (t.get("claimed_by") or "")
                ]
                for t in own_stale:
                    api("PATCH", f"/api/agent/tasks/{t['id']}", {
                        "status": "timed_out",
                        "output": f"Reaped on startup: runner restarted while task was running.",
                        "context": {**(t.get("context") or {}), "reaped_on_startup": True},
                    })
                if own_stale:
                    log.info("STARTUP_REAP: marked %d own stale tasks as timed_out", len(own_stale))
        except Exception as e:
            log.warning("STARTUP_REAP failed: %s", e)

        use_parallel = args.parallel > 0
        if use_parallel:
            global _MAX_PARALLEL
            _MAX_PARALLEL = args.parallel
            log.info("PARALLEL MODE: %d independent worker threads", _MAX_PARALLEL)
            worker_threads = run_parallel_workers(_MAX_PARALLEL, dry_run=args.dry_run)

        try:
            _handoff_paused_logged = False

            while True:
                # 1. Handoff check: yield to interactive sessions
                # 1. Housekeeping — ALWAYS runs, even when paused
                if not args.dry_run:
                    now = time.time()

                    # Heartbeat (keeps node visible in federation)
                    if now - last_heartbeat > heartbeat_interval:
                        _send_heartbeat()
                        last_heartbeat = now

                    # Process messages (interactive session needs to receive commands)
                    _process_node_messages(_NODE_ID)

                    # Periodic worktree cleanup
                    if now - last_cleanup > cleanup_interval:
                        _sweep_stale_worktrees(max_age_hours=2)
                        last_cleanup = now

                # 2. Check if interactive session has taken over (pause task execution only)
                _is_paused = False
                _handoff_lock = Path.home() / ".coherence-network" / "executor.lock"
                if _handoff_lock.exists():
                    try:
                        _lock_data = json.loads(_handoff_lock.read_text())
                        _lock_age = time.time() - _lock_data.get("heartbeat", 0)
                        _lock_pid = _lock_data.get("pid", 0)
                        _lock_alive = True
                        if sys.platform == "win32":
                            import ctypes
                            kernel32 = ctypes.windll.kernel32
                            handle = kernel32.OpenProcess(0x100000, False, _lock_pid)  # SYNCHRONIZE
                            _lock_alive = handle != 0
                            if handle:
                                kernel32.CloseHandle(handle)
                        else:
                            try:
                                os.kill(_lock_pid, 0)
                            except (OSError, ProcessLookupError):
                                _lock_alive = False
                        if _lock_data.get("type") == "interactive" and _lock_age < 300 and _lock_alive:
                            _is_paused = True
                            if not _handoff_paused_logged:
                                log.info("PAUSED: interactive session '%s' (PID %d) active — yielding task execution (heartbeat + messages continue)",
                                         _lock_data.get("session_id", "?"), _lock_pid)
                                _handoff_paused_logged = True
                        elif _lock_data.get("type") == "interactive":
                            log.info("RESUMED: interactive lock stale/dead — runner resuming")
                            _handoff_lock.unlink(missing_ok=True)
                    except Exception:
                        pass
                if not _is_paused:
                    _handoff_paused_logged = False

                if _is_paused:
                    time.sleep(args.interval)
                    continue

                # 3. Self-update: check for new commits, but only restart when idle
                if not args.no_self_update:
                    with _active_lock:
                        active = len(_active_idea_ids)
                    if active == 0:
                        if _update_pending.is_set():
                            log.info("SELF-UPDATE: workers drained, proceeding with update")
                        _check_for_updates_and_restart()
                    elif _update_pending.is_set():
                        log.info("SELF-UPDATE: waiting for %d tasks to finish before updating", active)

                # 4. Execute tasks (parallel or sequential)
                if not use_parallel:
                    run_all_pending(dry_run=args.dry_run)
                # else: workers run independently — main loop handles housekeeping only

                # 5. Post-execution housekeeping
                if not args.dry_run:
                    now = time.time()
                    push_measurements(_NODE_ID)
                    if now - last_reap > reap_interval:
                        _reap_stale_tasks(max_age_minutes=15)
                        last_reap = now

                time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Stopped. Pushing final measurements...")
            if not args.dry_run:
                push_measurements(_NODE_ID)
    else:
        # Single run: check for updates first
        if not args.no_self_update:
            _check_for_updates_and_restart()
        results = run_all_pending(dry_run=args.dry_run)
        if not args.dry_run:
            push_measurements(_NODE_ID)
        sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
