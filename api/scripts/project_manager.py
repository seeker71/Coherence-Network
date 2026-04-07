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
from datetime import datetime, timezone
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

PHASES = ["spec", "impl", "test", "review", "acceptance"]
TASK_TYPE_BY_PHASE = {"spec": "spec", "impl": "impl", "test": "test", "review": "review", "acceptance": None}

# Split/combine heuristics (deterministic; no AI or external services)
SPLIT_MAX_IDEA_CHARS = int(os.environ.get("PM_SPLIT_MAX_IDEA_CHARS", "300"))
SPLIT_MAX_SPEC_CHARS = int(os.environ.get("PM_SPLIT_MAX_SPEC_CHARS", "300"))
SPLIT_MAX_IMPL_CHARS = int(os.environ.get("PM_SPLIT_MAX_IMPL_CHARS", "300"))
SPLIT_MAX_PARTS = 5
SPLIT_MIN_PART_CHARS = 40


def _split_threshold(node_type: str) -> int:
    if node_type == "idea":
        return SPLIT_MAX_IDEA_CHARS
    if node_type == "spec":
        return SPLIT_MAX_SPEC_CHARS
    return SPLIT_MAX_IMPL_CHARS


def is_too_large(node_type: str, item: str) -> bool:
    """True if item exceeds split threshold for node_type. Deterministic heuristic."""
    return len(item) > _split_threshold(node_type)


def split_item(node_type: str, item: str) -> list[str]:
    """Split item into 2–5 child items. Deterministic: split by ' — ' or ';' or ' and '. Returns at least [item]."""
    items, _ = split_with_ordering(node_type, item)
    return items


