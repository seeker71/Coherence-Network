#!/usr/bin/env python3
"""Idea-to-Task Bridge — automatically generate tasks from open ideas.

Runs on a schedule (or manually) to keep the task pipeline fed without
overwhelming workers. Checks capacity, picks the highest-ROI unblocked
idea, and creates the appropriate next task (spec → impl → review).

Usage:
  python scripts/idea_to_task_bridge.py                  # one cycle
  python scripts/idea_to_task_bridge.py --loop --interval 3600  # hourly
  python scripts/idea_to_task_bridge.py --dry-run        # show what would happen
  python scripts/idea_to_task_bridge.py --max-pending 5  # capacity cap

Environment:
  AGENT_API_BASE  defaults to https://api.coherencycoin.com
"""

import argparse
import json
import logging
import os
import sys
import time

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("idea_bridge")

API_BASE = os.environ.get("AGENT_API_BASE", "https://api.coherencycoin.com")
_client = httpx.Client(timeout=20.0)

# ── Helpers ──────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        r = _client.get(f"{API_BASE}{path}", params=params or {})
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning("GET %s failed: %s", path, e)
    return None


def _post(path: str, body: dict) -> dict | None:
    try:
        r = _client.post(f"{API_BASE}{path}", json=body)
        if r.status_code in (200, 201):
            return r.json()
        else:
            log.warning("POST %s → %s: %s", path, r.status_code, r.text[:200])
    except Exception as e:
        log.warning("POST %s failed: %s", path, e)
    return None


# ── Core logic ───────────────────────────────────────────────────────────

def count_pending_tasks() -> int:
    """How many tasks are pending or running (not yet completed)."""
    data = _get("/api/agent/tasks", {"status": "pending", "limit": 100})
    pending = len(data) if isinstance(data, list) else len((data or {}).get("tasks", []))
    data2 = _get("/api/agent/tasks", {"status": "running", "limit": 100})
    running = len(data2) if isinstance(data2, list) else len((data2 or {}).get("tasks", []))
    return pending + running


def get_open_ideas() -> list[dict]:
    """Ideas that are not yet validated and could use work."""
    data = _get("/api/ideas", {"limit": 200})
    if not data:
        return []
    ideas = data.get("ideas", data) if isinstance(data, dict) else data
    return [
        i for i in ideas
        if i.get("manifestation_status") in ("none", "partial", None)
    ]


def pick_next_idea(ideas: list[dict]) -> dict | None:
    """Pick the highest-ROI idea that doesn't already have a running task."""
    # Use the API's selection endpoint for Thompson Sampling
    result = _post("/api/ideas/select", {"temperature": 0.3})
    if result and result.get("selected"):
        selected = result["selected"]
        # Make sure it's an open idea
        if selected.get("manifestation_status") in ("none", "partial", None):
            return selected
    # Fallback: sort by free_energy_score
    scored = sorted(ideas, key=lambda i: i.get("free_energy_score", 0), reverse=True)
    return scored[0] if scored else None


MAX_RETRIES_PER_PHASE: int = 2

# Canonical pipeline phase sequence
_PHASE_SEQUENCE: list[str] = [
    "spec", "impl", "test", "code-review", "deploy", "verify-production",
]


