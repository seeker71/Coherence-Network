#!/usr/bin/env python3
"""Local task runner: claims tasks, picks provider via Thompson Sampling, executes.

Provider selection is data-driven — SlotSelector("provider_{task_type}") picks
based on measured success rates. No hardcoded routing. New providers get
exploration boost, failures reduce selection probability.

Available providers are auto-detected from installed CLIs.

Usage:
  python scripts/local_runner.py                    # run all pending tasks once
  python scripts/local_runner.py --task TASK_ID     # run one specific task
  python scripts/local_runner.py --loop --interval 30  # poll continuously
  python scripts/local_runner.py --dry-run          # show what would run
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Resolve paths
_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent
_REPO_DIR = _API_DIR.parent
_LOG_DIR = _API_DIR / "logs"
sys.path.insert(0, str(_API_DIR))

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
API_BASE = os.environ.get("AGENT_API_BASE", "https://api.coherencycoin.com")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_TASK_TIMEOUT = [int(os.environ.get("AGENT_TASK_TIMEOUT", "300"))]


# ── Provider registry (auto-detected) ───────────────────────────────

def _detect_providers() -> dict[str, dict]:
    """Auto-detect available providers on this machine.

    Every provider is equal — CLI or API, all treated the same by Thompson Sampling.
    CLIs are detected by binary presence; API providers by reachability.
    """
    providers = {}
    cli_specs = {
        # claude --print: non-interactive, prints output
        "claude": {"cmd": ["claude", "--print", "--dangerously-skip-permissions"], "append_prompt": True},
        # codex exec --full-auto: non-interactive sandboxed execution
        "codex": {"cmd": ["codex", "exec", "--full-auto"], "append_prompt": True},
        # gemini -y -p <prompt>: yolo mode (auto-approve tools) + headless
        # -y is required: without it, tool calls block on approval (issue #12362)
        "gemini": {"cmd": ["gemini", "-y", "-p"], "append_prompt": True},
        # cursor agent -p: Cursor's headless agent mode
        "cursor": {"cmd": ["agent", "-p"], "append_prompt": True, "check_binary": "agent"},
        # ollama-local: local LLM (best available model)
        "ollama-local": {
            "cmd": ["ollama", "run"], "append_prompt": True,
            "check": _check_ollama_local, "model_select": _select_ollama_model,
        },
        # ollama-cloud: ollama cloud models (glm-5, etc.)
        "ollama-cloud": {
            "cmd": ["ollama", "run"], "append_prompt": True,
            "check": _check_ollama_cloud, "model_select": _select_ollama_cloud_model,
        },
    }
    for name, spec in cli_specs.items():
        binary = spec.pop("check_binary", None) or spec["cmd"][0]
        if not shutil.which(binary):
            log.debug("Provider not found: %s (%s)", name, binary)
            continue
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
            log.info("Provider detected: %s (%s)", name, shutil.which(binary))
        providers[name] = spec

    # API-based providers (no CLI binary needed)
    if _check_openrouter():
        providers["openrouter"] = {"api": True, "model": "openrouter/auto"}
        log.info("Provider detected: openrouter (API, free tier)")

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
        return any(":cloud" not in line for line in lines if line.strip())
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
        return any(":cloud" in line for line in result.stdout.split("\n"))
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
            if name and ":cloud" not in name:
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
            if parts and ":cloud" in parts[0]:
                return parts[0]
        return None
    except Exception:
        return None


def _check_openrouter() -> bool:
    """Check if OpenRouter API is reachable (free tier, no key required)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "https://openrouter.ai/api/v1/models"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() == "200"
    except Exception:
        return False


def _run_openrouter(prompt: str, cwd: str, timeout: int) -> tuple[bool, str, float]:
    """Execute via OpenRouter API (free tier). Returns (success, output, duration)."""
    start = time.time()
    try:
        sys.path.insert(0, str(_API_DIR))
        from app.services.openrouter_client import chat_completion
        content, usage, meta = chat_completion(
            model="openrouter/auto",  # auto-routes to best free model
            prompt=prompt,
            timeout_s=float(timeout),
        )
        duration = time.time() - start
        return True, content, duration
    except Exception as e:
        duration = time.time() - start
        return False, f"OpenRouter error: {e}", duration


PROVIDERS: dict[str, dict] = {}  # populated at startup


def select_provider(task_type: str) -> str:
    """Select provider via Thompson Sampling based on task outcome data."""
    available = list(PROVIDERS.keys())
    if not available:
        raise RuntimeError("No providers available")
    if len(available) == 1:
        return available[0]

    try:
        from app.services.slot_selection_service import SlotSelector
        selector = SlotSelector(f"provider_{task_type}")
        selected = selector.select(available)
        if selected:
            log.info("PROVIDER_SELECT task_type=%s selected=%s from=%s (Thompson Sampling)",
                     task_type, selected, available)
            return selected
    except Exception:
        log.warning("Thompson Sampling failed for provider selection, using round-robin", exc_info=True)

    # Fallback: simple rotation based on time
    import hashlib
    h = int(hashlib.md5(f"{time.time()}".encode()).hexdigest(), 16)
    selected = available[h % len(available)]
    log.info("PROVIDER_SELECT task_type=%s selected=%s (fallback)", task_type, selected)
    return selected


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
    error_class = None if success else classify_error(output)

    try:
        from app.services.slot_selection_service import SlotSelector
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
    except Exception:
        log.warning("Failed to record provider outcome", exc_info=True)


