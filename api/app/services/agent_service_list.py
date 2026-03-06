"""Agent task list and counts: list_tasks, get_attention_tasks, get_task_count, get_review_summary."""

import os
from typing import Any, List, Optional, Tuple

from app.config_loader import get_bool
from app.models.agent import TaskStatus, TaskType

from app.services import agent_task_store_service
from app.services.agent_service_store import (
    _deserialize_task,
    _ensure_store_loaded,
    _now,
    _store,
)


def _should_backfill_runtime_tasks(existing_count: int) -> bool:
    fallback_mode = str(os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_MODE", "empty_only")).strip().lower()
    if fallback_mode in {"0", "off", "false", "disabled", "none"}:
        return False
    if fallback_mode in {"always", "all", "1", "on", "true"}:
        return True
    return existing_count == 0


def _runtime_fallback_events_for_tasks(existing_count: int) -> list[Any]:
    fallback_in_tests = os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_IN_TESTS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if os.getenv("PYTEST_CURRENT_TEST") and not fallback_in_tests:
        return []
    if not _should_backfill_runtime_tasks(existing_count):
        return []
    try:
        from app.services import runtime_service
        limit = max(50, min(int(os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_LIMIT", "200")), 5000))
        return runtime_service.list_events(limit=limit)
    except Exception:
        return []


def _runtime_completion_event_to_task(event: Any, seen: set[str]) -> dict[str, Any] | None:
    metadata = getattr(event, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("tracking_kind") or "").strip() != "agent_task_completion":
        return None
    task_id = str(metadata.get("task_id") or "").strip()
    if not task_id or task_id in seen:
        return None
    status_raw = str(metadata.get("task_final_status") or "").strip()
    try:
        derived_status = TaskStatus(status_raw) if status_raw else TaskStatus.COMPLETED
    except ValueError:
        derived_status = TaskStatus.COMPLETED
    task_type_raw = str(metadata.get("task_type") or "").strip()
    try:
        derived_type = TaskType(task_type_raw) if task_type_raw else TaskType.IMPL
    except ValueError:
        derived_type = TaskType.IMPL
    recorded_at = getattr(event, "recorded_at", None) or _now()
    model = str(metadata.get("model") or "unknown").strip() or "unknown"
    command = str(metadata.get("repeatable_tool_call") or "").strip()
    direction = str(metadata.get("direction") or "").strip()
    if not direction and command:
        direction = command[:240]
    return {
        "id": task_id,
        "direction": direction or "(tracked completion)",
        "task_type": derived_type,
        "status": derived_status,
        "model": model,
        "command": command or "PATCH /api/agent/tasks/{task_id}",
        "started_at": None,
        "output": None,
        "context": {"source": "runtime_event_fallback"},
        "progress_pct": 100 if derived_status == TaskStatus.COMPLETED else None,
        "current_step": "completed" if derived_status == TaskStatus.COMPLETED else None,
        "decision_prompt": None,
        "decision": None,
        "claimed_by": str(metadata.get("worker_id") or metadata.get("agent_id") or "unknown"),
        "claimed_at": None,
        "created_at": recorded_at,
        "updated_at": recorded_at,
        "tier": str(metadata.get("provider") or "") or "unknown",
    }


def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int, int]:
    """List tasks with optional filters. Sorted by created_at descending.
    Returns (items, total, runtime_fallback_backfill_count)."""
    raw = os.getenv("AGENT_TASKS_USE_DB")
    if raw is None:
        raw = "1" if get_bool("agent_tasks", "use_db") else "0"
    use_db = str(raw).strip().lower() not in ("0", "false", "no", "off")
    if use_db and agent_task_store_service.enabled():
        status_value = status.value if isinstance(status, TaskStatus) else None
        task_type_value = task_type.value if isinstance(task_type, TaskType) else None
        rows, total = agent_task_store_service.load_tasks_page(
            status=status_value,
            task_type=task_type_value,
            limit=limit,
            offset=offset,
            include_output=False,
            include_command=False,
        )
        items: list[dict[str, Any]] = []
        for raw in rows:
            task = _deserialize_task(raw)
            if task is None:
                continue
            _store[task["id"]] = task
            items.append(task)
        runtime_backfill = 0
        if total == 0 and status is None and task_type is None and offset == 0:
            events = _runtime_fallback_events_for_tasks(0)
            seen: set[str] = {str(t.get("id") or "") for t in items if isinstance(t, dict)}
            for event in events:
                derived = _runtime_completion_event_to_task(event, seen)
                if derived is None:
                    continue
                items.append(derived)
                seen.add(str(derived.get("id") or ""))
                runtime_backfill += 1
            items.sort(key=lambda t: t["created_at"], reverse=True)
            items = items[:limit]
            total = len(items)
        return items, total, runtime_backfill

    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    events = _runtime_fallback_events_for_tasks(len(items))
    seen = {str(t.get("id") or "") for t in items if isinstance(t, dict)}
    runtime_backfill = 0
    for event in events:
        derived = _runtime_completion_event_to_task(event, seen)
        if derived is None:
            continue
        items.append(derived)
        seen.add(str(derived.get("id") or ""))
        runtime_backfill += 1
    if status is not None:
        items = [t for t in items if t["status"] == status]
    if task_type is not None:
        items = [t for t in items if t["task_type"] == task_type]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    items = items[offset : offset + limit]
    return items, total, runtime_backfill


def get_attention_tasks(limit: int = 20) -> Tuple[List[dict], int]:
    """List tasks with status needs_decision or failed."""
    if agent_task_store_service.enabled():
        rows, total = agent_task_store_service.load_attention_tasks(limit=limit)
        items = []
        for raw in rows:
            task = _deserialize_task(raw)
            if task is None:
                continue
            _store[task["id"]] = task
            items.append(task)
        return items, total
    _ensure_store_loaded(include_output=True)
    items = [
        t for t in _store.values()
        if t.get("status") in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)
    ]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    return items[:limit], total


def get_task_count() -> dict[str, Any]:
    """Lightweight task counts for dashboards."""
    if agent_task_store_service.enabled():
        return agent_task_store_service.load_status_counts()
    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    by_status: dict[str, int] = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status}


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention."""
    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    by_status = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    needs = [t for t in items if t["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)]
    return {"by_status": by_status, "needs_attention": needs, "total": len(items)}
