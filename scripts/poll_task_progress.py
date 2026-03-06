#!/usr/bin/env python3
"""Poll a task every minute and print progress until it reaches a terminal state."""
import json
import os
import sys
import time
import urllib.request

TASK_ID = os.environ.get("TASK_ID", "").strip()
API = os.environ.get("LOCAL_API_URL", "http://127.0.0.1:8000").rstrip("/")
INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "60"))
# Wait up to this long for task to show status=running before starting the progress loop.
STARTED_WAIT_SEC = int(os.environ.get("CLAUDE_RUN_STARTED_WAIT", "90"))
STARTED_POLL_SEC = 2

if not TASK_ID:
    print("Set TASK_ID=task_xxx", file=sys.stderr)
    sys.exit(1)


def get_task():
    url = f"{API}/api/agent/tasks/{TASK_ID}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": str(e)}


def main():
    # Wait for proof the task has started (status == "running") before progress loop.
    print(f"Waiting up to {STARTED_WAIT_SEC}s for task to start (status=running)...", flush=True)
    deadline = time.monotonic() + STARTED_WAIT_SEC
    while time.monotonic() < deadline:
        time.sleep(STARTED_POLL_SEC)
        t = get_task()
        if "_error" in t:
            continue
        status = str(t.get("status") or "").strip()
        if status == "running":
            print("Task started (runner claimed it). Starting progress loop.", flush=True)
            break
        if status in ("completed", "failed", "needs_decision"):
            print(f"Task already in terminal state: {status}. Exiting.", flush=True)
            return
        print(f"  ... status={status} (waiting for running)", flush=True)
    else:
        print("Task did not transition to 'running'. Check runner (AGENT_TASK_ID?) and api/logs.", flush=True)
        return

    minute = 0
    while True:
        minute += 1
        t = get_task()
        if "_error" in t:
            print(f"--- Minute {minute} --- Error: {t['_error']}")
            time.sleep(INTERVAL)
            continue
        status = str(t.get("status") or "").strip()
        progress = t.get("progress_pct")
        step = (t.get("current_step") or "")[:70]
        ctx = t.get("context") or {}
        tail = (ctx.get("runner_log_tail") or "").strip().split("\n")[-5:]
        tail = "\n    ".join(tail) if tail else ""

        print(f"--- Minute {minute} --- {time.strftime('%H:%M:%S', time.gmtime())} UTC", flush=True)
        print(f"  status={status}  progress_pct={progress}  current_step={step}", flush=True)
        if tail:
            print("  log_tail (last 5):", flush=True)
            print(f"    {tail}", flush=True)

        if status in ("completed", "failed", "needs_decision"):
            print("  -> Terminal state reached. Done.", flush=True)
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
