#!/usr/bin/env python3
"""Pipeline visibility: what's running, pending (how long), completed (duration), models, prompts.

Usage:
  .venv/bin/python scripts/check_pipeline.py [--task-id ID] [--log] [--json]
  --task-id ID  Show full log for task (prompt + response)
  --log         Include last 20 lines of running task's log if available
  --json        Output pipeline-status as JSON (for scripting)
"""

import argparse
import json
import os
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"), override=True)
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")


def _read_log_tail(task_id: str, n: int = 20) -> list:
    """Read last n non-empty lines from task log file."""
    p = os.path.join(_api_dir, "logs", f"task_{task_id}.log")
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f.readlines() if ln.strip()]
        return lines[-n:]
    except Exception:
        return []


def _fmt_seconds(s):
    if s is None:
        return "—"
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s}s"
    h, m = divmod(m, 60)
    return f"{h}h{m}m"


def main():
    ap = argparse.ArgumentParser(description="Pipeline visibility")
    ap.add_argument("--task-id", help="Show full log for task")
    ap.add_argument("--log", action="store_true", help="Include log preview for running task")
    ap.add_argument("--json", action="store_true", help="Output pipeline-status as JSON")
    args = ap.parse_args()

    if args.task_id:
        try:
            r = httpx.get(f"{BASE}/api/agent/tasks/{args.task_id}/log", timeout=10)
            if r.status_code != 200:
                print(f"Error: {r.status_code} — {r.text[:200]}")
                sys.exit(1)
            d = r.json()
            print(f"Task: {d['task_id']}")
            print("=" * 60)
            if d.get("command"):
                print("COMMAND (prompt):")
                print(d["command"][:2000])
                if len(d.get("command", "")) > 2000:
                    print("... [truncated]")
            print()
            if d.get("output"):
                print("OUTPUT (from API, may be truncated):")
                print(d["output"][:2000])
                if len(d.get("output", "")) > 2000:
                    print("... [truncated]")
            print()
            if d.get("log"):
                print("FULL LOG (from file):")
                print(d["log"])
            return
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    try:
        r = httpx.get(f"{BASE}/api/agent/pipeline-status", timeout=10)
        if r.status_code == 404:
            print("Pipeline-status endpoint not found (404). Restart API: ./scripts/start_with_telegram.sh")
            # Fallback: show basic task list
            r2 = httpx.get(f"{BASE}/api/agent/tasks", params={"limit": 10}, timeout=10)
            if r2.status_code == 200:
                j = r2.json()
                tasks = j.get("tasks", [])
                run = [t for t in tasks if t.get("status") == "running"]
                pend = [t for t in tasks if t.get("status") == "pending"]
                print(f"  Running: {len(run)}  Pending: {len(pend)}")
                for t in run[:2]:
                    print(f"    • {t['id']} ({t.get('task_type')}) {t.get('model', '')}")
            sys.exit(1)
        if r.status_code != 200:
            print(f"API error: {r.status_code}")
            sys.exit(1)
        data = r.json()
    except httpx.ConnectError as e:
        print(f"API not reachable: {e}")
        print("Start the API: ./scripts/start_with_telegram.sh")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    print("Pipeline Status")
    print("=" * 60)

    # Running
    running = data.get("running") or []
    if running:
        t = running[0]
        print(f"RUNNING: {t['id']} ({t['task_type']}) | model: {t['model']}")
        print(f"  Duration: {_fmt_seconds(t.get('running_seconds'))}")
        print(f"  Direction: {(t.get('direction') or '')[:70]}...")
        # Live tail from streamed log (agent_runner writes incrementally)
        tail = t.get("live_tail") or _read_log_tail(t["id"], 25)
        if tail:
            print(f"  Live output (last {len(tail)} lines):")
            for line in tail[-18:]:
                print(f"    {line[:90]}")
    else:
        print("RUNNING: —")

    # Pending
    pending = data.get("pending") or []
    print(f"\nPENDING: {len(pending)} tasks")
    for t in pending[:8]:
        wait = _fmt_seconds(t.get("wait_seconds"))
        print(f"  • {t['id']} ({t['task_type']}) | wait: {wait} | {(t.get('direction') or '')[:50]}...")

    # Recent completed
    completed = data.get("recent_completed") or []
    print(f"\nRECENT COMPLETED: {len(completed)}")
    for t in completed[:5]:
        dur = _fmt_seconds(t.get("duration_seconds"))
        out_len = t.get("output_len", 0)
        print(f"  • {t['id']} ({t['task_type']}) | duration: {dur} | output: {out_len} chars")

    # PM state
    pm = data.get("project_manager")
    if pm:
        print(f"\nPROJECT MANAGER: item {pm.get('backlog_index', '?')}, phase={pm.get('phase', '?')}")
        if pm.get("current_task_id"):
            print(f"  Waiting on: {pm['current_task_id']}")
        if pm.get("blocked"):
            print("  (blocked by needs_decision)")

    # Latest LLM request/response
    req = data.get("latest_request")
    resp = data.get("latest_response")
    if req or resp:
        print("\n--- Latest LLM activity ---")
        if req:
            d = (req.get("direction") or "")[:120]
            print(f"REQUEST ({req.get('task_id', '')} [{req.get('status', '')}]): {d}{'...' if len(req.get('direction') or '') > 120 else ''}")
            cmd = (req.get("prompt_preview") or "")[:400]
            if cmd:
                print(f"  Cmd: {cmd}{'...' if len(req.get('prompt_preview') or '') > 400 else ''}")
        if resp:
            prev = (resp.get("output_preview") or "").strip()
            print(f"RESPONSE ({resp.get('task_id', '')} [{resp.get('status', '')}], {resp.get('output_len', 0)} chars):")
            if prev:
                for line in prev.split("\n")[:10]:
                    print(f"  {line[:85]}")
                if len(prev) > 800:
                    print("  ... [truncated]")
            else:
                print("  (empty)")
        print("---")

    print()
    print("Full task log: .venv/bin/python scripts/check_pipeline.py --task-id TASK_ID")
    print("Ollama request count: check Ollama/GIN logs (each POST /v1/messages = 1 turn)")


if __name__ == "__main__":
    main()