def get_provider_stats() -> dict:
    """Get current provider selection stats for all task types."""
    try:
        from app.services.slot_selection_service import SlotSelector
        available = list(PROVIDERS.keys())
        stats = {}
        for task_type in ["spec", "test", "impl", "review", "heal"]:
            selector = SlotSelector(f"provider_{task_type}")
            stats[task_type] = selector.stats(available)
        return stats
    except Exception:
        return {}


# ── API calls ────────────────────────────────────────────────────────

def api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    """Call the API via curl."""
    url = f"{API_BASE}{path}"
    cmd = ["curl", "-s", "-X", method, url, "-H", "Content-Type: application/json"]
    if body:
        cmd += ["-d", json.dumps(body)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if not result.stdout.strip():
            log.error("API %s %s → empty response", method, path)
            return None
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        log.error("API %s %s → bad JSON: %s", method, path, result.stdout[:200])
        return None
    except Exception as e:
        log.error("API %s %s failed: %s", method, path, e)
        return None


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


# ── Execution ────────────────────────────────────────────────────────

def build_prompt(task: dict) -> str:
    direction = task.get("direction", "")
    task_type = task.get("task_type", "unknown")
    context = task.get("context", {}) or {}
    agent = context.get("task_agent", "dev-engineer")

    return f"""You are acting as a {agent} for the Coherence Network project.

Task type: {task_type}
Task ID: {task.get('id', 'unknown')}

Direction:
{direction}

Work in the repository at {_REPO_DIR}. Follow the project's CLAUDE.md conventions.

Output a summary: files created/modified, validation results, errors encountered."""


def execute_with_provider(provider: str, prompt: str) -> tuple[bool, str, float]:
    """Run prompt through a provider (CLI or API). Returns (success, output, duration)."""
    spec = PROVIDERS[provider]

    # API-based providers (openrouter)
    if spec.get("api"):
        return _run_openrouter(prompt, str(_REPO_DIR), _TASK_TIMEOUT[0])

    cmd = list(spec["cmd"])
    stdin_input = None

    if spec.get("stdin_prompt"):
        # ollama-style: prompt via stdin
        stdin_input = prompt
    elif spec.get("append_prompt"):
        cmd.append(prompt)

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, input=stdin_input,
            timeout=_TASK_TIMEOUT[0], cwd=str(_REPO_DIR),
        )
        duration = time.time() - start
        output = result.stdout or result.stderr or "(no output)"
        return result.returncode == 0, output, duration

    except subprocess.TimeoutExpired as e:
        duration = time.time() - start
        # Capture whatever partial output exists — this is diagnostic value
        partial_stdout = getattr(e, "stdout", None) or ""
        partial_stderr = getattr(e, "stderr", None) or ""
        diagnostic = f"TIMEOUT after {duration:.0f}s (limit={_TASK_TIMEOUT[0]}s)\n"
        if partial_stdout:
            diagnostic += f"--- partial stdout ({len(partial_stdout)} chars) ---\n{partial_stdout[-2000:]}\n"
        if partial_stderr:
            diagnostic += f"--- partial stderr ({len(partial_stderr)} chars) ---\n{partial_stderr[-2000:]}\n"
        if not partial_stdout and not partial_stderr:
            # Blind timeout — zero diagnostic value. This MUST bubble up.
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

    # Select provider (data-driven)
    provider = select_provider(task_type)

    if dry_run:
        log.info("DRY RUN task=%s type=%s provider=%s", task_id, task_type, provider)
        return True

    # Execute
    prompt = build_prompt(task)
    log.info("EXECUTING task=%s type=%s provider=%s", task_id, task_type, provider)

    success, output, duration = execute_with_provider(provider, prompt)

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

    # Report to API
    complete_task(task_id, output, success, {
        "worker_id": WORKER_ID,
        "provider": provider,
        "duration_s": round(duration, 1),
    })

    log.info("OUTCOME task=%s type=%s provider=%s success=%s duration=%.1fs",
             task_id, task_type, provider, success, duration)
    return success


def run_all_pending(dry_run: bool = False) -> dict:
    tasks = list_pending()
    if not tasks:
        log.info("No pending tasks")
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


def main():
    parser = argparse.ArgumentParser(description="Task runner — data-driven provider selection")
    parser.add_argument("--task", help="Run a specific task ID")
    parser.add_argument("--loop", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--timeout", type=int, default=_TASK_TIMEOUT[0], help="Task timeout (seconds)")
    parser.add_argument("--stats", action="store_true", help="Show provider stats and exit")
    args = parser.parse_args()

    _TASK_TIMEOUT[0] = args.timeout

    # Detect providers
    global PROVIDERS
    PROVIDERS = _detect_providers()
    if not PROVIDERS:
        log.error("No provider CLIs found. Install claude, codex, cursor, or gemini.")
        sys.exit(1)

    log.info("Runner starting: api=%s worker=%s timeout=%ds providers=%s",
             API_BASE, WORKER_ID, _TASK_TIMEOUT[0], list(PROVIDERS.keys()))

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
        try:
            while True:
                run_all_pending(dry_run=args.dry_run)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Stopped")
    else:
        results = run_all_pending(dry_run=args.dry_run)
        sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