def split_with_ordering(node_type: str, item: str) -> tuple[list[str], list[list[int]]]:
    """Split item into child items and return ordering: (children_items, depends_on_per_child).
    Ordering is decided at split time: default linear (child i depends on 0..i-1).
    Callers use this so sub-impls can be signaled ordering constraints."""
    threshold = _split_threshold(node_type)
    if len(item) <= threshold:
        return [item], [[]]
    parts = re.split(r"\s+—\s+|\s*;\s*|\s+and\s+", item, maxsplit=SPLIT_MAX_PARTS - 1)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= SPLIT_MIN_PART_CHARS]
    if len(parts) <= 1:
        chunk = max(SPLIT_MIN_PART_CHARS, (len(item) + 1) // 2)
        parts = [item[:chunk].rsplit(" ", 1)[0] or item[:chunk], item[chunk:].lstrip()]
    items = parts[: SPLIT_MAX_PARTS] if len(parts) > 1 else [item]
    # Default ordering: linear — child i depends on 0..i-1
    ordering = [list(range(i)) for i in range(len(items))]
    return items, ordering


def format_ordering_signal(child: dict, total_children: int) -> str:
    """Format ordering constraints for the sub-impl so it sees its position and dependencies."""
    idx = child.get("child_idx", 0)
    deps = child.get("depends_on", [])
    if total_children <= 1:
        return ""
    dep_str = ", ".join(str(d + 1) for d in deps) if deps else "none"
    return f" [Sub-impl {idx + 1} of {total_children}; depends on sub-impl(s) {dep_str}. Complete only this part.]"


def next_runnable_in_parallel(done_indices: list[int], ordering: list[list[int]], total: int) -> int | None:
    """First child index k not in done_indices whose depends_on are all in done_indices. None if all done or no runnable."""
    done_set = set(done_indices)
    for k in range(total):
        if k in done_set:
            continue
        deps = ordering[k] if k < len(ordering) else list(range(k))
        if all(j in done_set for j in deps):
            return k
    return None


def all_children_complete(split_parent: dict) -> bool:
    """True if every child in split_parent has complete=True."""
    children = split_parent.get("children") or []
    return all(c.get("complete") for c in children) and len(children) > 0


def _has_depends_on(children: list) -> bool:
    """True if any child declares depends_on (explicit ordering)."""
    return any("depends_on" in c for c in children)


def get_next_runnable_index(split_parent: dict) -> int | None:
    """Index of next child that can run: not complete and all depends_on complete. None if all done or no runnable."""
    children = split_parent.get("children") or []
    if not children:
        return None
    if _has_depends_on(children):
        for k, c in enumerate(children):
            if c.get("complete"):
                continue
            deps = c.get("depends_on", [])
            if all(children[j].get("complete") for j in deps if 0 <= j < len(children)):
                return k
        return None
    idx = split_parent.get("current_child_idx", 0)
    if idx >= len(children):
        return None
    if children[idx].get("complete"):
        idx += 1
        while idx < len(children) and children[idx].get("complete"):
            idx += 1
        split_parent["current_child_idx"] = idx
    return idx if idx < len(children) else None


def get_current_child(split_parent: dict) -> dict | None:
    """Return the child we're currently working on (respects depends_on ordering), or None if all done."""
    children = split_parent.get("children") or []
    runnable_idx = get_next_runnable_index(split_parent)
    if runnable_idx is None:
        return None
    split_parent["current_child_idx"] = runnable_idx
    return children[runnable_idx]


def mark_child_complete(split_parent: dict, child_idx: int) -> None:
    """Mark child at child_idx as complete."""
    children = split_parent.get("children") or []
    if 0 <= child_idx < len(children):
        children[child_idx]["complete"] = True


def advance_to_next_child(split_parent: dict) -> int | None:
    """Advance current_child_idx to next incomplete child (linear order). Returns next idx or None if all done."""
    children = split_parent.get("children") or []
    idx = split_parent.get("current_child_idx", 0)
    idx += 1
    while idx < len(children) and children[idx].get("complete"):
        idx += 1
    split_parent["current_child_idx"] = idx
    return idx if idx < len(children) else None


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
    "specs/agent-orchestration-api.md — Any remaining agent API items",
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
    data = {
        "backlog_index": 0,
        "phase": "spec",
        "current_task_id": None,
        "iteration": 1,
        "blocked": False,
        "split_parent": None,
    }
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


def _run_acceptance_gate(backlog_idx: int, item_preview: str, log: logging.Logger) -> tuple[bool, str]:
    """First-class acceptance gate: run validation and write minimal evidence. Returns (ok, evidence_path)."""
    pytest_ok, pytest_out = run_pytest()
    os.makedirs(LOG_DIR, exist_ok=True)
    evidence_path = os.path.join(LOG_DIR, f"acceptance_evidence_item_{backlog_idx}.json")
    evidence = {
        "backlog_idx": backlog_idx,
        "item_preview": (item_preview or "")[:80],
        "pytest_ok": pytest_ok,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)
    except OSError as e:
        log.warning("acceptance gate: could not write evidence %s: %s", evidence_path, e)
    log.info("acceptance gate item %d: pytest=%s evidence=%s", backlog_idx, "ok" if pytest_ok else "fail", evidence_path)
    return pytest_ok, evidence_path


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
    """Build direction from config (api/config/prompt_templates.json). No prompt data in code."""
    from app.services.agent_routing.prompt_templates_loader import build_direction as _build_from_config

    return _build_from_config(phase, item, iteration, last_output)


def _task_payload(direction: str, task_type: str, use_cursor: bool = False, context_extra: dict | None = None) -> dict:
    """Build POST body for /api/agent/tasks. context_extra merged into context (e.g. split ordering for sub-impls)."""
    default_cursor = os.environ.get("AGENT_EXECUTOR_DEFAULT", "").lower() == "cursor"
    use_cursor = use_cursor or default_cursor
    payload = {"direction": direction, "task_type": task_type}
    ctx = dict(context_extra or {})
    if use_cursor:
        ctx["executor"] = "cursor"
    if ctx:
        payload["context"] = ctx
    return payload


def _load_parallel_state() -> dict:
    """Load state for parallel mode: in_flight, next_backlog_idx, split_total, split_done."""
    default = {
        "in_flight": [],
        "next_backlog_idx": 0,
        "completed_items": 0,
        "blocked": False,
        "split_total": {},
        "split_done": {},
        "split_items": {},
        "split_ordering": {},
    }
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
                completed_tid = tid

                if status == "needs_decision":
                    state["blocked"] = True
                    save_state(state)
                    if once:
                        break
                    time.sleep(interval)
                    continue

                if status == "failed":
                    if phase == "impl" and iteration < MAX_ITERATIONS:
                        dir = build_direction("impl", backlog[idx], iteration + 1, (output or "")[:2000])
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                        if resp.status_code == 201:
                            still_flying.append({
                                "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                "iteration": iteration + 1,
                            })
                            log.info("retry impl iteration %d item %d (triggered_by=%s)", iteration + 1, idx, completed_tid)
                    elif phase == "review" or iteration >= MAX_ITERATIONS:
                        next_idx = max(next_idx, idx + 1)
                        state["next_backlog_idx"] = next_idx
                        state["completed_items"] = state.get("completed_items", 0) + 1
                        log.info("item %d failed max iterations, advance", idx)
                    else:
                        dir = build_direction("impl", backlog[idx], iteration + 1, (output or "")[:2000])
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                        if resp.status_code == 201:
                            still_flying.append({
                                "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                "iteration": iteration + 1,
                            })
                    save_state({**state, "in_flight": still_flying})
                    continue

                # status == completed
                if phase == "spec":
                    total_children = ent.get("total_children")
                    child_idx = ent.get("child_idx", 0)
                    if total_children is not None:
                        key = f"{idx}:spec"
                        split_done = dict(state.get("split_done") or {})
                        split_total = state.get("split_total") or {}
                        split_items = state.get("split_items") or {}
                        split_ordering = state.get("split_ordering") or {}
                        raw_done = split_done.get(key, [])
                        done_list = list(range(raw_done)) if isinstance(raw_done, int) else list(raw_done)
                        done_list.append(child_idx)
                        split_done[key] = done_list
                        state["split_done"] = split_done
                        ordering = split_ordering.get(key, [list(range(j)) for j in range(total_children)])
                        next_k = next_runnable_in_parallel(done_list, ordering, total_children)
                        if next_k is not None:
                            children_items = split_items.get(key, [])
                            if next_k < len(children_items):
                                part = children_items[next_k]
                                dir = build_direction("spec", part, 1)
                                child_ctx = {"child_idx": next_k, "depends_on": ordering[next_k] if next_k < len(ordering) else list(range(next_k))}
                                dir = dir + format_ordering_signal(child_ctx, total_children)
                                context_extra = {"split_child_index": next_k, "split_total_children": total_children, "split_depends_on": child_ctx["depends_on"]}
                                resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "spec", use_cursor, context_extra))
                                if resp.status_code == 201:
                                    still_flying.append({"item_idx": idx, "phase": "spec", "task_id": resp.json().get("id"), "iteration": 1, "child_idx": next_k, "total_children": total_children})
                                    log.info("item %d spec child %d/%d done, created next runnable %d", idx, child_idx + 1, total_children, next_k + 1)
                        elif len(done_list) >= total_children:
                            state["split_done"] = {k: v for k, v in split_done.items() if k != key}
                            state["split_total"] = {k: v for k, v in split_total.items() if k != key}
                            state["split_items"] = {k: v for k, v in split_items.items() if k != key}
                            state["split_ordering"] = {k: v for k, v in split_ordering.items() if k != key}
                            dir = build_direction("impl", backlog[idx], 1)
                            resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                            if resp.status_code == 201:
                                still_flying.append({"item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"), "iteration": 1})
                                log.info("item %d spec split combined (%d children), impl created (depends_on=%s)", idx, total_children, completed_tid)
                    else:
                        dir = build_direction("impl", backlog[idx], 1)
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                        if resp.status_code == 201:
                            still_flying.append({"item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"), "iteration": 1})
                            log.info("item %d spec done, impl created (depends_on=%s)", idx, completed_tid)
                elif phase == "impl":
                    dir = build_direction("test", backlog[idx], 1)
                    resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "test", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                    if resp.status_code == 201:
                        still_flying.append({"item_idx": idx, "phase": "test", "task_id": resp.json().get("id"), "iteration": 1})
                        log.info("item %d impl done, test created (depends_on=%s)", idx, completed_tid)
                elif phase == "test":
                    dir = build_direction("review", backlog[idx], 1)
                    resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "review", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                    if resp.status_code == 201:
                        still_flying.append({"item_idx": idx, "phase": "review", "task_id": resp.json().get("id"), "iteration": 1})
                        log.info("item %d test done, review created (depends_on=%s)", idx, completed_tid)
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
                            # Pass full review output so impl can use PATCH_GUIDANCE (spec 108)
                            dir = build_direction("impl", backlog[idx], iteration + 1, output or "")
                            resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [completed_tid]}))
                            if resp.status_code == 201:
                                still_flying.append({
                                    "item_idx": idx, "phase": "impl", "task_id": resp.json().get("id"),
                                    "iteration": iteration + 1,
                                })

            state["in_flight"] = still_flying

            # Fill slots: create spec tasks for next backlog items (buffer 2+ specs)
            spec_count = sum(1 for e in still_flying if e["phase"] == "spec")
            split_total = state.get("split_total") or {}
            split_done = state.get("split_done") or {}
            while next_idx < len(backlog) and spec_count < 2:  # buffer at least 2 specs
                item = backlog[next_idx]
                if is_too_large("spec", item):
                    children_items, ordering = split_with_ordering("spec", item)
                    key = f"{next_idx}:spec"
                    N = len(children_items)
                    split_total = dict(state.get("split_total") or {})
                    split_total[key] = N
                    state["split_total"] = split_total
                    state["split_done"] = dict(state.get("split_done") or {})
                    state["split_done"][key] = []
                    state["split_items"] = dict(state.get("split_items") or {})
                    state["split_items"][key] = children_items
                    state["split_ordering"] = dict(state.get("split_ordering") or {})
                    state["split_ordering"][key] = ordering
                    split_done = state["split_done"]
                    # Create only first runnable child (ordering-aware)
                    i = next_runnable_in_parallel(split_done[key], ordering, N)
                    if i is not None:
                        part = children_items[i]
                        dir = build_direction("spec", part, 1)
                        child_ctx = {"child_idx": i, "depends_on": ordering[i] if i < len(ordering) else list(range(i))}
                        dir = dir + format_ordering_signal(child_ctx, N)
                        context_extra = {
                            "split_child_index": i,
                            "split_total_children": N,
                            "split_depends_on": child_ctx["depends_on"],
                        }
                        resp = client.post(f"{BASE}/api/agent/tasks", json=_task_payload(dir, "spec", use_cursor, context_extra))
                        if resp.status_code == 201:
                            still_flying.append({
                                "item_idx": next_idx, "phase": "spec", "task_id": resp.json().get("id"),
                                "iteration": 1, "child_idx": i, "total_children": N,
                            })
                            spec_count += 1
                            log.info("created spec child %d/%d for item %d (split, ordering)", i + 1, N, next_idx)
                    next_idx += 1
                else:
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
                    split_parent = state.get("split_parent")

                    # If in split, mark child complete and advance to next child or combine
                    if split_parent and status == "completed":
                        child_idx = split_parent.get("current_child_idx", 0)
                        mark_child_complete(split_parent, child_idx)
                        next_idx = advance_to_next_child(split_parent)
                        if next_idx is None:
                            state["split_parent"] = None
                            next_phase_idx = (PHASES.index(phase) + 1) % len(PHASES)
                            state["phase"] = PHASES[next_phase_idx]
                            state["iteration"] = 1
                            if next_phase_idx == 0:
                                state["backlog_index"] = idx + 1
                                items_completed_this_run += 1
                                log.info("combined %d children for item %d, advanced to next item", len(split_parent["children"]), idx)
                                refresh_backlog(log)
                                if max_items > 0 and items_completed_this_run >= max_items:
                                    save_state(state)
                                    return
                            else:
                                log.info("combined %d children, advanced to phase=%s", len(split_parent["children"]), state["phase"])
                        save_state(state)
                        if once:
                            break
                        time.sleep(interval)
                        continue

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
                                    json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [task_id]}),
                                )
                                if resp.status_code == 201:
                                    state["current_task_id"] = resp.json().get("id")
                                    log.info("retry impl iteration %d task=%s (triggered_by=%s)", iteration + 1, state["current_task_id"], task_id)
                        else:
                            state["phase"] = "impl"
                            state["iteration"] = iteration + 1
                            dir = build_direction("impl", backlog[idx], iteration + 1, output)
                            resp = client.post(
                                f"{BASE}/api/agent/tasks",
                                json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [task_id]}),
                            )
                            if resp.status_code == 201:
                                state["current_task_id"] = resp.json().get("id")
                                log.info("phase %s failed, retry impl task=%s (triggered_by=%s)", phase, state["current_task_id"], task_id)
                        save_state(state)
                        if once:
                            break
                        time.sleep(interval)
                        continue

                    # status == "completed" — create next phase with depends_on_task_ids so runner gates on completion
                    if phase == "spec":
                        state["phase"] = "impl"
                        dir = build_direction("impl", backlog[idx], 1)
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [task_id]}),
                        )
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("spec done, created impl task=%s (depends_on=%s)", state["current_task_id"], task_id)
                    elif phase == "impl":
                        state["phase"] = "test"
                        dir = build_direction("test", backlog[idx], 1)
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "test", use_cursor, {"depends_on_task_ids": [task_id]}),
                        )
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("impl done, created test task=%s (depends_on=%s)", state["current_task_id"], task_id)
                    elif phase == "test":
                        state["phase"] = "review"
                        dir = build_direction("review", backlog[idx], 1)
                        resp = client.post(
                            f"{BASE}/api/agent/tasks",
                            json=_task_payload(dir, "review", use_cursor, {"depends_on_task_ids": [task_id]}),
                        )
                        if resp.status_code == 201:
                            state["current_task_id"] = resp.json().get("id")
                            log.info("test done, created review task=%s (depends_on=%s)", state["current_task_id"], task_id)
                    elif phase == "review":
                        pytest_ok, pytest_out = run_pytest()
                        review_ok = review_indicates_pass(output)
                        if pytest_ok and review_ok:
                            state["phase"] = "acceptance"
                            log.info("item %d review passed, advance to acceptance gate", idx)
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
                                    json=_task_payload(dir, "impl", use_cursor, {"depends_on_task_ids": [task_id]}),
                                )
                                if resp.status_code == 201:
                                    state["current_task_id"] = resp.json().get("id")
                                    log.info("validation failed, retry impl task=%s (triggered_by=%s)", state["current_task_id"], task_id)
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

            # No current task — run acceptance gate or create next task
            if phase == "acceptance":
                gate_ok, evidence_path = _run_acceptance_gate(idx, backlog[idx] if idx < len(backlog) else "", log)
                state["backlog_index"] = idx + 1
                state["phase"] = "spec"
                state["iteration"] = 1
                state["current_task_id"] = None
                items_completed_this_run += 1
                log.info("item %d acceptance gate done (ok=%s), next item", idx, gate_ok)
                refresh_backlog(log)
                if max_items > 0 and items_completed_this_run >= max_items:
                    save_state(state)
                    return
                save_state(state)
                if once:
                    break
                time.sleep(interval)
                continue

            if idx >= len(backlog):
                log.info("Backlog complete")
                if once:
                    break
                time.sleep(interval)
                continue

            item = backlog[idx]
            split_parent = state.get("split_parent")

            # Check if we need to split (before creating task); split decision is ordering-aware
            if split_parent is None and is_too_large(phase, item):
                children_items, ordering = split_with_ordering(phase, item)
                split_parent = {
                    "backlog_idx": idx,
                    "phase": phase,
                    "children": [
                        {
                            "item": c,
                            "child_idx": i,
                            "complete": False,
                            "task_id": None,
                            "depends_on": ordering[i] if i < len(ordering) else list(range(i)),
                        }
                        for i, c in enumerate(children_items)
                    ],
                    "split_reason": "item_too_long",
                    "current_child_idx": 0,
                }
                state["split_parent"] = split_parent
                log.info("split %s for item %d into %d children (reason=%s, ordering=linear)", phase, idx, len(children_items), split_parent["split_reason"])

            # Use child item when in split
            if split_parent:
                current_child = get_current_child(split_parent)
                if current_child is None:
                    # All children done — combine and advance phase
                    state["split_parent"] = None
                    next_phase_idx = (PHASES.index(phase) + 1) % len(PHASES)
                    state["phase"] = PHASES[next_phase_idx]
                    state["iteration"] = 1
                    if next_phase_idx == 0:
                        state["backlog_index"] = idx + 1
                        items_completed_this_run += 1
                        log.info("combined %d children for item %d, advanced to next item", len(split_parent["children"]), idx)
                        refresh_backlog(log)
                        if max_items > 0 and items_completed_this_run >= max_items:
                            save_state(state)
                            return
                    else:
                        log.info("combined %d children, advanced to phase=%s", len(split_parent["children"]), state["phase"])
                    save_state(state)
                    if once:
                        break
                    time.sleep(interval)
                    continue
                item = current_child["item"]

            task_type = TASK_TYPE_BY_PHASE[phase]
            direction = build_direction(phase, item, iteration)
            context_extra = None
            if split_parent:
                total_children = len(split_parent["children"])
                direction = direction + format_ordering_signal(current_child, total_children)
                context_extra = {
                    "split_child_index": current_child.get("child_idx", 0),
                    "split_total_children": total_children,
                    "split_depends_on": current_child.get("depends_on", []),
                }

            resp = client.post(
                f"{BASE}/api/agent/tasks",
                json=_task_payload(direction, task_type, use_cursor, context_extra),
            )
            if resp.status_code == 201:
                t = resp.json()
                task_id = t.get("id")
                state["current_task_id"] = task_id
                state["phase"] = phase
                if split_parent:
                    current_child = get_current_child(split_parent)
                    if current_child is not None:
                        current_child["task_id"] = task_id
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
        BACKLOG_FILE = os.path.normpath(os.path.abspath(args.backlog))
    if args.state_file:
        STATE_FILE = os.path.normpath(os.path.abspath(args.state_file))
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
        sys.stdout.flush()

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
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(0)

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
