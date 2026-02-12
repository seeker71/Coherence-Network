#!/usr/bin/env python3
"""Project Manager orchestrator: spec → impl → test → review until all pass.

Finds the next backlog item, runs design (spec), implement, test, review phases.
Validates pytest and review pass before advancing. Loops impl→test→review until
pass or max iterations. Pauses on needs_decision for human /reply.

Usage:
  python scripts/project_manager.py [--interval 15] [--hours 8] [--once] [--max-items N] [--verbose]
"""

import argparse
import json
import logging
from typing import Tuple
import os
import re
import subprocess
import sys
import time

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
sys.path.insert(0, _api_dir)
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"), override=True)
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")
LOG_DIR = os.path.join(_api_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "project_manager.log")
BACKLOG_FILE = os.path.join(PROJECT_ROOT, "specs", "005-backlog.md")
STATE_FILE = os.path.join(LOG_DIR, "project_manager_state.json")
MAX_ITERATIONS = 5

PHASES = ["spec", "impl", "test", "review"]
TASK_TYPE_BY_PHASE = {"spec": "spec", "impl": "impl", "test": "test", "review": "review"}


def _setup_logging(verbose: bool = False) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log = logging.getLogger("project_manager")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not log.handlers:
        h = logging.FileHandler(LOG_FILE, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        if verbose:
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            log.addHandler(sh)
    return log


def load_backlog() -> list[str]:
    """Parse specs/005-backlog.md for work items (numbered lines)."""
    items = []
    if not os.path.isfile(BACKLOG_FILE):
        return items
    with open(BACKLOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"^\d+\.\s+(.+)$", line)
            if m and not line.startswith("#"):
                items.append(m.group(1).strip())
    return items


# Candidates for backlog refresh (from PLAN.md and specs/)
BACKLOG_CANDIDATES = [
    "docs/PLAN.md Sprint 0 — Skeleton, CI, deploy: git push → CI green; /health 200; landing live",
    "docs/PLAN.md Sprint 1 — Graph: 5K+ npm packages; API returns real data; search works",
    "docs/PLAN.md Sprint 2 — Coherence + UI: /project/npm/react shows score; search across npm+PyPI",
    "docs/PLAN.md Sprint 3 — Import Stack: Drop package-lock.json → full risk analysis + tree",
    "docs/PLAN.md Month 1 — Concept specs, indexer, top 1K npm packages, basic API",
    "docs/PLAN.md Month 2 — Coherence algorithm spec, calculator agent, dashboard, PyPI indexing",
    "specs/001-health-check.md — Any remaining health check items",
    "specs/002-agent-orchestration-api.md — Any remaining agent API items",
    "Add or improve tests for existing API endpoints per specs",
    "Review and improve docs/AGENT-DEBUGGING.md and docs/MODEL-ROUTING.md",
]


def refresh_backlog(log: logging.Logger, remaining: int = 2) -> bool:
    """Append new items from candidates if backlog has <= remaining items left (by position). Returns True if refreshed."""
    items = load_backlog()
    current_set = {it.strip().lower() for it in items}
    added = []
    for cand in BACKLOG_CANDIDATES:
        key = cand.strip().lower()
        if key not in current_set:
            added.append(cand)
            current_set.add(key)
    if len(added) == 0:
        return False
    with open(BACKLOG_FILE, "a", encoding="utf-8") as f:
        start = len(items) + 1
        for i, it in enumerate(added):
            f.write(f"\n{start + i}. {it}")
    log.info("refreshed backlog: added %d items (total now %d)", len(added), len(items) + len(added))
    return True


def load_state() -> dict:
    data = {"backlog_index": 0, "phase": "spec", "current_task_id": None, "iteration": 1, "blocked": False}
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
                data.update(loaded)
        except (json.JSONDecodeError, IOError):
            pass
    return data


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_pytest() -> Tuple[bool, str]:
    """Run pytest in api/. Excludes holdout tests (agent validation). CI runs full suite."""
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "-v", "--tb=short", "--ignore=tests/holdout"],
            cwd=_api_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def review_indicates_pass(output: str) -> bool:
    """Check if review output suggests pass."""
    if not output:
        return False
    lower = output.lower()
    if "fail" in lower:
        return False
    if "no pass" in lower or "not pass" in lower:
        return False
    return "pass" in lower


def build_direction(phase: str, item: str, iteration: int, last_output: str = "") -> str:
    if phase == "spec":
        return f"Write or expand the spec for: {item}. Use specs/TEMPLATE.md. Output the spec path."
    if phase == "impl":
        if iteration > 1:
            return f"Fix the issues (iteration {iteration}): {item}. Review feedback or test failures: {last_output[:300]}"
        return f"Implement per spec: {item}. Modify only files listed in the spec."
    if phase == "test":
        return f"Write and run tests for: {item}. Ensure tests define the contract. Do not modify tests to make impl pass."
    if phase == "review":
        return f"Review the implementation for: {item}. Check spec compliance, security, correctness. Output: pass/fail and issues."
    return item


