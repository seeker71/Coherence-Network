#!/usr/bin/env python3
"""Run one Claude impl task (pinned spec), wait for terminal state, then write a report.

Flow: create task -> start runner (fresh) with AGENT_TASK_ID -> wait for proof task started
(status=running) -> progress loop every POLL_INTERVAL until completed/failed/needs_decision.

Report includes: proof of file changes (git diff), proof of restartable (log tail, context),
task/spec/idea tracking, and on failure actionable info + usage/tool/friction pointers.

Usage:
  LOCAL_API_URL=http://127.0.0.1:8000 SPEC_ID=auto-get-api-agent-collective-health-7f5865fc \\
    python3 scripts/run_claude_impl_with_report.py

Requires: API running, Claude CLI in PATH, AGENT_AUTO_EXECUTE=0.
If task does not reach status=running within CLAUDE_RUN_STARTED_WAIT (default 90s), script
exits with diagnostics (runner log tail, other pending tasks) so you can fix (e.g. ensure
runner was started with AGENT_TASK_ID).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "api"
DOCS_DIR = REPO_ROOT / "docs"
LOGS_DIR = API_DIR / "logs"

LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://127.0.0.1:8000").rstrip("/")
SPEC_ID = os.environ.get("SPEC_ID", "auto-get-api-agent-collective-health-7f5865fc").strip()
SPEC_TITLE = os.environ.get("SPEC_TITLE", "Auto spec: GET /api/agent/collective-health").strip()
# No time cap by default: wait until task reaches completed/failed/needs_decision. Set CLAUDE_RUN_MAX_WAIT > 0 to cap (seconds).
MAX_WAIT_SECONDS = int(os.environ.get("CLAUDE_RUN_MAX_WAIT", "0"))
POLL_INTERVAL = int(os.environ.get("CLAUDE_RUN_POLL_INTERVAL", "30"))
# Wait up to this long for task to transition to "running" after starting the runner. Only then start the progress loop.
STARTED_WAIT_SECONDS = int(os.environ.get("CLAUDE_RUN_STARTED_WAIT", "90"))
STARTED_POLL_INTERVAL = 2


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str, str]:
    r = subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def _git_state() -> tuple[str, str]:
    code, out, _ = _run(["git", "status", "-s"], timeout=10)
    status = out if code == 0 else ""
    code2, out2, _ = _run(["git", "diff", "--name-only"], timeout=10)
    names = out2 if code2 == 0 else ""
    return status, names


def _git_diff_stat() -> str:
    code, out, _ = _run(["git", "diff", "--stat"], timeout=15)
    return out if code == 0 else ""


def _git_diff_files() -> list[str]:
    _, names, _ = _run(["git", "diff", "--name-only"], timeout=10)
    return [n.strip() for n in names.splitlines() if n.strip()]


def _http_get(path: str, timeout: int = 10) -> dict | list | None:
    import urllib.request

    url = f"{LOCAL_API_URL}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _http_post(path: str, data: dict, timeout: int = 15) -> dict | None:
    import urllib.request

    url = f"{LOCAL_API_URL}{path}"
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def main() -> int:
    print("Pre-state (git)...")
    pre_status, pre_names = _git_state()
    pre_diff_stat = _git_diff_stat()

    direction = (
        f"Implement spec {SPEC_ID} ({SPEC_TITLE}) from spec file. "
        "Follow the spec verification contract, add/update tests for behavior, and run local validation. "
        "Do not modify tests only to force pass."
    )
    payload = {
        "direction": direction,
        "task_type": "impl",
        "context": {
            "executor": "claude",
            "source": "spec_implementation_gap",
            "spec_id": SPEC_ID,
            "spec_title": SPEC_TITLE,
        },
    }

    print("Creating task...")
    task_resp = _http_post("/api/agent/tasks", payload)
    if not task_resp or "id" not in task_resp:
        print("Failed to create task:", task_resp, file=sys.stderr)
        return 1
    task_id = task_resp["id"]
    print(f"Task id: {task_id}")

    env = os.environ.copy()
    env["AGENT_TASK_ID"] = task_id
    env["AGENT_AUTO_GENERATE_IDLE_TASKS"] = "0"
    env["AGENT_TASK_TIMEOUT"] = "0"
    env["AGENT_API_BASE"] = LOCAL_API_URL

    print("Starting runner (fresh process, no timeout)...")
    venv_python = API_DIR / ".venv" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable
    runner_log_path = LOGS_DIR / f"runner_start_{task_id}.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(runner_log_path, "w", encoding="utf-8") as runner_log_file:
        runner = subprocess.Popen(
            [python_exe, "scripts/agent_runner.py", "--once", "--workers", "1", "--interval", "1", "--verbose"],
            cwd=API_DIR,
            env=env,
            stdout=runner_log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    # Wait for proof the task has started (status == "running") before starting the progress loop.
    print(f"Waiting up to {STARTED_WAIT_SECONDS}s for task to start (status=running)...")
    started_deadline = time.monotonic() + STARTED_WAIT_SECONDS
    task_started = False
    while time.monotonic() < started_deadline:
        time.sleep(STARTED_POLL_INTERVAL)
        t = _http_get(f"/api/agent/tasks/{task_id}")
        if not t:
            continue
        last_status = str(t.get("status") or "").strip().lower()
        if last_status == "running":
            task_started = True
            print("Task started (runner claimed it). Starting progress loop.")
            break
        if last_status in ("completed", "failed", "needs_decision"):
            print(f"Task reached terminal state before we saw 'running': {last_status}")
            task_started = True
            break
        print(f"  ... status={last_status} (waiting for running)")

    if not task_started:
        print("Task did not transition to 'running'. Diagnosing...")
        t = _http_get(f"/api/agent/tasks/{task_id}") or {}
        pending = _http_get("/api/agent/tasks?status=pending&limit=10")
        pending_ids = []
        if isinstance(pending, dict):
            for x in pending.get("tasks") or []:
                if x.get("id"):
                    pending_ids.append(x.get("id"))
        print(f"  Task status: {t.get('status')}")
        print(f"  Other pending task ids: {pending_ids[:5]}")
        print(f"  Runner log (last 40 lines): {runner_log_path}")
        if runner_log_path.exists():
            lines = runner_log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            for line in lines:
                print(f"    {line}")
        print("  Possible causes: runner picked another task (no AGENT_TASK_ID?), API unreachable, runner crash. Check api/logs/agent_runner.log and runner_start_*.log")
        runner.terminate()
        try:
            runner.wait(timeout=10)
        except subprocess.TimeoutExpired:
            runner.kill()
            runner.wait()
        return 1

    # Progress loop: poll every POLL_INTERVAL until terminal state.
    deadline = time.monotonic() + MAX_WAIT_SECONDS if MAX_WAIT_SECONDS > 0 else None
    last_status = str((_http_get(f"/api/agent/tasks/{task_id}") or {}).get("status") or "running").strip().lower()
    while True:
        time.sleep(POLL_INTERVAL)
        if deadline is not None and time.monotonic() >= deadline:
            print("Max wait reached; task still running. Report will show progress and how to resume.")
            break
        t = _http_get(f"/api/agent/tasks/{task_id}")
        if not t:
            continue
        last_status = str(t.get("status") or "").strip().lower()
        progress = t.get("progress_pct")
        step = t.get("current_step") or ""
        print(f"  status={last_status} progress={progress} step={step[:50]}")
        if last_status in ("completed", "failed", "needs_decision"):
            break

    if runner.poll() is None:
        runner.terminate()
        try:
            runner.wait(timeout=15)
        except subprocess.TimeoutExpired:
            runner.kill()
            runner.wait()

    # Collect evidence
    task = _http_get(f"/api/agent/tasks/{task_id}") or {}
    ctx = task.get("context") or {}
    output = (task.get("output") or "")[-4000:]
    log_path = LOGS_DIR / f"task_{task_id}.log"
    log_tail = ""
    if log_path.exists():
        try:
            log_tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            log_tail = "\n".join(log_tail)
        except Exception:
            log_tail = "(read error)"

    post_status, post_names = _git_state()
    post_diff_stat = _git_diff_stat()
    changed_files = _git_diff_files()

    runtime_events = _http_get(f"/api/runtime/events?limit=50") or []
    task_events = [e for e in (runtime_events if isinstance(runtime_events, list) else []) if (e.get("metadata") or {}).get("task_id") == task_id]

    friction = _http_get("/api/friction/events?status=open&limit=20") or []

    report_path = DOCS_DIR / f"CLAUDE_RUN_REPORT_{task_id}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Claude run report — {task_id}\n\n")
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}Z\n\n")
        f.write(f"- **Spec:** `{SPEC_ID}` — {SPEC_TITLE}\n")
        f.write(f"- **Task:** `{task_id}`\n")
        f.write(f"- **Status:** {last_status}\n\n")

        f.write("## Tracking (task / spec / idea)\n\n")
        f.write(f"- **Task context spec_id:** `{ctx.get('spec_id', '')}`\n")
        f.write(f"- **Task context idea_id:** `{ctx.get('idea_id', '')}`\n")
        f.write(f"- **Task context source:** `{ctx.get('source', '')}`\n")
        f.write(f"- **Runtime events for this task:** {len(task_events)} (GET `/api/runtime/events`, filter `metadata.task_id={task_id}`)\n")
        f.write(f"- **Usage:** GET `/api/agent/usage` or `/usage` page for tool/executor usage.\n")
        f.write(f"- **Friction (open):** {len(friction) if isinstance(friction, list) else 0} (GET `/api/friction/events?status=open`)\n\n")

        f.write("## Proof of file changes\n\n")
        if changed_files:
            f.write("**Files changed (git diff --name-only):**\n\n")
            for name in changed_files:
                f.write(f"- `{name}`\n")
            f.write("\n**Diff stat:**\n\n```\n")
            f.write(post_diff_stat or "(none)")
            f.write("\n```\n\n")
        else:
            f.write("No new changes in working tree from this run (or run did not complete successfully).\n\n")

        f.write("## Proof of restartable / progress\n\n")
        f.write(f"- **Task log file:** `api/logs/task_{task_id}.log`\n")
        f.write(f"- **context.resumable:** `{ctx.get('resumable', '')}`\n")
        f.write(f"- **context.timeout_snapshot_at:** `{ctx.get('timeout_snapshot_at', '')}`\n")
        f.write(f"- **context.partial_output_len:** `{ctx.get('partial_output_len', '')}`\n")
        f.write(f"- **progress_pct:** `{task.get('progress_pct')}` | **current_step:** `{task.get('current_step')}`\n\n")
        f.write("**Log tail (last 80 lines):**\n\n```\n")
        f.write(log_tail or "(no log file)")
        f.write("\n```\n\n")

        if last_status != "completed":
            f.write("## Failure / non-complete: actionable information\n\n")
            f.write(f"- **Status:** `{last_status}`\n")
            f.write(f"- **Failure class / context:** check task `context.executor_policy`, `context.target_state_observation`\n")
            f.write("- **Full task:** `GET /api/agent/tasks/{task_id}`\n")
            f.write("- **Full output:** truncated in API; full in `api/logs/task_{task_id}.log`\n\n")
            f.write("**Output tail:**\n\n```\n")
            f.write(output[-2500:] if output else "(empty)")
            f.write("\n```\n\n")
            f.write("**How to fix / resume:**\n")
            f.write("1. Inspect task log and output above for errors (auth, timeout, command not found, etc.).\n")
            f.write("2. Fix environment (Claude CLI, OAuth, PATH) or spec/test issues.\n")
            f.write("3. To retry same task: PATCH task status back to `pending` so runner picks it up again.\n")
            f.write("4. Check usage/friction: GET `/api/agent/usage`, GET `/api/friction/events?status=open`.\n")

    print(f"Report written: {report_path}")
    return 0 if last_status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