def determine_task_type(idea: dict) -> str | None:
    """What kind of task does this idea need next?

    R5: Uses live task history from GET /api/ideas/{id}/tasks instead of
    stale idea.stage. Walks the phase sequence forward, skipping completed
    phases. Returns None if all phases are complete or the next phase has
    exhausted its retry budget.
    """
    idea_id = idea.get("id", "")
    if not idea_id:
        return "spec"

    # Fetch live task history
    tasks_data = _get(f"/api/ideas/{idea_id}/tasks")
    if not tasks_data or not isinstance(tasks_data, dict):
        # Fallback: no task data available, start from spec
        return "spec"

    phase_summary = tasks_data.get("phase_summary", {})
    if not phase_summary:
        # No phase_summary available — fall back to groups analysis
        groups = tasks_data.get("groups", [])
        if not groups:
            return "spec"
        # Build a simple summary from groups
        completed_phases: set[str] = set()
        for g in groups:
            if not isinstance(g, dict):
                continue
            phase = g.get("task_type", "")
            sc = g.get("status_counts", {})
            if int(sc.get("completed", 0) or 0) > 0:
                completed_phases.add(phase)
        # Walk forward
        for phase in _PHASE_SEQUENCE:
            if phase in completed_phases:
                log.info("%s already completed for %s, advancing to next", phase, idea_id)
                continue
            return phase
        return None  # all done

    # Walk forward using phase_summary
    for phase in _PHASE_SEQUENCE:
        ps = phase_summary.get(phase, {})
        if ps.get("should_skip"):
            log.info("%s already completed for %s, advancing to next", phase, idea_id)
            continue
        # Check retry budget: if exhausted with no completion, skip (needs human)
        if ps.get("retry_budget_left", MAX_RETRIES_PER_PHASE) <= 0 and not ps.get("should_skip"):
            failed = ps.get("failed", 0)
            log.warning(
                "%s for %s has %d failures with no completion — needs human intervention",
                phase, idea_id, failed,
            )
            return None
        return phase

    # All phases complete
    log.info("All phases complete for %s — skipping", idea_id)
    return None


def _idea_has_task_in_phase(idea_id: str, task_type: str) -> str | None:
    """Check if an idea already has a task of this type in a blocking state.

    Returns the task status string if a blocking task exists, or None if
    the phase is clear for a new task. Only blocks on pending/running/
    completed/done — failed tasks allow retry.
    """
    data = _get(f"/api/ideas/{idea_id}/tasks")
    if not data:
        return None
    groups = data.get("groups", [])
    blocking_statuses = {"pending", "running", "completed", "done"}
    for group in groups:
        if group.get("task_type") == task_type:
            status_counts = group.get("status_counts", {})
            for status, count in status_counts.items():
                if status in blocking_statuses and count > 0:
                    return status
    return None


def _emit_friction_skip(idea: dict, reason: str) -> None:
    """Emit a friction event when the bridge skips a closed or duplicate idea."""
    idea_id = idea.get("id", "unknown")
    idea_name = idea.get("name", idea_id)
    log.info("FRICTION: Skipping idea '%s' — %s", idea_name, reason)
    # Best-effort POST to friction endpoint; don't fail the cycle
    try:
        import datetime
        _post("/api/friction/events", {
            "id": f"bridge-skip-{idea_id}-{int(time.time())}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "stage": "task_generation",
            "block_type": "lifecycle_closure",
            "severity": "low",
            "owner": "idea_to_task_bridge",
            "unblock_condition": "none — idea is closed or has existing task",
            "energy_loss_estimate": 0.1,
            "cost_of_delay": 0.0,
            "status": "resolved",
            "endpoint": "idea_to_task_bridge.run_cycle",
        })
    except Exception:
        pass  # Best-effort; friction logging should never break the bridge


def build_task_direction(idea: dict, task_type: str) -> str:
    """Build the task direction from the idea's context."""
    name = idea.get("name", idea.get("id", "unknown"))
    desc = idea.get("description", "")
    questions = idea.get("open_questions", [])

    # Build direction from open questions if available
    question_text = ""
    if questions:
        q_list = []
        for q in questions[:3]:  # Max 3 questions per task
            qt = q.get("question", q) if isinstance(q, dict) else str(q)
            q_list.append(f"- {qt}")
        question_text = "\n\nOpen questions to address:\n" + "\n".join(q_list)

    directions = {
        "spec": f"Write a specification for: {name}.\n\n{desc}{question_text}\n\nOutput a spec document in specs/ covering: requirements, API endpoints, data models, and verification criteria.",
        "test": f"Write tests for the spec: {name}.\n\n{desc}\n\nWrite pytest tests in api/tests/ that encode the expected behavior from the spec. Tests should fail until implementation is done.",
        "impl": f"Implement: {name}.\n\n{desc}\n\nImplement the feature to satisfy the existing tests and spec. Follow existing patterns in the codebase.",
        "review": f"Review the implementation of: {name}.\n\n{desc}\n\nVerify tests pass, check for edge cases, validate against the spec, and confirm coherence score criteria.",
    }
    return directions.get(task_type, directions["spec"])


