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

# Repo root: scripts/ -> add parent for api imports when run from dev env
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "api") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "api"))

from app.services.idea_validation_category import (  # noqa: E402
    review_prompt_addendum_for_category,
    spec_phase_category_hint,
)

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


def determine_task_type(idea: dict) -> str:
    """What kind of task does this idea need next?

    Lifecycle: spec → test → impl → review
    - No spec exists → spec
    - Spec exists, no tests → test
    - Tests exist, no impl → impl
    - Impl exists → review
    """
    stage = idea.get("stage", "none") or "none"
    status = idea.get("manifestation_status", "none") or "none"

    if stage in ("none", "research"):
        return "spec"
    elif stage in ("spec", "specification"):
        return "test"
    elif stage in ("test", "testing"):
        return "impl"
    elif stage in ("implementation", "impl"):
        return "review"
    else:
        # Default: if it has open questions, spec them out
        return "spec"


def build_task_direction(idea: dict, task_type: str) -> str:
    """Build the task direction from the idea's context."""
    name = idea.get("name", idea.get("id", "unknown"))
    desc = idea.get("description", "")
    questions = idea.get("open_questions", [])
    interfaces = idea.get("interfaces") or []
    if not isinstance(interfaces, list):
        interfaces = []
    vc = idea.get("validation_category") or "network_internal"

    # Build direction from open questions if available
    question_text = ""
    if questions:
        q_list = []
        for q in questions[:3]:  # Max 3 questions per task
            qt = q.get("question", q) if isinstance(q, dict) else str(q)
            q_list.append(f"- {qt}")
        question_text = "\n\nOpen questions to address:\n" + "\n".join(q_list)

    category_line = spec_phase_category_hint(interfaces, desc)
    review_extra = review_prompt_addendum_for_category(str(vc))
    directions = {
        "spec": (
            f"Write a specification for: {name}.\n\n{desc}{question_text}\n\n"
            f"Output a spec document in specs/ covering: requirements, API endpoints, data models, and verification criteria.\n\n"
            f"{category_line}"
        ),
        "test": f"Write tests for the spec: {name}.\n\n{desc}\n\nWrite pytest tests in api/tests/ that encode the expected behavior from the spec. Tests should fail until implementation is done.",
        "impl": f"Implement: {name}.\n\n{desc}\n\nImplement the feature to satisfy the existing tests and spec. Follow existing patterns in the codebase.",
        "review": (
            f"Review the implementation of: {name}.\n\n{desc}\n\n"
            "Verify tests pass, check for edge cases, validate against the spec, and confirm coherence score criteria.\n\n"
            f"{review_extra}"
        ),
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

    # 4. Determine task type
    task_type = determine_task_type(idea)
    log.info("Selected idea: '%s' → %s task", idea.get("name", "?"), task_type)

    # 5. Create the task
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
