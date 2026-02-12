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
import dateutil.parser

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
sys.path.insert(0, _api_dir)
# Do not chdir at import time — tests import this module; chdir only in main() when run as script

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
NEEDS_DECISION_TIMEOUT_HOURS = float(os.environ.get("PIPELINE_NEEDS_DECISION_TIMEOUT_HOURS", "0"))

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


def _parse_backlog_file(path: str) -> list[str]:
    """Parse backlog file for numbered work items."""
    items = []
    if not path or not os.path.isfile(path):
        return items
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"^\d+\.\s+(.+)$", line)
            if m and not line.startswith("#"):
                items.append(m.group(1).strip())
    return items


def load_backlog() -> list[str]:
    """Parse backlog for work items. If META_BACKLOG and META_RATIO set, interleave product + meta (spec 028, EXECUTION-PLAN)."""
    product = _parse_backlog_file(BACKLOG_FILE)
    meta_file = os.environ.get("PIPELINE_META_BACKLOG")
    meta_ratio = float(os.environ.get("PIPELINE_META_RATIO", "0") or "0")
    if not meta_file or meta_ratio <= 0:
        return product
    meta = _parse_backlog_file(meta_file)
    if not meta:
        return product
    # Interleave: every 1/meta_ratio-th slot from meta (e.g. 0.2 → every 5th)
    n = max(1, int(1.0 / meta_ratio))
    combined = []
    pi, mi = 0, 0
    i = 0
    while pi < len(product) or mi < len(meta):
        if i % n == 0 and mi < len(meta):
            combined.append(meta[mi])
            mi += 1
        elif pi < len(product):
            combined.append(product[pi])
            pi += 1
        elif mi < len(meta):
            combined.append(meta[mi])
            mi += 1
        i += 1
    return combined


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
    """Write state atomically (temp file + replace) to avoid corruption on concurrent access."""
    d = os.path.dirname(STATE_FILE)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    tmp = STATE_FILE + ".tmp." + str(os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


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
    # More robust checking - looking for explicit pass/fail signals
    if "fail" in lower and not ("not fail" in lower or "no fail" in lower):
        return False
    if "no pass" in lower or "not pass" in lower:
        return False
    # Looking for explicit pass indicators
    pass_indicators = ["pass", "complete", "ok", "success"]
    for indicator in pass_indicators:
        if indicator in lower:
            return True
    return False


def build_direction(phase: str, item: str, iteration: int, last_output: str = "") -> str:
    if phase == "spec":
        return f"Write or expand the spec for: {item}. Use specs/TEMPLATE.md. Output the spec path."
    if phase == "impl":
        if iteration > 1:
            return f"Fix the issues (iteration {iteration}): {item}. Review feedback or test failures: {last_output[:300]}"
        return f"Implement per spec: {item}. Modify only files listed in the spec. Do not add features not in the spec."
    if phase == "test":
        return f"Write and run tests for: {item}. Ensure tests define the contract. Do not modify tests to make impl pass."
    if phase == "review":
        return f"Review the implementation for: {item}. Check spec compliance, security, correctness. Output: pass/fail and issues."
    return item


def _task_payload(direction: str, task_type: str, use_cursor: bool = False) -> dict:
    """Build POST body for /api/agent/tasks. use_cursor=True passes context.executor=cursor."""
    # Default to cursor when AGENT_EXECUTOR_DEFAULT=cursor (env)
    default_cursor = os.environ.get("AGENT_EXECUTOR_DEFAULT", "").lower() == "cursor"
    use_cursor = use_cursor or default_cursor
    payload = {"direction": direction, "task_type": task_type}
    if use_cursor:
        payload["context"] = {"executor": "cursor"}
    return payload


def _load_parallel_state() -> dict:
    """Load state for parallel mode: in_flight, item_phase, next_backlog_idx."""
    default = {"in_flight": [], "item_phase": {}, "next_backlog_idx": 0, "completed_items": 0, "blocked": False}
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
                default.update(loaded)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def run_parallel(
    interval: int,
    hours: float,
    once: bool,
    log: logging.Logger,
    verbose: bool = False,
    max_items: int = 0,
    use_cursor: bool = False,
) -> None:
    """Parallel mode: maintain tasks in spec/impl/test/review simultaneously. Spec 028."""
    deadline = time.time() + hours * 3600 if hours else None

    with httpx.Client(timeout=30.0) as client:
        while True:
            backlog = load_backlog()
            if not backlog:
                refresh_backlog(log)
                backlog = load_backlog()
                if not backlog:
                    log.warning("Backlog empty")
                    return

            if deadline and time.time() >= deadline:
                log.info("Reached time limit")
                break

            if max_items > 0:
                state = _load_parallel_state()
                if state.get("completed_items", 0) >= max_items:
                    log.info("Reached --max-items=%d", max_items)
                    break

            # Check needs_decision
            r = client.get(f"{BASE}/api/agent/tasks", params={"status": "needs_decision", "limit": 1})
            if r.status_code == 200 and (r.json().get("total") or 0) > 0:
                state = _load_parallel_state()
                state["blocked"] = True
                state.setdefault("blocked_at", time.time())
                save_state(state)
                if NEEDS_DECISION_TIMEOUT_HOURS > 0:
                    blocked_since = state.get("blocked_at", time.time())
                    if time.time() - blocked_since > NEEDS_DECISION_TIMEOUT_HOURS * 3600:
                        tasks = r.json().get("tasks") or []
                        if tasks:
                            nd_task_id = tasks[0].get("id")
                            client.patch(
                                f"{BASE}/api/agent/tasks/{nd_task_id}",
                                json={"status": "failed", "output": "Auto-skip: needs_decision timeout"},
                            )
                            state["blocked"] = False
                            state.pop("blocked_at", None)
                            save_state(state)
                            log.warning("needs_decision timeout: auto-skipped %s", nd_task_id)
                else:
                    log.info("Blocked: needs_decision")
                    if once:
                        break
                    time.sleep(interval)
                    continue

            state = _load_parallel_state()
            state["blocked"] = False
            in_flight = state.get("in_flight") or []
            item_phase = state.get("item_phase") or {}
            next_idx = state.get("next_backlog_idx", 0)

            # Poll in-flight tasks
            still_flying = []
            for ent in in_flight:
                tid = ent.get("task_id")
                if not tid:
                    continue
                r = client.get(f"{BASE}/api/agent/tasks/{tid}")
                if r.status_code != 200:
                    still_flying.append(ent)
                    continue
                t = r.json()
                status = t.get("status", "")
                if status in ("pending", "running"):
                    still_flying.append(ent)
                    continue

                # Task finished
                idx = ent["item_idx"]
                phase = ent["phase"]
                iteration = ent.get("iteration", 1)
                output = t.get("output") or ""

                if status == "needs_decision":
                    state["blocked"] = True
                    save_state(state)
                    if once:
                        break
                    time.sleep(interval)
                    continue

                if status == "failed":
                    if phase == "impl" and iteration < MAX_ITERATIONS:
                        dir = build_direction("impl", backlog[idx], iteration + 1, output[:300])
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor))
                        if resp.status_code == 201:
                            still_flying.append({
                                "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                "iteration": iteration + 1,
                            })
                            log.info("retry impl iteration %d item %d", iteration + 1, idx)
                    elif phase == "review" or iteration >= MAX_ITERATIONS:
                        next_idx = max(next_idx, idx + 1)
                        state["next_backlog_idx"] = next_idx
                        state["completed_items"] = state.get("completed_items", 0) + 1
                        log.info("item %d failed max iterations, advance", idx)
                    else:
                        dir = build_direction("impl", backlog[idx], iteration + 1, output[:300])
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor))
                        if resp.status_code == 201:
                            still_flying.append({
                                "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                "iteration": iteration + 1,
                            })
                    save_state({**state, "in_flight": still_flying})
                    continue

                # status == completed
                if phase == "spec":
                    dir = build_direction("impl", backlog[idx], 1)
                    resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor))
                    if resp.status_code == 201:
                        still_flying.append({"item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"), "iteration": 1})
                        log.info("item %d spec done, impl created", idx)
                elif phase == "impl":
                    dir = build_direction("test", backlog[idx], 1)
                    resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "test", use_cursor))
                    if resp.status_code == 201:
                        still_flying.append({"item_idx": idx, "phase": "test", "task_id": resp.json().get("id"), "iteration": 1})
                        log.info("item %d impl done, test created", idx)
                elif phase == "test":
                    dir = build_direction("review", backlog[idx], 1)
                    resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "review", use_cursor))
                    if resp.status_code == 201:
                        still_flying.append({"item_idx": idx, "phase": "review", "task_id": resp.json().get("id"), "iteration": 1})
                        log.info("item %d test done, review created", idx)
                elif phase == "review":
                    pytest_ok, _ = run_pytest()
                    review_ok = review_indicates_pass(output)
                    if pytest_ok and review_ok:
                        next_idx = max(next_idx, idx + 1)
                        state["next_backlog_idx"] = next_idx
                        state["completed_items"] = state.get("completed_items", 0) + 1
                        log.info("item %d passed, next_backlog_idx=%d", idx, next_idx)
                        refresh_backlog(log)
                    else:
                        if iteration >= MAX_ITERATIONS:
                            next_idx = max(next_idx, idx + 1)
                            state["next_backlog_idx"] = next_idx
                            state["completed_items"] = state.get("completed_items", 0) + 1
                        else:
                            dir = build_direction("impl", backlog[idx], iteration + 1, f"pytest={'fail' if not pytest_ok else 'ok'} review={'fail' if not review_ok else 'ok'}")
                            resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor))
                            if resp.status_code == 201:
                                still_flying.append({
                                    "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                    "iteration": iteration + 1,
                                })

            state["in_flight"] = still_flying

            # Fill slots: create spec tasks for next backlog items (buffer 2+ specs)
            phases_in_flight = {e["phase"] for e in still_flying}
            spec_count = sum(1 for e in still_flying if e["phase"] == "spec")
            while next_idx < len(backlog) and spec_count < 2:  # buffer at least 2 specs
                item = backlog[next_idx]
                dir = build_direction("spec", item, 1)
                resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "spec", use_cursor))
                if resp.status_code != 201:
                    break
                still_flying.append({"item_idx": next_idx, "phase": "spec", "task_id": resp.json().get("id"), "iteration": 1})
                log.info("created spec for item %d (buffer)", next_idx)
                next_idx += 1
                spec_count += 1

            state["in_flight"] = still_flying
            state["next_backlog_idx"] = next_idx
            save_state(state)

            if once:
                break
            time.sleep(interval)


