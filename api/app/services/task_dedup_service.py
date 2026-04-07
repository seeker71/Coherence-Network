"""Task deduplication service — prevents duplicate tasks for the same idea+phase.

Provides:
  - check_idea_phase_history(idea_id, phase) -> IdeaPhaseHistory
  - build_skip_context(idea_id, skipped_phases, tasks_payload) -> dict
  - Constants: MAX_RETRIES_PER_PHASE, MAX_TASKS_PER_PHASE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

MAX_RETRIES_PER_PHASE: int = 2
MAX_TASKS_PER_PHASE: int = 3

# Canonical phase sequence
PHASE_SEQUENCE: list[str] = [
    "spec", "impl", "test", "code-review", "deploy", "verify-production",
]


# ── Data model ────────────────────────────────────────────────────────────

@dataclass
class IdeaPhaseHistory:
    """Summary of an idea's task history for a single phase."""
    completed_count: int = 0
    failed_count: int = 0
    active_count: int = 0
    total_count: int = 0
    latest_completed_task: dict[str, Any] | None = None
    should_skip: bool = False
    retry_budget_left: int = MAX_RETRIES_PER_PHASE

    def __post_init__(self) -> None:
        self.should_skip = self.completed_count >= 1
        self.retry_budget_left = max(0, MAX_RETRIES_PER_PHASE - self.failed_count)


# ── Core gate ─────────────────────────────────────────────────────────────

def check_idea_phase_history(idea_id: str, phase: str) -> IdeaPhaseHistory:
    """Query the task store and return per-phase stats for an idea.

    Fail-open: returns all-zero IdeaPhaseHistory for unknown ideas or
    on any exception, so callers never crash.
    """
    try:
        from app.services.agent_service_list import list_tasks_for_idea
        payload = list_tasks_for_idea(idea_id)
    except Exception:
        log.warning("check_idea_phase_history: failed to load tasks for %s", idea_id)
        return IdeaPhaseHistory()

    return _extract_phase_history(payload, phase)


def _extract_phase_history(payload: dict[str, Any], phase: str) -> IdeaPhaseHistory:
    """Extract phase stats from a list_tasks_for_idea response dict."""
    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        return IdeaPhaseHistory()

    for group in groups:
        if not isinstance(group, dict):
            continue
        task_type = str(group.get("task_type") or "").strip().lower()
        if task_type != phase:
            continue

        status_counts = group.get("status_counts", {})
        if not isinstance(status_counts, dict):
            status_counts = {}

        completed = int(status_counts.get("completed", 0) or 0)
        failed = int(status_counts.get("failed", 0) or 0)
        timed_out = int(status_counts.get("timed_out", 0) or 0)
        pending = int(status_counts.get("pending", 0) or 0)
        running = int(status_counts.get("running", 0) or 0)
        needs_decision = int(status_counts.get("needs_decision", 0) or 0)

        # timed_out counts toward retry budget same as failed (Scenario 3 edge)
        effective_failed = failed + timed_out
        active = pending + running
        total = completed + failed + timed_out + active + needs_decision

        # Find latest completed task
        latest_completed: dict[str, Any] | None = None
        tasks = group.get("tasks", [])
        if isinstance(tasks, list):
            for t in tasks:
                if not isinstance(t, dict):
                    continue
                t_status = t.get("status", "")
                if hasattr(t_status, "value"):
                    t_status = t_status.value
                if t_status == "completed":
                    if latest_completed is None:
                        latest_completed = t
                    else:
                        # Pick the one with the latest updated_at
                        t_at = t.get("updated_at") or t.get("created_at") or ""
                        l_at = latest_completed.get("updated_at") or latest_completed.get("created_at") or ""
                        if str(t_at) > str(l_at):
                            latest_completed = t

        history = IdeaPhaseHistory(
            completed_count=completed,
            failed_count=effective_failed,
            active_count=active,
            total_count=total,
            latest_completed_task=latest_completed,
        )
        return history

    # Phase not found in groups — no tasks for this phase
    return IdeaPhaseHistory()


# ── Context propagation on skip-ahead (R7) ────────────────────────────────

def build_skip_context(
    idea_id: str,
    skipped_phases: list[str],
    tasks_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build context for a skip-ahead task by pulling fields from completed tasks
    of the skipped phases.

    Propagates: impl_branch, spec_file, pr_number/pr_url from skipped phases.
    """
    ctx: dict[str, Any] = {"idea_id": idea_id}
    source_label_parts: list[str] = []

    groups = tasks_payload.get("groups", [])
    if not isinstance(groups, list):
        return ctx

    # Index groups by task_type for fast lookup
    group_map: dict[str, dict[str, Any]] = {}
    for g in groups:
        if isinstance(g, dict):
            tt = str(g.get("task_type") or "").strip().lower()
            if tt:
                group_map[tt] = g

    for phase in skipped_phases:
        group = group_map.get(phase)
        if not group:
            continue

        # Find the latest completed task in this group
        tasks = group.get("tasks", [])
        if not isinstance(tasks, list):
            continue

        latest: dict[str, Any] | None = None
        for t in tasks:
            if not isinstance(t, dict):
                continue
            t_status = t.get("status", "")
            if hasattr(t_status, "value"):
                t_status = t_status.value
            if t_status != "completed":
                continue
            if latest is None:
                latest = t
            else:
                t_at = t.get("updated_at") or t.get("created_at") or ""
                l_at = latest.get("updated_at") or latest.get("created_at") or ""
                if str(t_at) > str(l_at):
                    latest = t

        if latest is None:
            continue

        task_ctx = latest.get("context") or {}
        if not isinstance(task_ctx, dict):
            task_ctx = {}

        # Propagate known fields
        if task_ctx.get("impl_branch"):
            ctx["impl_branch"] = task_ctx["impl_branch"]
        elif phase == "impl":
            log.warning("impl_branch missing from completed impl for %s", idea_id)

        if task_ctx.get("spec_file"):
            ctx["spec_file"] = task_ctx["spec_file"]

        if task_ctx.get("pr_number"):
            ctx["pr_number"] = task_ctx["pr_number"]
        if task_ctx.get("pr_url"):
            ctx["pr_url"] = task_ctx["pr_url"]

        source_label_parts.append(phase)

    return ctx


def compute_phase_summary(tasks_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compute per-phase summary dict from a list_tasks_for_idea response.

    Returns a dict keyed by phase name, each value containing:
      completed, failed, active, should_skip, retry_budget_left
    """
    result: dict[str, dict[str, Any]] = {}
    groups = tasks_payload.get("groups", [])
    if not isinstance(groups, list):
        return result

    for group in groups:
        if not isinstance(group, dict):
            continue
        phase = str(group.get("task_type") or "").strip().lower()
        if not phase:
            continue

        history = _extract_phase_history(tasks_payload, phase)
        result[phase] = {
            "completed": history.completed_count,
            "failed": history.failed_count,
            "active": history.active_count,
            "should_skip": history.should_skip,
            "retry_budget_left": history.retry_budget_left,
        }

    return result