def run(
    interval: int,
    hours: float,
    once: bool,
    log: logging.Logger,
    verbose: bool = False,
    max_items: int = 0,
) -> None:
    deadline = time.time() + hours * 3600 if hours else None
    items_completed_this_run = 0

    with httpx.Client(timeout=30.0) as client:
        while True:
            backlog = load_backlog()
            if not backlog:
                refresh_backlog(log)
                backlog = load_backlog()
                if not backlog:
                    log.warning("Backlog empty at %s", BACKLOG_FILE)
                    return

            if deadline and time.time() >= deadline:
                log.info("Reached time limit (%.1f h), stopping", hours)
                break

            # Refresh backlog when running low (2 or fewer items left)
            state = load_state()
            idx = state["backlog_index"]
            if idx >= len(backlog) - 2 and len(backlog) > 0:
                refresh_backlog(log)
                backlog = load_backlog()
            phase = state["phase"]
            task_id = state.get("current_task_id")
            iteration = state.get("iteration", 1)

            # Check needs_decision — do not create new tasks
            r = client.get(f"{BASE}/api/agent/tasks", params={"status": "needs_decision", "limit": 1})
            if r.status_code == 200 and (r.json().get("total") or 0) > 0:
                state["blocked"] = True
                save_state(state)
                log.info("Blocked: task needs_decision; waiting for human /reply")
                if once:
                    break
                time.sleep(interval)
                continue

            state["blocked"] = False

            # If we're waiting on a task, poll it
            if task_id:
                r = client.get(f"{BASE}/api/agent/tasks/{task_id}")
                if r.status_code == 404:
                    log.warning("task %s not found (404) — API may have restarted; clearing and recreating", task_id)
                    state["current_task_id"] = None
                    save_state(state)
                    # Fall through to "no current task" path below to create new task
                elif r.status_code != 200:
                    log.warning("GET task %s failed status=%s", task_id, r.status_code)
                    time.sleep(interval)
                    continue
                else:
                    t = r.json()
                    status = t.get("status", "")
                    if status == "pending" or status == "running":
                        log.debug("waiting for task %s status=%s", task_id, status)
                        if once:
                            break
                        time.sleep(interval)
                        continue

                    # Task finished
                    state["current_task_id"] = None
                    output = t.get("output") or ""

                    if status == "needs_decision":
                        state["blocked"] = True
                        save_state(state)
                        log.info("Task %s needs_decision; pausing", task_id)
                        if once:
                            break
                        time.sleep(interval)
                        continue

                    if status == "failed":
                        if phase == "impl":
                            state["iteration"] = iteration + 1
                            if iteration >= MAX_ITERATIONS:
                                log.warning("Max iterations reached; advancing to next item")
                                idx += 1
                                state["backlog_index"] = idx
                                state["phase"] = "spec"
                                state["iteration"] = 1
                                items_completed_this_run += 1
                                refresh_backlog(log)
                                if max_items > 0 and items_completed_this_run >= max_items:
                                    log.info("Reached --max-items=%d, stopping", max_items)
                                    save_state(state)
                                    return
                            else:
                                state["phase"] = "impl"
                                dir = build_direction("impl", backlog[idx], iteration + 1, output)
                                resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "impl"})
                                if resp.status_code == 201:
                                    state["current_task_id"] = resp.json().get("id")
                                    log.info("retry impl iteration %d task=%s", iteration + 1, state["current_task_id"])
                        else:
                            state["phase"] = "impl"
                            state["iteration"] = iteration + 1
                            dir = build_direction("impl", backlog[idx], iteration + 1, output)
                            resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "impl"})
                            if resp.status_code == 201:
                                state["current_task_id"] = resp.json().get("id")
                                log.info("phase %s failed, retry impl task=%s", phase, state["current_task_id"])
                        save_state(state)
                        if once:
                            break
                        time.sleep(interval)
                        continue

                    # status == "completed"
                    if phase == "spec":
                        state["phase"] = "impl"
                        dir = build_direction("impl", backlog[idx], 1)
                        resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "impl"})
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("spec done, created impl task=%s", state["current_task_id"])
                    elif phase == "impl":
                        state["phase"] = "test"
                        dir = build_direction("test", backlog[idx], 1)
                        resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "test"})
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("impl done, created test task=%s", state["current_task_id"])
                    elif phase == "test":
                        state["phase"] = "review"
                        dir = build_direction("review", backlog[idx], 1)
                        resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "review"})
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("test done, created review task=%s", state["current_task_id"])
                    elif phase == "review":
                        pytest_ok, pytest_out = run_pytest()
                        review_ok = review_indicates_pass(output)
                        if pytest_ok and review_ok:
                            state["backlog_index"] = idx + 1
                            state["phase"] = "spec"
                            state["iteration"] = 1
                            items_completed_this_run += 1
                            log.info("item %d passed validation, next item", idx)
                            refresh_backlog(log)
                            if max_items > 0 and items_completed_this_run >= max_items:
                                log.info("Reached --max-items=%d, stopping", max_items)
                                return
                            if idx + 1 >= len(backlog):
                                log.info("Backlog complete")
                                if once:
                                    break
                                time.sleep(interval)
                                continue
                        else:
                            state["phase"] = "impl"
                            state["iteration"] = iteration + 1
                            if state["iteration"] > MAX_ITERATIONS:
                                log.warning("Max iterations; advancing")
                                state["backlog_index"] = idx + 1
                                state["phase"] = "spec"
                                state["iteration"] = 1
                                items_completed_this_run += 1
                            else:
                                fail_reason = f"pytest={'fail' if not pytest_ok else 'ok'} review={'fail' if not review_ok else 'ok'}"
                                dir = build_direction("impl", backlog[idx], state["iteration"], fail_reason)
                                resp = client.post(f"{BASE}/api/agent/tasks", json={"direction": dir, "task_type": "impl"})
                                if resp.status_code == 201:
                                    state["current_task_id"] = resp.json().get("id")
                                    log.info("validation failed, retry impl task=%s", state["current_task_id"])
                            if max_items > 0 and items_completed_this_run >= max_items:
                                log.info("Reached --max-items=%d, stopping", max_items)
                                save_state(state)
                                return
                    save_state(state)
                    if once:
                        break
                    time.sleep(interval)
                    continue
                if once:
                    break
                time.sleep(interval)
                continue

            # No current task — create next
            if idx >= len(backlog):
                log.info("Backlog complete")
                if once:
                    break
                time.sleep(interval)
                continue

            item = backlog[idx]
            task_type = TASK_TYPE_BY_PHASE[phase]
            direction = build_direction(phase, item, iteration)

            resp = client.post(
                f"{BASE}/api/agent/tasks",
                json={"direction": direction, "task_type": task_type},
            )
            if resp.status_code == 201:
                t = resp.json()
                state["current_task_id"] = t.get("id")
                state["phase"] = phase
                save_state(state)
                log.info("created %s task=%s for item %d", phase, state["current_task_id"], idx)
                if verbose:
                    print(f"  Created {phase} task {state['current_task_id']}: {item[:50]}...")
            else:
                log.warning("POST task failed status=%s", resp.status_code)

            if once:
                break
            time.sleep(interval)


