#!/usr/bin/env python3
"""Create an agent task via API and optionally run the command.

Usage:
  python scripts/test_agent_run.py [--run] [direction]
  python scripts/test_agent_run.py --run "Add a test endpoint GET /api/ping"

Requires API running. Default direction: "Reply with exactly: agent-test-ok"
"""

import argparse
import os
import subprocess
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))  # project root for claude cwd

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")
DEFAULT_DIRECTION = "Reply with exactly: agent-test-ok"


def main():
    ap = argparse.ArgumentParser(description="Create agent task and optionally run command")
    ap.add_argument("direction", nargs="?", default=DEFAULT_DIRECTION, help="Task direction")
    ap.add_argument("--run", action="store_true", help="Execute the command (default: print only)")
    ap.add_argument("--task-type", default="impl", choices=["spec", "test", "impl", "review", "heal"])
    ap.add_argument("--model", help="Override model in command (e.g. granite3.3:latest)")
    args = ap.parse_args()

    print("=== Agent run test ===\n")
    print(f"API: {BASE}")
    print(f"Direction: {args.direction[:60]}...")
    print()

    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BASE}/api/agent/tasks",
            json={"direction": args.direction, "task_type": args.task_type},
        )
        if r.status_code != 201:
            print(f"API error: {r.status_code} {r.text}")
            sys.exit(1)

        task = r.json()
        task_id = task["id"]
        command = task["command"]
        model = task["model"]

        if args.model:
            import re
            command = re.sub(r"--model\s+\S+", f"--model {args.model}", command)
            print(f"Model override: {args.model}")

        print(f"Task: {task_id}")
        print(f"Model: {model}")
        print(f"Command: {command}\n")

        if not args.run:
            print("Dry run. Use --run to execute.")
            return

        # Set env for Claude + Ollama
        env = os.environ.copy()
        env.setdefault("ANTHROPIC_AUTH_TOKEN", "ollama")
        env.setdefault("ANTHROPIC_BASE_URL", "http://localhost:11434")
        env.setdefault("ANTHROPIC_API_KEY", "")

        # PATCH to running
        c.patch(f"{BASE}/api/agent/tasks/{task_id}", json={"status": "running"})

        print("Running...\n")
        try:
            result = subprocess.run(
                command,
                shell=True,
                env=env,
                cwd=os.path.dirname(_api_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = (result.stdout or "") + (result.stderr or "")
            status = "completed" if result.returncode == 0 else "failed"
            c.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={"status": status, "output": output[:2000]},
            )
            print(output[:1500])
            print(f"\nExit: {result.returncode} -> {status}")
        except subprocess.TimeoutExpired:
            c.patch(f"{BASE}/api/agent/tasks/{task_id}", json={"status": "failed", "output": "Timeout"})
            print("Timeout")
            sys.exit(1)
        except Exception as e:
            c.patch(f"{BASE}/api/agent/tasks/{task_id}", json={"status": "failed", "output": str(e)})
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
