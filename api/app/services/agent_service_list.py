"""Agent task list and counts: list_tasks, get_attention_tasks, get_task_count, get_review_summary."""

import os
from typing import Any, List, Optional, Tuple

from app.config_loader import get_bool, get_int, get_str
from app.models.agent import TaskStatus, TaskType

from app.services import agent_task_store_service
from app.services.agent_service_store import (
    _deserialize_task,
    _ensure_store_loaded,
    _now,
    _store,
)


def _should_backfill_runtime_tasks(existing_count: int) -> bool:
    fallback_mode = get_str("agent_tasks", "runtime_fallback_mode", default="empty_only").strip().lower()
    if fallback_mode in {"0", "off", "false", "disabled", "none"}:
        return False
    if fallback_mode in {"always", "all", "1", "on", "true"}:
        return True
    return existing_count == 0


def _runtime_fallback_events_for_tasks(existing_count: int) -> list[Any]:
    fallback_in_tests = get_bool("agent_tasks", "runtime_fallback_in_tests", default=False)
    running_under_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if running_under_pytest:
        if not fallback_in_tests:
            return []
        should_backfill = existing_count == 0 or _should_backfill_runtime_tasks(existing_count)
    else:
        should_backfill = _should_backfill_runtime_tasks(existing_count)
    if not should_backfill:
        return []
    try:
        from app.services import runtime_service
        limit = max(50, min(get_int("agent_tasks", "runtime_fallback_limit", default=200), 5000))
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


def _build_idea_workspace_lookup() -> dict[str, str]:
    """Build a mapping of idea_id -> workspace_id for task filtering.

    Tasks don't carry workspace_id directly; they reference an idea via
    context.idea_id, and the idea carries workspace_id. We build this
    lookup once per list_tasks call when a workspace filter is requested.
    """
    try:
        from app.services import idea_service
        ideas = idea_service._read_ideas(persist_ensures=False)
    except Exception:
        return {}
    lookup: dict[str, str] = {}
    for i in ideas:
        ws = getattr(i, "workspace_id", None) or "coherence-network"
        lookup[str(i.id)] = str(ws)
    return lookup


def _task_matches_workspace(task: dict[str, Any], workspace_id: str, lookup: dict[str, str]) -> bool:
    """Return True when a task's resolved idea belongs to the given workspace.

    Tasks whose idea_id is unknown fall back to the default workspace
    so legacy tasks remain visible to the default tenant only.
    """
    idea_id = _resolve_task_idea_id(task)
    if not idea_id:
        return workspace_id == "coherence-network"
    task_workspace = lookup.get(str(idea_id)) or "coherence-network"
    return task_workspace == workspace_id


def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 20,
    offset: int = 0,
    workspace_id: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """List tasks with optional filters. Sorted by created_at descending.
    Returns (items, total, runtime_fallback_backfill_count).

    When workspace_id is provided, results are post-filtered by the
    workspace of each task's linked idea (via context.idea_id).
    """
    use_db = get_bool("agent_tasks", "use_db", default=True)
    if use_db and agent_task_store_service.enabled():
        status_value = status.value if isinstance(status, TaskStatus) else None
        task_type_value = task_type.value if isinstance(task_type, TaskType) else None
        # DB-backed fast path: push workspace filter down to SQL.
        # The store treats NULL workspace_id as the default workspace,
        # so legacy rows remain visible to the default tenant only.
        rows, total = agent_task_store_service.load_tasks_page(
            status=status_value,
            task_type=task_type_value,
            limit=limit,
            offset=offset,
            include_output=False,
            include_command=False,
            workspace_id=workspace_id,
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
    if workspace_id:
        lookup = _build_idea_workspace_lookup()
        items = [t for t in items if _task_matches_workspace(t, workspace_id, lookup)]
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


def _resolve_task_idea_id(task: dict[str, Any]) -> str:
    """Resolve the idea_id for a task using its context dict."""
    from app.services.agent_service_completion_tracking import resolve_runtime_idea_id_for_task
    return resolve_runtime_idea_id_for_task(task)


def list_tasks_for_idea(idea_id: str) -> dict[str, Any]:
    """Return all tasks linked to an idea, grouped by type with status counts."""
    all_tasks, _total, _backfill = list_tasks(limit=5000, offset=0)

    matched: list[dict[str, Any]] = []
    for task in all_tasks:
        resolved = _resolve_task_idea_id(task)
        if resolved == idea_id:
            matched.append(task)

    groups_map: dict[str, list[dict[str, Any]]] = {}
    for task in matched:
        tt = task["task_type"]
        tt_val = tt.value if hasattr(tt, "value") else str(tt)
        groups_map.setdefault(tt_val, []).append(task)

    type_order = ["spec", "impl", "test", "review", "heal"]
    groups: list[dict[str, Any]] = []
    for tt in type_order:
        tasks_in_group = groups_map.pop(tt, [])
        if not tasks_in_group:
            continue
        status_counts: dict[str, int] = {}
        for t in tasks_in_group:
            s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
            status_counts[s] = status_counts.get(s, 0) + 1
        groups.append({
            "task_type": tt,
            "count": len(tasks_in_group),
            "status_counts": status_counts,
            "tasks": tasks_in_group,
        })
    # Any remaining types not in type_order
    for tt, tasks_in_group in sorted(groups_map.items()):
        status_counts = {}
        for t in tasks_in_group:
            s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
            status_counts[s] = status_counts.get(s, 0) + 1
        groups.append({
            "task_type": tt,
            "count": len(tasks_in_group),
            "status_counts": status_counts,
            "tasks": tasks_in_group,
        })

    result = {
        "idea_id": idea_id,
        "total": len(matched),
        "groups": groups,
    }

    # R6: compute per-phase dedup summary
    try:
        from app.services.task_dedup_service import compute_phase_summary
        result["phase_summary"] = compute_phase_summary(result)
    except Exception:
        result["phase_summary"] = {}

    return result
