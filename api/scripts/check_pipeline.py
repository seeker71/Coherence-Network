#!/usr/bin/env python3
"""Pipeline visibility: what's running, pending (how long), completed (duration), models, prompts.

Usage:
  .venv/bin/python scripts/check_pipeline.py [--task-id ID] [--log] [--json] [--attention] [--hierarchical | --flat]
  --task-id ID  Show full log for task (prompt + response)
  --log         Include last 20 lines of running task's log if available
  --json        Output pipeline-status as JSON (for scripting)
  --attention  Print attention flags (stuck, repeated_failures, low_success_rate) in human-readable form
  --hierarchical  Explicitly use hierarchical view (Goal → PM → Tasks → Artifacts). Default for human-readable.
  --flat       Legacy flat output (sections not strictly layered).
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
PROJECT_ROOT = os.path.dirname(_api_dir)

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


def _get_pipeline_process_args():
    """Return {runner_workers: int|None, pm_parallel: bool|None} from ps."""
    out = {"runner_workers": None, "pm_parallel": None}
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            return out
        for line in (r.stdout or "").strip().splitlines():
            if "agent_runner" in line and "python" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p in ("--workers", "-w") and i + 1 < len(parts):
                        try:
                            out["runner_workers"] = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
                if out["runner_workers"] is None:
                    out["runner_workers"] = 1
                break
        for line in (r.stdout or "").strip().splitlines():
            if "project_manager" in line and "python" in line:
                out["pm_parallel"] = " --parallel " in (" " + line) or line.rstrip().endswith(" --parallel")
                break
    except Exception:
        pass
    return out


def _fetch_status_report() -> Optional[dict]:
    """GET /api/agent/status-report. Returns None on error or unreachable."""
    try:
        r = httpx.get(f"{BASE}/api/agent/status-report", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_effectiveness() -> Optional[dict]:
    """GET /api/agent/effectiveness. Returns None on error or unreachable."""
    try:
        r = httpx.get(f"{BASE}/api/agent/effectiveness", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _build_hierarchical_from_data(data: dict, effectiveness: Optional[dict], proc: dict) -> dict:
    """Build hierarchical dict (layer_0_goal … layer_3_attention) from pipeline-status + effectiveness when status-report is missing."""
    pm = data.get("project_manager") or {}
    running = data.get("running") or []
    pending = data.get("pending") or []
    completed = data.get("recent_completed") or []
    att = data.get("attention") or {}

    # Layer 0: Goal (from effectiveness fallback)
    layer0 = {"status": "unknown", "summary": "Report not yet generated"}
    if effectiveness:
        gp = effectiveness.get("goal_proximity", 0)
        t = effectiveness.get("throughput", {})
        sr = effectiveness.get("success_rate", 0)
        layer0 = {
            "status": "ok" if gp >= 0.5 else "needs_attention",
            "goal_proximity": gp,
            "summary": f"goal_proximity={gp}, {t.get('completed_7d', 0)} tasks (7d), {int((sr or 0) * 100)}% success",
        }

    # Layer 1: Orchestration (from PM state + process detection)
    rw = proc.get("runner_workers")
    pp = proc.get("pm_parallel")
    pm_seen = pm is not None and (pm.get("backlog_index") is not None or pm.get("phase") is not None)
    runner_seen = rw is not None
    layer1 = {
        "status": "ok" if (runner_seen or pm_seen) else "needs_attention",
        "project_manager": pm,
        "runner_workers": rw,
        "pm_parallel": pp,
        "summary": f"PM item={pm.get('backlog_index', '?')} phase={pm.get('phase', '?')}; runner_workers={rw}; pm_parallel={pp}",
    }

    # Layer 2: Execution (Tasks)
    layer2 = {
        "status": "ok",
        "running": running,
        "pending": pending,
        "recent_completed": completed,
        "summary": f"running={len(running)}, pending={len(pending)}, recent_completed={len(completed)}",
    }

    # Layer 3: Attention (from pipeline-status attention)
    flags = (att.get("flags") or []) if isinstance(att, dict) else []
    layer3 = {
        "status": "ok" if not flags else "needs_attention",
        "flags": flags,
        "summary": "No issues" if not flags else f"Attention: {', '.join(flags)}",
    }

    return {
        "layer_0_goal": layer0,
        "layer_1_orchestration": layer1,
        "layer_2_execution": layer2,
        "layer_3_attention": layer3,
    }


def main():
    ap = argparse.ArgumentParser(description="Pipeline visibility")
    ap.add_argument("--task-id", help="Show full log for task")
    ap.add_argument("--log", action="store_true", help="Include log preview for running task")
    ap.add_argument("--json", action="store_true", help="Output pipeline-status as JSON")
    ap.add_argument("--attention", action="store_true", help="Print attention flags (stuck, repeated_failures, low_success_rate)")
    ap.add_argument("--hierarchical", action="store_true", help="Use hierarchical view (Goal → PM → Tasks → Artifacts). Default for human-readable.")
    ap.add_argument("--flat", action="store_true", help="Legacy flat output (sections not strictly layered).")
    args = ap.parse_args()
    use_hierarchical = not args.flat

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
        if use_hierarchical:
            status_report = _fetch_status_report()
            effectiveness = _fetch_effectiveness()
            proc = _get_pipeline_process_args()
            if status_report and status_report.get("layer_0_goal") and status_report.get("layer_0_goal").get("summary") != "Report not yet generated by monitor":
                hierarchical = {
                    "layer_0_goal": status_report.get("layer_0_goal", {}),
                    "layer_1_orchestration": status_report.get("layer_1_orchestration", {}),
                    "layer_2_execution": status_report.get("layer_2_execution", {}),
                    "layer_3_attention": status_report.get("layer_3_attention", {}),
                }
            else:
                hierarchical = _build_hierarchical_from_data(data, effectiveness, proc)
            out = {**data, "hierarchical": hierarchical}
            print(json.dumps(out, indent=2))
        else:
            print(json.dumps(data, indent=2))
        return

    if args.attention:
        att = data.get("attention") or {}
        flags = att.get("flags") or []
        if flags:
            print("Attention:", ", ".join(flags))
        else:
            print("Attention: —")
        print()

    if use_hierarchical:
        # Hierarchical view: Goal → PM/Orchestration → Tasks → Artifacts
        status_report = _fetch_status_report()
        effectiveness = _fetch_effectiveness()
        proc = _get_pipeline_process_args()
        running = data.get("running") or []
        pending = data.get("pending") or []
        completed = data.get("recent_completed") or []
        pm = data.get("project_manager")

        # Layer 0: Goal
        layer0 = None
        if status_report and status_report.get("layer_0_goal"):
            l0 = status_report["layer_0_goal"]
            if l0.get("summary") and "not yet generated" not in (l0.get("summary") or "").lower():
                layer0 = l0
        if not layer0 and effectiveness:
            gp = effectiveness.get("goal_proximity", 0)
            t = effectiveness.get("throughput", {})
            sr = effectiveness.get("success_rate", 0)
            layer0 = {
                "status": "ok" if gp >= 0.5 else "needs_attention",
                "goal_proximity": gp,
                "summary": f"goal_proximity={gp}, {t.get('completed_7d', 0)} tasks (7d), {int((sr or 0) * 100)}% success",
            }
        print("Pipeline Status (hierarchical)")
        print("=" * 60)
        print("Goal (Layer 0)")
        if layer0:
            print(f"  status: {layer0.get('status', '?')}")
            print(f"  {layer0.get('summary', '')}")
            if layer0.get("goal_proximity") is not None:
                print(f"  goal_proximity: {layer0['goal_proximity']}")
        else:
            print("  (report not yet generated)")

        # Layer 1: PM / Orchestration
        layer1 = None
        if status_report and status_report.get("layer_1_orchestration") and (status_report["layer_1_orchestration"].get("summary") or status_report["layer_1_orchestration"].get("status") != "unknown"):
            layer1 = status_report["layer_1_orchestration"]
        if not layer1:
            rw = proc.get("runner_workers")
            pp = proc.get("pm_parallel")
            parts = []
            if rw is not None:
                parts.append(f"agent_runner workers={rw}" + (" (ok)" if rw >= 5 else " (need 5)"))
            else:
                parts.append("agent_runner not seen")
            if pp is not None:
                parts.append(f"PM parallel={str(pp).lower()}" + (" (ok)" if pp else " (need --parallel)"))
            else:
                parts.append("PM not seen")
            layer1 = {"summary": "; ".join(parts)}
            if pm:
                layer1["summary"] = f"item {pm.get('backlog_index', '?')}, phase={pm.get('phase', '?')}; " + layer1["summary"]
        print("\nPM / Orchestration (Layer 1)")
        print(f"  {layer1.get('summary', '')}")
        if pm:
            print(f"  PROJECT MANAGER: item {pm.get('backlog_index', '?')}, phase={pm.get('phase', '?')}")
            if pm.get("current_task_id"):
                print(f"  Waiting on: {pm['current_task_id']}")
            if pm.get("blocked"):
                print("  (blocked by needs_decision)")

        # Layer 2: Tasks
        print("\nTasks (Layer 2)")
        if running:
            t = running[0]
            print(f"  RUNNING: {t['id']} ({t['task_type']}) | model: {t['model']} | duration: {_fmt_seconds(t.get('running_seconds'))}")
            print(f"    Direction: {(t.get('direction') or '')[:70]}...")
            tail = t.get("live_tail") or _read_log_tail(t["id"], 25)
            if tail and args.log:
                for line in tail[-18:]:
                    print(f"    {line[:90]}")
        else:
            print("  RUNNING: —")
        print(f"  PENDING: {len(pending)} tasks")
        for t in pending[:8]:
            wait = _fmt_seconds(t.get("wait_seconds"))
            print(f"    • {t['id']} ({t['task_type']}) | wait: {wait} | {(t.get('direction') or '')[:50]}...")
        print(f"  RECENT COMPLETED: {len(completed)}")
        for t in completed[:5]:
            dur = _fmt_seconds(t.get("duration_seconds"))
            print(f"    • {t['id']} ({t['task_type']}) | duration: {dur}")

        # Layer 3: Artifacts (recent completed with output size / preview)
        print("\nArtifacts (Layer 3)")
        if completed:
            for t in completed[:5]:
                out_len = t.get("output_len", 0)
                prev = (t.get("output_preview") or "").strip()
                line = f"  • {t['id']} | output: {out_len} chars"
                if prev:
                    line += f" | preview: {(prev.split(chr(10))[0])[:60]}..."
                print(line)
        else:
            print("  (no recent completed tasks)")

    else:
        # Legacy flat output
        print("Pipeline Status")
        print("=" * 60)

        running = data.get("running") or []
        if running:
            t = running[0]
            print(f"RUNNING: {t['id']} ({t['task_type']}) | model: {t['model']}")
            print(f"  Duration: {_fmt_seconds(t.get('running_seconds'))}")
            print(f"  Direction: {(t.get('direction') or '')[:70]}...")
            tail = t.get("live_tail") or _read_log_tail(t["id"], 25)
            if tail:
                print(f"  Live output (last {len(tail)} lines):")
                for line in tail[-18:]:
                    print(f"    {line[:90]}")
        else:
            print("RUNNING: —")

        pending = data.get("pending") or []
        print(f"\nPENDING: {len(pending)} tasks")
        for t in pending[:8]:
            wait = _fmt_seconds(t.get("wait_seconds"))
            print(f"  • {t['id']} ({t['task_type']}) | wait: {wait} | {(t.get('direction') or '')[:50]}...")

        completed = data.get("recent_completed") or []
        print(f"\nRECENT COMPLETED: {len(completed)}")
        for t in completed[:5]:
            dur = _fmt_seconds(t.get("duration_seconds"))
            out_len = t.get("output_len", 0)
            print(f"  • {t['id']} ({t['task_type']}) | duration: {dur} | output: {out_len} chars")

        pm = data.get("project_manager")
        if pm:
            print(f"\nPROJECT MANAGER: item {pm.get('backlog_index', '?')}, phase={pm.get('phase', '?')}")
            if pm.get("current_task_id"):
                print(f"  Waiting on: {pm['current_task_id']}")
            if pm.get("blocked"):
                print("  (blocked by needs_decision)")

        proc = _get_pipeline_process_args()
        rw = proc.get("runner_workers")
        pp = proc.get("pm_parallel")
        parts = []
        if rw is not None:
            parts.append(f"agent_runner workers={rw}" + (" (ok)" if rw >= 5 else " (need 5)"))
        else:
            parts.append("agent_runner not seen")
        if pp is not None:
            parts.append(f"PM parallel={str(pp).lower()}" + (" (ok)" if pp else " (need --parallel)"))
        else:
            parts.append("PM not seen")
        print(f"\nPROCESSES: {', '.join(parts)}")

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
    # Request count hint: Cursor uses its own usage; Claude+local uses model provider logs
    executor = os.environ.get("AGENT_EXECUTOR_DEFAULT", "claude")
    if executor == "cursor":
        print("Request count: Cursor tracks usage in app; model provider logs for Claude/Ollama path")
    else:
        print("Request count: check model provider logs (Ollama/GIN: each POST /v1/messages = 1 turn)")


if __name__ == "__main__":
    main()