def create_task(idea: dict, task_type: str, dry_run: bool = False) -> dict | None:
    """Create a task for the given idea."""
    direction = build_task_direction(idea, task_type)
    idea_id = idea.get("id", "unknown")
    idea_name = idea.get("name", idea_id)

    payload = {
        "direction": direction,
        "task_type": task_type,
        "context": {
            "idea_id": idea_id,
            "idea_name": idea_name,
            "bridge_generated": True,
        },
        "target_state": f"{task_type.title()} completed for: {idea_name}",
        "success_evidence": f"{task_type} artifact exists and meets quality criteria",
        "abort_evidence": f"Cannot make progress on {task_type} — blocked or unclear requirements",
    }

    if dry_run:
        log.info("DRY RUN — would create %s task for idea '%s'", task_type, idea_name)
        log.info("  Direction: %s", direction[:120] + "...")
        return {"id": "dry-run", "status": "dry-run"}

    result = _post("/api/agent/tasks", payload)
    if result:
        log.info("CREATED %s task %s for idea '%s'", task_type, result.get("id", "?"), idea_name)
    else:
        log.warning("FAILED to create task for idea '%s'", idea_name)
    return result


# ── Main loop ────────────────────────────────────────────────────────────

def run_cycle(max_pending: int = 5, dry_run: bool = False) -> bool:
    """Run one bridge cycle. Returns True if a task was created."""

    # 1. Check capacity
    active = count_pending_tasks()
    log.info("Active tasks (pending+running): %d / %d max", active, max_pending)
    if active >= max_pending:
        log.info("At capacity — skipping task generation")
        return False

    # 2. Get open ideas
    ideas = get_open_ideas()
    log.info("Open ideas (none/partial): %d", len(ideas))
    if not ideas:
        log.info("No open ideas — all validated!")
        return False

    # 3. Pick the next idea
    idea = pick_next_idea(ideas)
    if not idea:
        log.info("Could not select an idea")
        return False

    # 4. Determine task type — None means idea is closed (R4)
    task_type = determine_task_type(idea)
    idea_name = idea.get("name", "?")
    idea_id = idea.get("id", "unknown")

    if task_type is None:
        _emit_friction_skip(idea, f"stage '{idea.get('stage')}' is reviewing or complete")
        log.info("Skipping '%s' — idea is closed (stage=%s)", idea_name, idea.get("stage"))
        return False

    # 5. Task history guard — prevent duplicate tasks for same idea+phase (R2)
    existing_status = _idea_has_task_in_phase(idea_id, task_type)
    if existing_status is not None:
        log.info("Skipping '%s' — already has %s task in state %s", idea_name, task_type, existing_status)
        return False

    log.info("Selected idea: '%s' → %s task", idea_name, task_type)

    # 6. Create the task
    result = create_task(idea, task_type, dry_run=dry_run)
    return result is not None


def main():
    parser = argparse.ArgumentParser(description="Idea-to-Task Bridge")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between cycles (default: 3600)")
    parser.add_argument("--max-pending", type=int, default=5, help="Max pending+running tasks (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without creating tasks")
    args = parser.parse_args()

    log.info("Idea-to-Task Bridge starting (api=%s max_pending=%d interval=%ds)",
             API_BASE, args.max_pending, args.interval)

    if args.loop:
        while True:
            try:
                run_cycle(max_pending=args.max_pending, dry_run=args.dry_run)
            except Exception as e:
                log.error("Cycle failed: %s", e, exc_info=True)
            log.info("Next cycle in %ds", args.interval)
            time.sleep(args.interval)
    else:
        run_cycle(max_pending=args.max_pending, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
