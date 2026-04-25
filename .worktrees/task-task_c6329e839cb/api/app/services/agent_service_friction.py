"""Agent task failure friction: record task failure as friction event."""

from typing import Any
from uuid import uuid4

from app.models.friction import FrictionEvent

from app.services import friction_service
from app.services.agent_service_store import _now
from app.services.agent_service_task_derive import (
    normalize_worker_id,
    status_value,
    task_output_text,
)


def linked_task_ids_from_friction_events() -> set[str]:
    try:
        events, _ = friction_service.load_events()
    except Exception:
        return set()
    linked_ids = set()
    for event in events:
        task_id = str(getattr(event, "task_id", "") or "").strip()
        if task_id:
            linked_ids.add(task_id)
    return linked_ids


def record_task_failure_friction(task: dict[str, Any], *, linked_task_ids: set[str] | None = None) -> bool:
    """Record a friction event for a failed task if not already linked. Returns True if recorded."""
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return False
    if linked_task_ids is None:
        linked_task_ids = linked_task_ids_from_friction_events()
    if task_id in linked_task_ids:
        return False

    notes_parts = [
        f"task_id={task_id}",
        f"task_type={status_value(task.get('task_type')) or 'unknown'}",
        f"claimed_by={normalize_worker_id(task.get('claimed_by'))}",
        "failure_reason=task transitioned to failed without linked friction event",
    ]
    output = task_output_text(task).strip()
    if output:
        notes_parts.append(f"output_preview={output[:400]}")

    event = FrictionEvent(
        id=f"fric_{uuid4().hex[:12]}",
        timestamp=_now(),
        task_id=task_id,
        endpoint="tool:agent-task-completion",
        stage="agent_runner",
        block_type="task_failure",
        severity="high",
        owner="agent_pipeline",
        unblock_condition="Investigate failed task output, then rerun or close with a documented resolution.",
        energy_loss_estimate=0.0,
        cost_of_delay=0.0,
        status="open",
        notes=" | ".join(notes_parts)[:1200],
        resolved_at=None,
        time_open_hours=None,
        resolution_action=None,
    )
    try:
        friction_service.append_event(event)
    except Exception:
        return False
    linked_task_ids.add(task_id)
    return True
