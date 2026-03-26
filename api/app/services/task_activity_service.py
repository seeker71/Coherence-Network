"""Task activity log — in-memory ring buffer for live task visibility.

Tracks what nodes are executing, provides event streams per task,
and supports SSE-based live updates.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

_MAX_ACTIVITY = 1000
_LOCK = threading.Lock()
_ACTIVITY_LOG: list[dict[str, Any]] = []
_TASK_STREAMS: dict[str, list[dict[str, Any]]] = {}
_ACTIVE_TASKS: dict[str, dict[str, Any]] = {}  # task_id -> latest executing event


def log_activity(task_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Record a task activity event.

    event_types: "claimed", "executing", "progress", "output", "completed", "failed", "timeout"
    """
    event: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "task_id": task_id,
        "node_id": data.get("node_id", ""),
        "node_name": data.get("node_name", ""),
        "provider": data.get("provider", ""),
        "event_type": event_type,
        "data": {k: v for k, v in data.items() if k not in ("node_id", "node_name", "provider")},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with _LOCK:
        _ACTIVITY_LOG.append(event)
        if len(_ACTIVITY_LOG) > _MAX_ACTIVITY:
            _ACTIVITY_LOG[:] = _ACTIVITY_LOG[-_MAX_ACTIVITY:]

        if task_id not in _TASK_STREAMS:
            _TASK_STREAMS[task_id] = []
        _TASK_STREAMS[task_id].append(event)

        if event_type in ("claimed", "executing", "progress"):
            _ACTIVE_TASKS[task_id] = event
        elif event_type in ("completed", "failed", "timeout"):
            # Calculate duration from first event to now
            prev = _ACTIVE_TASKS.pop(task_id, None)
            if prev:
                try:
                    start_ts = datetime.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
                    duration_s = (datetime.now(timezone.utc) - start_ts).total_seconds()
                    event["data"]["duration_s"] = round(duration_s, 1)
                except Exception:
                    pass

    return event


def get_activity(
    limit: int = 50,
    task_id: str | None = None,
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent activity, optionally filtered."""
    with _LOCK:
        items = list(_ACTIVITY_LOG)

    if task_id:
        items = [e for e in items if e["task_id"] == task_id]
    if node_id:
        items = [e for e in items if e["node_id"] == node_id]

    return items[-limit:]


def get_task_stream(task_id: str) -> list[dict[str, Any]]:
    """Get all events for a specific task."""
    with _LOCK:
        return list(_TASK_STREAMS.get(task_id, []))


_ACTIVE_TTL_SECONDS = 900  # 15 min — if no update in this window, task is stale


def get_active_tasks() -> list[dict[str, Any]]:
    """Get currently executing tasks across all nodes.

    Filters out stale entries (no heartbeat in _ACTIVE_TTL_SECONDS).
    Enriches with idea_id/idea_name from the task store.
    """
    now = datetime.now(timezone.utc)
    with _LOCK:
        active = []
        stale_ids = []
        for task_id, event in _ACTIVE_TASKS.items():
            try:
                ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                age = (now - ts).total_seconds()
                if age > _ACTIVE_TTL_SECONDS:
                    stale_ids.append(task_id)
                    continue
            except Exception:
                pass
            active.append(dict(event))
        for stale_id in stale_ids:
            _ACTIVE_TASKS.pop(stale_id, None)

    # Enrich with idea context from task store
    try:
        from app.services import agent_service
        for event in active:
            task_id = event.get("task_id", "")
            if task_id and not event.get("data", {}).get("idea_id"):
                task = agent_service.get_task(task_id)
                if isinstance(task, dict):
                    ctx = task.get("context") or {}
                    event.setdefault("data", {})["idea_id"] = ctx.get("idea_id", "")
    except Exception:
        pass

    return active
