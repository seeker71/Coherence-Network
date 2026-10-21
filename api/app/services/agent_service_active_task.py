"""Agent active task: find by fingerprint/session_key, upsert."""

from typing import Any

from app.models.agent import AgentTaskCreate, TaskType

from app.services import agent_task_store_service
from app.services.agent_service_store import (
    _ensure_store_loaded,
    _now,
    _save_store_to_disk,
    _serialize_task,
    _store,
)
from app.services.agent_service_task_derive import is_active_status
from app.services.agent_service_crud import create_task, _claim_running_task


def active_tasks_by_fingerprint() -> dict[str, dict[str, Any]]:
    """Every active task that carries a fingerprint, indexed by it — one pass over the store.

    A loop that asks find_active_task_by_fingerprint once per idea scans the whole store each time;
    on production that was 4,600 ideas against thousands of tasks, 91 s of CPU per inventory flow
    build, rebuilt every 30 s under page loads — the API's "ten-minute window" after each start
    (2026-10-21). Build this once and look up.
    """
    _ensure_store_loaded(include_output=False)
    index: dict[str, dict[str, Any]] = {}
    for task in _store.values():
        if not is_active_status(task.get("status")):
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        fingerprint = str(context.get("task_fingerprint") or "").strip()
        if fingerprint and fingerprint not in index:
            index[fingerprint] = task
    return index


def find_active_task_by_fingerprint(task_fingerprint: str) -> dict[str, Any] | None:
    _ensure_store_loaded(include_output=False)
    fingerprint = (task_fingerprint or "").strip()
    if not fingerprint:
        return None
    for task in _store.values():
        if not is_active_status(task.get("status")):
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if context.get("task_fingerprint") == fingerprint:
            return task
    return None


def find_active_task_by_session_key(session_key: str) -> dict[str, Any] | None:
    _ensure_store_loaded(include_output=False)
    key = (session_key or "").strip()
    if not key:
        return None
    for task in _store.values():
        if not is_active_status(task.get("status")):
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if str(context.get("session_key") or "").strip() == key:
            return task
    return None


def upsert_active_task(
    *,
    session_key: str,
    direction: str,
    task_type: TaskType,
    worker_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Ensure a running task exists for a unique session key. Returns (task, created)."""
    _ensure_store_loaded(
        force_reload=agent_task_store_service.enabled(),
        include_output=False,
    )
    normalized_key = (session_key or "").strip()
    if not normalized_key:
        raise ValueError("session_key is required")

    existing = find_active_task_by_session_key(normalized_key)
    if existing is not None:
        _claim_running_task(existing, worker_id)
        existing["updated_at"] = _now()
        if agent_task_store_service.enabled():
            agent_task_store_service.upsert_task(_serialize_task(existing))
        else:
            _save_store_to_disk()
        return existing, False

    payload_context = dict(context or {})
    payload_context["session_key"] = normalized_key
    payload_context.setdefault("source", "external_active_session")
    created = create_task(
        AgentTaskCreate(direction=direction, task_type=task_type, context=payload_context)
    )
    _claim_running_task(created, worker_id)
    created["updated_at"] = _now()
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(created))
    else:
        _save_store_to_disk()
    return created, True
