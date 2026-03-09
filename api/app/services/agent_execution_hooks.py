"""Lifecycle hook registry for agent task execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from app.models.runtime import RuntimeEventCreate
from app.services import agent_service, runtime_service
from app.services.agent_execution_hooks_config import (
    enabled_subscribers,
    event_status_code as _event_status_code,
    jsonl_max_lines,
    jsonl_path,
    jsonl_subscriber_enabled,
    runtime_subscriber_enabled,
)
from app.services.agent_execution_hooks_summary import summarize_lifecycle_events as _summarize_lifecycle_events

LifecycleHookPayload = dict[str, Any]
LifecycleHook = Callable[[LifecycleHookPayload], None]

_LIFECYCLE_HOOKS: list[LifecycleHook] = []


def register_lifecycle_hook(hook: LifecycleHook) -> None:
    if hook not in _LIFECYCLE_HOOKS:
        _LIFECYCLE_HOOKS.append(hook)


def clear_lifecycle_hooks() -> None:
    _LIFECYCLE_HOOKS.clear()


def list_lifecycle_hooks() -> list[LifecycleHook]:
    return list(_LIFECYCLE_HOOKS)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _runtime_metadata(payload: LifecycleHookPayload) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "tracking_kind": "agent_task_lifecycle",
        "lifecycle_event": _to_text(payload.get("event")),
        "task_id": _to_text(payload.get("task_id")),
        "task_status": _to_text(payload.get("task_status")),
        "task_type": _to_text(payload.get("task_type")),
        "worker_id": str(payload.get("worker_id") or ""),
        "model": str(payload.get("model") or ""),
    }
    if "route_is_paid" in payload:
        metadata["route_is_paid"] = bool(payload.get("route_is_paid"))
    if "ok" in payload:
        metadata["ok"] = bool(payload.get("ok"))
    if payload.get("reason"):
        metadata["reason"] = str(payload.get("reason") or "")
    if payload.get("error"):
        metadata["error"] = str(payload.get("error") or "")[:800]
    if payload.get("failure_category"):
        metadata["failure_category"] = str(payload.get("failure_category") or "")
    if "retry_count" in payload:
        try:
            metadata["retry_count"] = int(payload.get("retry_count") or 0)
        except (TypeError, ValueError):
            pass
    if payload.get("blind_spot"):
        metadata["blind_spot"] = str(payload.get("blind_spot") or "")[:200]
    return metadata


def _record_runtime_lifecycle_event(payload: LifecycleHookPayload) -> None:
    if not runtime_subscriber_enabled():
        return
    task_payload: dict[str, Any] = {
        "direction": str(payload.get("direction") or ""),
        "context": payload.get("task_context") if isinstance(payload.get("task_context"), dict) else {},
    }
    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-lifecycle",
            method="RUN",
            status_code=_event_status_code(payload.get("task_status")),
            runtime_ms=1.0,
            idea_id=agent_service.resolve_runtime_idea_id_for_task(task_payload),
            metadata=_runtime_metadata(payload),
        )
    )


def _append_jsonl_lifecycle_event(payload: LifecycleHookPayload) -> None:
    if not jsonl_subscriber_enabled():
        return

    row = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tracking_kind": "agent_task_lifecycle",
        "event": _to_text(payload.get("event")),
        "task_id": _to_text(payload.get("task_id")),
        "task_type": _to_text(payload.get("task_type")),
        "task_status": _to_text(payload.get("task_status")),
        "worker_id": _to_text(payload.get("worker_id")),
        "model": _to_text(payload.get("model")),
        "ok": bool(payload.get("ok")) if "ok" in payload else None,
        "reason": _to_text(payload.get("reason")),
        "error": _to_text(payload.get("error"))[:800],
    }
    if "route_is_paid" in payload:
        row["route_is_paid"] = bool(payload.get("route_is_paid"))

    path = jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")

    max_lines = jsonl_max_lines()
    if max_lines is None:
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= max_lines:
        return
    trimmed = lines[-max_lines:]
    path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def dispatch_lifecycle_event(
    event: str,
    *,
    task_id: str,
    task: dict[str, Any],
    **extra: Any,
) -> None:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    payload: LifecycleHookPayload = {
        "event": str(event or "").strip(),
        "task_id": str(task_id or "").strip(),
        "task_type": _to_text(task.get("task_type")),
        "task_status": _to_text(task.get("status")),
        "model": str(task.get("model") or context.get("model_override") or ""),
        "direction": str(task.get("direction") or ""),
        "task_context": context,
    }
    if context.get("last_failure_category"):
        payload["failure_category"] = str(context.get("last_failure_category") or "")
    if "retry_count" in context:
        payload["retry_count"] = context.get("retry_count")
    if context.get("blind_spot"):
        payload["blind_spot"] = str(context.get("blind_spot") or "")
    payload.update(extra)

    try:
        _record_runtime_lifecycle_event(payload)
    except Exception:
        pass
    try:
        _append_jsonl_lifecycle_event(payload)
    except Exception:
        pass

    for hook in list_lifecycle_hooks():
        try:
            hook(dict(payload))
        except Exception:
            continue


def summarize_lifecycle_events(
    *,
    seconds: int = 3600,
    limit: int = 500,
    task_id: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    return _summarize_lifecycle_events(seconds=seconds, limit=limit, task_id=task_id, source=source)
