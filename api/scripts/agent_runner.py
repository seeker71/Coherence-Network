#!/usr/bin/env python3
"""Agent runner: polls pending tasks, runs commands, PATCHes status.

Usage:
  python scripts/agent_runner.py [--interval 10] [--once]

Requires API running. Runs one task at a time. When task reaches needs_decision,
runner stops for that task; user replies via /reply. MVP: no auto-resume.
"""

import argparse
import os
import subprocess
import sys
import time

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")


def run_one_task(client: httpx.Client, task_id: str, command: str) -> bool:
    """Execute task command, PATCH status. Returns True if completed/failed, False if needs_decision."""
    env = os.environ.copy()
    env.setdefault("ANTHROPIC_AUTH_TOKEN", "ollama")
    env.setdefault("ANTHROPIC_BASE_URL", "http://localhost:11434")
    env.setdefault("ANTHROPIC_API_KEY", "")

    # PATCH to running
    r = client.patch(f"{BASE}/api/agent/tasks/{task_id}", json={"status": "running"})
    if r.status_code != 200:
        print(f"PATCH running failed: {r.status_code}")
        return True

    print(f"Running: {command[:80]}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            env=env,
            cwd=os.path.dirname(_api_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = (result.stdout or "") + (result.stderr or "")
        status = "completed" if result.returncode == 0 else "failed"
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": status, "output": output[:4000]},
        )
        print(f"  -> {status} (exit {result.returncode})")
        return True
    except subprocess.TimeoutExpired:
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "Timeout 300s"},
        )
        print("  -> failed (timeout)")
        return True
    except Exception as e:
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": str(e)},
        )
        print(f"  -> failed: {e}")
        return True


def poll_and_run(client: httpx.Client, once: bool = False, interval: int = 10) -> None:
    """Poll for pending tasks and run one at a time."""
    while True:
        r = client.get(f"{BASE}/api/agent/tasks", params={"status": "pending", "limit": 1})
        if r.status_code != 200:
            print(f"GET tasks failed: {r.status_code}")
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

        task = tasks[0]
        task_id = task["id"]
        # List doesn't include command; fetch full task
        r2 = client.get(f"{BASE}/api/agent/tasks/{task_id}")
        if r2.status_code != 200:
            print(f"GET task {task_id} failed: {r2.status_code}")
            continue
        full = r2.json()
        command = full.get("command")
        if not command:
            # Skip malformed
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={"status": "failed", "output": "No command"},
            )
            continue

        run_one_task(client, task_id, command)
        if once:
            break


def main():
    ap = argparse.ArgumentParser(description="Agent runner: poll and execute pending tasks")
    ap.add_argument("--interval", type=int, default=10, help="Poll interval (seconds)")
    ap.add_argument("--once", action="store_true", help="Run one task and exit")
    args = ap.parse_args()

    print(f"Agent runner | API: {BASE} | interval: {args.interval}s\n")

    with httpx.Client(timeout=30.0) as client:
        poll_and_run(client, once=args.once, interval=args.interval)


if __name__ == "__main__":
    main()