def run(
    interval: int,
    hours: float,
    once: bool,
    log: logging.Logger,
    verbose: bool = False,
    max_items: int = 0,
    use_cursor: bool = False,
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
                state.setdefault("blocked_at", time.time())
                save_state(state)
                # Timeout: auto-skip to unblock (autonomy)
                if NEEDS_DECISION_TIMEOUT_HOURS > 0:
                    blocked_since = state.get("blocked_at", time.time())
                    if time.time() - blocked_since > NEEDS_DECISION_TIMEOUT_HOURS * 3600:
                        tasks = r.json().get("tasks") or []
                        if tasks:
                            nd_task_id = tasks[0].get("id")
                            client.patch(
                                f"{BASE}/api/agent/tasks/{nd_task_id}",
                                json={"status": "failed", "output": "Auto-skip: needs_decision timeout (PIPELINE_NEEDS_DECISION_TIMEOUT_HOURS)"},
                            )
                            idx = state["backlog_index"]
                            state["backlog_index"] = idx + 1
                            state["phase"] = "spec"
                            state["iteration"] = 1
                            state["current_task_id"] = None
                            state["blocked"] = False
                            state.pop("blocked_at", None)
                            log.warning("needs_decision timeout: auto-skipped task %s, advanced to item %d", nd_task_id, idx + 1)
                else:
                    log.info("Blocked: task needs_decision; waiting for human /reply")
                    if once:
                        break
                    time.sleep(interval)
                    continue

            state["blocked"] = False
            state.pop("blocked_at", None)

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
                    # Check if task has timed out (running for more than 3600 seconds)
                    created_at = t.get("created_at")
                    if status == "running" and created_at:
                        try:
                            created_time = dateutil.parser.isoparse(created_at)
                            import datetime
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            elapsed_seconds = (current_time - created_time).total_seconds()
                            log.debug("Task %s has been running for %d seconds", task_id, elapsed_seconds)
                            if elapsed_seconds > 3600:  # 1 hour timeout
                                log.warning("Task %s has timed out after %d seconds", task_id, elapsed_seconds)
                                # Mark as failed to trigger retry logic
                                status = "failed"
                        except Exception as e:
                            log.warning("Could not parse task timing: %s", e)
                            # In case of parsing error, treat as normal running task

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
                        state.setdefault("blocked_at", time.time())
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
                                resp = client.post(
                                    f"{BASE}/api/agent/tasks",
                                    json=_task_payload(dir, "impl", use_cursor),
                                )
                                if resp.status_code == 201:
                                    state["current_task_id"] = resp.json().get("id")
                                    log.info("retry impl iteration %d task=%s", iteration + 1, state["current_task_id"])
                        else:
                            state["phase"] = "impl"
                            state["iteration"] = iteration + 1
                            dir = build_direction("impl", backlog[idx], iteration + 1, output)
                            resp = client.post(
                                f"{BASE}/api/agent/tasks",
                                json=_task_payload(dir, "impl", use_cursor),
                            )
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
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "impl", use_cursor),
                        )
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("spec done, created impl task=%s", state["current_task_id"])
                    elif phase == "impl":
                        state["phase"] = "test"
                        dir = build_direction("test", backlog[idx], 1)
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "test", use_cursor),
                        )
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("impl done, created test task=%s", state["current_task_id"])
                    elif phase == "test":
                        state["phase"] = "review"
                        dir = build_direction("review", backlog[idx], 1)
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "review", use_cursor),
                        )
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
                                resp = client.post(
                                    f"{BASE}/api/agent/tasks",
                                    json=_task_payload(dir, "impl", use_cursor),
                                )
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
                json=_task_payload(direction, task_type, use_cursor),
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
    os.chdir(PROJECT_ROOT)  # Only when run as script (spec 005: dry-run/once use repo root)
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
    ap.add_argument(
        "--cursor",
        action="store_true",
        help="Use Cursor CLI (agent) for all tasks. Also set via AGENT_EXECUTOR_DEFAULT=cursor",
    )
    ap.add_argument(
        "--claude",
        action="store_true",
        help="Use Claude Code CLI instead of Cursor (overrides AGENT_EXECUTOR_DEFAULT)",
    )
    ap.add_argument("--parallel", action="store_true", help="Parallel mode: spec/impl/test/review in flight; buffer 2+ specs (spec 028)")
    args = ap.parse_args()

    if args.backlog:
        BACKLOG_FILE = os.path.abspath(args.backlog)
    if args.state_file:
        STATE_FILE = os.path.abspath(args.state_file)
    if args.reset and os.path.isfile(STATE_FILE):
        os.remove(STATE_FILE)

    log = _setup_logging(verbose=args.verbose)
    use_cursor = (args.cursor or os.environ.get("AGENT_EXECUTOR_DEFAULT", "").lower() == "cursor") and not args.claude
    log.info(
        "Project Manager started API=%s backlog=%s executor=%s",
        BASE,
        BACKLOG_FILE,
        "cursor" if use_cursor else "claude",
    )

    if args.verbose:
        s = load_state()
        print(f"Project Manager | API: {BASE} | backlog: {BACKLOG_FILE}")
        print(f"  State: item {s['backlog_index']}, phase={s['phase']}, blocked={s.get('blocked', False)}")
        print(f"  Log: {LOG_FILE}\n")

    # Dry-run: no HTTP calls; log preview and exit 0 (spec 005 verification).
    # Must print deterministic preview to stdout so E2E smoke tests can assert without --verbose.
    if args.dry_run:
        backlog = load_backlog()
        state = load_state()
        idx = state["backlog_index"]
        phase = state["phase"]
        log.info("DRY-RUN: backlog=%d items, index=%d, phase=%s", len(backlog), idx, phase)
        # Deterministic preview: backlog index, phase, next item (spec 005 PM complete)
        print(f"DRY-RUN: backlog index={idx}, phase={phase}")
        if backlog and idx < len(backlog):
            log.info("DRY-RUN: would create %s task for: %s", phase, backlog[idx][:60])
            print(f"Would create {phase} task: {backlog[idx][:80]}...")
        else:
            log.info("DRY-RUN: backlog empty or complete")
            print("DRY-RUN: backlog empty or complete")
        return

    # Short timeout so we fail fast when API is down (avoids "Connection stalled" / long waits in CI)
    with httpx.Client(timeout=5.0) as client:
        try:
            r = client.get(f"{BASE}/api/health")
            if r.status_code != 200:
                log.error("API not reachable at %s (status=%s)", BASE, r.status_code)
                print(f"API not reachable at {BASE} — start the API first")
                sys.exit(1)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            log.error("API check failed: %s", e)
            print(f"API not reachable: {e}")
            sys.exit(1)
        except Exception as e:
            log.error("API check failed: %s", e)
            print(f"API not reachable: {e}")
            sys.exit(1)

    # Cursor by default when AGENT_EXECUTOR_DEFAULT=cursor; --claude overrides
    use_cursor = (args.cursor or os.environ.get("AGENT_EXECUTOR_DEFAULT", "").lower() == "cursor") and not args.claude
    runner = run_parallel if args.parallel else run
    runner(
        interval=args.interval,
        hours=args.hours,
        once=args.once,
        log=log,
        verbose=args.verbose,
        max_items=args.max_items,
        use_cursor=use_cursor,
    )


if __name__ == "__main__":
    main()
