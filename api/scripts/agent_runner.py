#!/usr/bin/env python3
"""Agent runner: polls pending tasks, runs commands, PATCHes status.

Usage:
  python scripts/agent_runner.py [--interval 10] [--once] [--verbose] [--workers N]

Requires API running. With Cursor executor, --workers N runs up to N tasks in parallel.
When task reaches needs_decision, runner stops for that task; user replies via /reply.

Debug: Logs to api/logs/agent_runner.log; full output in api/logs/task_{id}.log
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"), override=True)
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")
LOG_DIR = os.path.join(_api_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "agent_runner.log")
# Local models need longer; cloud/Claude typically faster. Default 1h for local, 10min for cloud.
TASK_TIMEOUT = int(os.environ.get("AGENT_TASK_TIMEOUT", "3600"))
HTTP_TIMEOUT = int(os.environ.get("AGENT_HTTP_TIMEOUT", "30"))
MAX_RETRIES = int(os.environ.get("AGENT_HTTP_RETRIES", "3"))
RETRY_BACKOFF = 2  # seconds between retries


def _tool_token(command: str) -> str:
    """Extract best-effort tool token from a shell command."""
    s = (command or "").strip()
    if not s:
        return "unknown"
    # Very simple parse: first token.
    return s.split()[0].strip() or "unknown"


def _scrub_command(command: str) -> str:
    """Best-effort scrub of secrets in command strings before writing to friction notes."""
    s = (command or "").replace("\n", " ").strip()
    if not s:
        return ""
    # Redact common token prefixes.
    redactions = ("gho_", "ghp_", "github_pat_", "sk-", "rk-", "xoxb-", "xoxp-")
    for pref in redactions:
        if pref in s:
            # Keep prefix visible, redact remainder of token chunk.
            parts = s.split(pref)
            rebuilt = parts[0]
            for tail in parts[1:]:
                # Redact until next whitespace.
                rest = tail.split(None, 1)
                redacted = pref + "REDACTED"
                rebuilt += redacted + ((" " + rest[1]) if len(rest) == 2 else "")
            s = rebuilt
    return s[:240]


def _time_cost_per_second() -> float:
    """Convert wall time into an energy loss estimate. Units are relative (not dollars)."""
    try:
        v = float(os.environ.get("PIPELINE_TIME_COST_PER_SECOND", "0.01"))
    except ValueError:
        v = 0.01
    return max(0.0, v)


def _post_runtime_event(
    client: httpx.Client,
    *,
    tool_name: str,
    status_code: int,
    runtime_ms: float,
    task_id: str,
    task_type: str,
    model: str,
    returncode: int,
    output_len: int,
) -> None:
    if os.environ.get("PIPELINE_TOOL_TELEMETRY_ENABLED", "1").strip() in {"0", "false", "False"}:
        return
    payload = {
        "source": "worker",
        "endpoint": f"tool:{tool_name}",
        "method": "RUN",
        "status_code": int(status_code),
        "runtime_ms": max(0.1, float(runtime_ms)),
        "idea_id": "coherence-network-agent-pipeline",
        "metadata": {
            "task_id": task_id,
            "task_type": task_type,
            "model": model,
            "returncode": int(returncode),
            "output_len": int(output_len),
        },
    }
    try:
        client.post(f"{BASE}/api/runtime/events", json=payload, timeout=5.0)
    except Exception:
        # Telemetry should not affect task progression.
        pass


def _post_tool_failure_friction(
    client: httpx.Client,
    *,
    tool_name: str,
    task_id: str,
    task_type: str,
    model: str,
    duration_seconds: float,
    returncode: int,
    command: str,
) -> None:
    if os.environ.get("PIPELINE_TOOL_FAILURE_FRICTION_ENABLED", "1").strip() in {"0", "false", "False"}:
        return
    now = datetime.now(timezone.utc)
    energy_loss = round(max(0.0, float(duration_seconds)) * _time_cost_per_second(), 6)
    cmd_summary = _scrub_command(command)
    payload = {
        "id": f"fr_toolfail_{task_id}_{uuid.uuid4().hex[:8]}",
        "timestamp": now.isoformat(),
        "stage": "agent_runner",
        "block_type": "tool_failure",
        "severity": "high" if duration_seconds >= 120 or returncode != 0 else "medium",
        "owner": "automation",
        "unblock_condition": "Fix tool invocation/dependencies/auth; rerun task",
        "energy_loss_estimate": energy_loss,
        "cost_of_delay": energy_loss,
        "status": "resolved",
        "resolved_at": now.isoformat(),
        "time_open_hours": round(max(0.0, float(duration_seconds)) / 3600.0, 6),
        "resolution_action": "task_marked_failed",
        "notes": f"tool={tool_name} task_id={task_id} task_type={task_type} model={model} returncode={returncode} cmd={cmd_summary}",
    }
    try:
        client.post(f"{BASE}/api/friction/events", json=payload, timeout=5.0)
    except Exception:
        pass


def _setup_logging(verbose: bool = False) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "agent_runner.log")
    log = logging.getLogger("agent_runner")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not log.handlers:
        h = logging.FileHandler(log_file, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        if verbose:
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            log.addHandler(sh)
    return log


def _try_commit(task_id: str, task_type: str, log: logging.Logger) -> None:
    """Run commit_progress.py when PIPELINE_AUTO_COMMIT=1. Non-blocking; logs on failure."""
    import subprocess

    project_root = os.path.dirname(_api_dir)
    script = os.path.join(_api_dir, "scripts", "commit_progress.py")
    push = os.environ.get("PIPELINE_AUTO_PUSH") == "1"
    cmd = [sys.executable, script, "--task-id", task_id, "--task-type", task_type]
    if push:
        cmd.append("--push")
    try:
        r = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and r.stderr:
            log.warning("commit_progress failed: %s", r.stderr[:200])
    except Exception as e:
        log.warning("commit_progress error: %s", e)


def _uses_anthropic_cloud(command: str) -> bool:
    """True if command uses Anthropic cloud (e.g. HEAL with claude-3-5-haiku), not Ollama."""
    if "ollama/" in command:
        return False
    return "claude-3-5" in command or "claude-4" in command


def _uses_cursor_cli(command: str) -> bool:
    """True if command uses Cursor CLI (agent '...'). Cursor uses its own auth."""
    return command.strip().startswith("agent ")


def run_one_task(
    client: httpx.Client,
    task_id: str,
    command: str,
    log: logging.Logger,
    verbose: bool = False,
    task_type: str = "impl",
    model: str = "unknown",
) -> bool:
    """Execute task command, PATCH status. Returns True if completed/failed, False if needs_decision."""
    env = os.environ.copy()
    if _uses_cursor_cli(command):
        # Cursor CLI uses Cursor app auth; ensure OpenAI-compatible env vars for OpenRouter
        env.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        env.setdefault("OPENAI_API_BASE", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        log.info("task=%s using Cursor CLI with OpenRouter", task_id)
    elif _uses_anthropic_cloud(command):
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        env.setdefault("ANTHROPIC_API_KEY", api_key)
        log.info("task=%s using Anthropic cloud has_key=%s", task_id, bool(api_key))
    else:
        env.setdefault("ANTHROPIC_AUTH_TOKEN", "ollama")
        env.setdefault("ANTHROPIC_BASE_URL", "http://localhost:11434")
        env.setdefault("ANTHROPIC_API_KEY", "")
    # Suppress Claude Code requests to unsupported local-model endpoints (GitHub #13949)
    env.setdefault("DISABLE_TELEMETRY", "1")
    env.setdefault("DISABLE_ERROR_REPORTING", "1")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"

    # PATCH to running
    r = client.patch(
        f"{BASE}/api/agent/tasks/{task_id}",
        json={"status": "running", "worker_id": worker_id},
    )
    if r.status_code != 200:
        if r.status_code == 409:
            log.info("task=%s already claimed by another worker; skipping", task_id)
        else:
            log.error("task=%s PATCH running failed status=%s", task_id, r.status_code)
        return True

    start_time = time.monotonic()
    log.info("task=%s starting command=%s", task_id, command[:120])
    if verbose:
        print(f"Running: {command[:80]}...")

    out_file = os.path.join(LOG_DIR, f"task_{task_id}.log")
    output_lines: list[str] = []
    reader_done = threading.Event()

    def _stream_reader(proc: subprocess.Popen) -> None:
        """Read process stdout line-by-line, write to log file + collect output."""
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(f"# task_id={task_id} status=running\n")
                f.write(f"# command={command}\n")
                f.write("---\n")
                f.flush()
                for line in iter(proc.stdout.readline, ""):
                    f.write(line)
                    f.flush()
                    output_lines.append(line)
        except Exception as e:
            output_lines.append(f"\n[stream error: {e}]\n")
        finally:
            reader_done.set()

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            env=env,
            cwd=os.path.dirname(_api_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        reader = threading.Thread(target=_stream_reader, args=(process,), daemon=False)
        reader.start()

        try:
            process.wait(timeout=TASK_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            output_lines.append(f"\n[Timeout {TASK_TIMEOUT}s]\n")

        reader_done.wait(timeout=5)
        reader.join(timeout=2)

        output = "".join(output_lines)
        returncode = process.returncode if process.returncode is not None else -9
        duration_sec = round(time.monotonic() - start_time, 1)
        tool_name = _tool_token(command)

        # Zero/short output on exit 0 is suspicious: likely capture failure or silent crash
        MIN_OUTPUT_CHARS = 10
        output_stripped = (output or "").strip()
        if returncode == 0 and len(output_stripped) < MIN_OUTPUT_CHARS:
            status = "failed"
            output = (
                output
                + f"\n[Pipeline] Marked failed: completed with {len(output_stripped)} chars output (expected >{MIN_OUTPUT_CHARS}). Possible capture failure or silent crash."
            )
        else:
            status = "completed" if returncode == 0 else "failed"

        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"\n# duration_seconds={duration_sec} exit={returncode} status={status}\n")

        # Record tool execution telemetry (cost even when failing).
        sc = 200 if status == "completed" else 500
        _post_runtime_event(
            client,
            tool_name=tool_name,
            status_code=sc,
            runtime_ms=duration_sec * 1000.0,
            task_id=task_id,
            task_type=task_type,
            model=model,
            returncode=returncode,
            output_len=len(output or ""),
        )
        if status != "completed":
            _post_tool_failure_friction(
                client,
                tool_name=tool_name,
                task_id=task_id,
                task_type=task_type,
                model=model,
                duration_seconds=duration_sec,
                returncode=returncode,
                command=command,
            )

        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": status, "output": output[:4000]},
        )
        log.info("task=%s %s exit=%s duration=%.1fs output_len=%d out_file=%s", task_id, status, returncode, duration_sec, len(output), out_file)
        if verbose:
            print(f"  -> {status} (exit {returncode})")

        # Auto-commit progress (spec 030) when PIPELINE_AUTO_COMMIT=1
        if status == "completed" and task_type != "heal" and os.environ.get("PIPELINE_AUTO_COMMIT") == "1":
            _try_commit(task_id, task_type, log)

        return True
    except Exception as e:
        duration_sec = round(time.monotonic() - start_time, 1)  # start_time set before try
        tool_name = _tool_token(command)
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"\n# duration_seconds={duration_sec} exit=-1 status=failed error={e}\n")
        _post_runtime_event(
            client,
            tool_name=tool_name,
            status_code=500,
            runtime_ms=duration_sec * 1000.0,
            task_id=task_id,
            task_type=task_type,
            model=model,
            returncode=-1,
            output_len=len(str(e)),
        )
        _post_tool_failure_friction(
            client,
            tool_name=tool_name,
            task_id=task_id,
            task_type=task_type,
            model=model,
            duration_seconds=duration_sec,
            returncode=-1,
            command=command,
        )
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": str(e)},
        )
        log.exception("task=%s error: %s", task_id, e)
        return True


def poll_and_run(
    client: httpx.Client,
    once: bool = False,
    interval: int = 10,
    workers: int = 1,
    log: logging.Logger = None,
    verbose: bool = False,
) -> None:
    """Poll for pending tasks and run up to workers in parallel (Cursor supports multiple concurrent agent invocations)."""
    log = log or logging.getLogger("agent_runner")
    while True:
        r = _http_with_retry(
            client, "GET", f"{BASE}/api/agent/tasks", log, params={"status": "pending", "limit": workers}
        )
        if r is None:
            if once:
                break
            time.sleep(interval)
            continue
        if r.status_code != 200:
            log.warning("GET tasks failed: %s", r.status_code)
            if once:
                break
            time.sleep(interval)
            continue

        data = r.json()
        tasks = data.get("tasks") or []
        if not tasks:
            if once:
                print("No pending tasks")
                break
            time.sleep(interval)
            continue

        # Fetch full task (including command) for each
        to_run: list[tuple[str, str, str, str]] = []
        for task in tasks:
            task_id = task["id"]
            r2 = _http_with_retry(client, "GET", f"{BASE}/api/agent/tasks/{task_id}", log)
            if r2 is None or r2.status_code != 200:
                log.warning("GET task %s failed: %s", task_id, r2.status_code if r2 else "None")
                continue
            full = r2.json()
            command = full.get("command")
            if not command:
                client.patch(
                    f"{BASE}/api/agent/tasks/{task_id}",
                    json={"status": "failed", "output": "No command"},
                )
                continue
            task_type = str(full.get("task_type", "impl"))
            model = str(full.get("model", "unknown"))
            to_run.append((task_id, command, task_type, model))

        if not to_run:
            if once:
                break
            time.sleep(interval)
            continue

        if workers == 1:
            tid, cmd, tt, m = to_run[0]
            run_one_task(client, tid, cmd, log=log, verbose=verbose, task_type=tt, model=m)
        else:
            with ThreadPoolExecutor(max_workers=len(to_run)) as ex:
                futures = {
                    ex.submit(run_one_task, client, tid, cmd, log, verbose, tt, m): (tid, cmd)
                    for tid, cmd, tt, m in to_run
                }
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        tid, _ = futures[future]
                        log.exception("task=%s worker error: %s", tid, e)

        if once:
            break


def _check_api(client: httpx.Client) -> bool:
    """Verify API is reachable. Returns True if OK."""
    try:
        r = client.get(f"{BASE}/api/health")
        return r.status_code == 200
    except Exception:
        return False


def _http_with_retry(client: httpx.Client, method: str, url: str, log: logging.Logger, **kwargs) -> Optional[httpx.Response]:
    """Make HTTP request with retries for transient connection errors. Returns None on final failure."""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method.upper() == "GET":
                return client.get(url, timeout=HTTP_TIMEOUT, **kwargs)
            if method.upper() == "PATCH":
                return client.patch(url, timeout=HTTP_TIMEOUT, **kwargs)
            if method.upper() == "POST":
                return client.post(url, timeout=HTTP_TIMEOUT, **kwargs)
            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                log.warning("API %s %s failed (attempt %d/%d): %s — retrying in %ds", method, url, attempt, MAX_RETRIES, e, RETRY_BACKOFF)
                time.sleep(RETRY_BACKOFF)
    log.error("API %s %s failed after %d retries: %s", method, url, MAX_RETRIES, last_exc)
    return None


def main():
    ap = argparse.ArgumentParser(description="Agent runner: poll and execute pending tasks")
    ap.add_argument("--interval", type=int, default=10, help="Poll interval (seconds)")
    ap.add_argument("--once", action="store_true", help="Run one task and exit")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print progress to stdout")
    ap.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help="Max parallel tasks (default 1). With Cursor executor, use 2+ to run multiple tasks concurrently.",
    )
    args = ap.parse_args()

    workers = max(1, args.workers)
    log = _setup_logging(verbose=args.verbose)
    log.info("Agent runner started API=%s interval=%s timeout=%ds workers=%d", BASE, args.interval, TASK_TIMEOUT, workers)

    with httpx.Client(timeout=float(HTTP_TIMEOUT)) as client:
        if not _check_api(client):
            msg = f"API not reachable at {BASE}/api/health — start the API first"
            log.error(msg)
            print(msg)
            sys.exit(1)
        if args.verbose:
            print(f"Agent runner | API: {BASE} | interval: {args.interval}s | workers: {workers}")
            print(f"  Log: {LOG_FILE}")
            print("  Polling for pending tasks...\n")

        poll_and_run(
            client, once=args.once, interval=args.interval, workers=workers, log=log, verbose=args.verbose
        )


if __name__ == "__main__":
    main()