def main():
    global BACKLOG_FILE, STATE_FILE
    ap = argparse.ArgumentParser(description="Project Manager: spec→impl→test→review pipeline")
    ap.add_argument("--interval", type=int, default=15, help="Seconds between polls")
    ap.add_argument("--hours", type=float, default=0, help="Run for N hours (0 = indefinitely)")
    ap.add_argument("--once", action="store_true", help="Run one cycle and exit")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--backlog", default=None, help="Backlog file (default: specs/005-backlog.md)")
    ap.add_argument("--state-file", default=None, help="State file (default: logs/project_manager_state.json)")
    ap.add_argument("--reset", action="store_true", help="Reset state before starting (fresh run)")
    ap.add_argument("--dry-run", action="store_true", help="Log what would be done, no HTTP calls, exit after one cycle")
    ap.add_argument("--max-items", type=int, default=0, help="Stop after completing N backlog items (0 = no limit)")
    args = ap.parse_args()

    if args.backlog:
        BACKLOG_FILE = os.path.abspath(args.backlog)
    if args.state_file:
        STATE_FILE = os.path.abspath(args.state_file)
    if args.reset and os.path.isfile(STATE_FILE):
        os.remove(STATE_FILE)

    log = _setup_logging(verbose=args.verbose)
    log.info("Project Manager started API=%s backlog=%s", BASE, BACKLOG_FILE)

    with httpx.Client(timeout=15.0) as client:
        try:
            r = client.get(f"{BASE}/api/health")
            if r.status_code != 200:
                log.error("API not reachable at %s (status=%s)", BASE, r.status_code)
                print(f"API not reachable at {BASE} — start the API first")
                sys.exit(1)
        except Exception as e:
            log.error("API check failed: %s", e)
            print(f"API not reachable: {e}")
            sys.exit(1)

    if args.verbose:
        s = load_state()
        print(f"Project Manager | API: {BASE} | backlog: {BACKLOG_FILE}")
        print(f"  State: item {s['backlog_index']}, phase={s['phase']}, blocked={s.get('blocked', False)}")
        print(f"  Log: {LOG_FILE}\n")

    if args.dry_run:
        backlog = load_backlog()
        state = load_state()
        idx = state["backlog_index"]
        phase = state["phase"]
        log.info("DRY-RUN: backlog=%d items, index=%d, phase=%s", len(backlog), idx, phase)
        if backlog and idx < len(backlog):
            log.info("DRY-RUN: would create %s task for: %s", phase, backlog[idx][:60])
            print(f"Would create {phase} task: {backlog[idx][:80]}...")
        else:
            log.info("DRY-RUN: backlog empty or complete")
        return

    run(
        interval=args.interval,
        hours=args.hours,
        once=args.once,
        log=log,
        verbose=args.verbose,
        max_items=args.max_items,
    )


if __name__ == "__main__":
    main()
