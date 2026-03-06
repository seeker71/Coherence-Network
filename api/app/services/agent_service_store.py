"""Agent task store: in-memory store, persistence, serialization."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config_loader import get_bool, get_float, get_int, get_str
from app.models.agent import TaskStatus, TaskType
from app.services import agent_task_store_service


class TaskClaimConflictError(RuntimeError):
    """Raised when attempting to start/claim a task already claimed by another worker."""

    def __init__(self, message: str, claimed_by: str | None = None):
        super().__init__(message)
        self.claimed_by = claimed_by


ACTIVE_TASK_STATUSES = {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.NEEDS_DECISION}

# Mutable store and load state (tests and facade access these via agent_service re-exports)
_store: dict[str, dict[str, Any]] = {}
_store_loaded = False
_store_loaded_path: str | None = None
_store_loaded_test_context: str | None = None
_store_loaded_includes_output = False
_store_loaded_at_monotonic = 0.0


def _default_store_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "agent_tasks.json"


def _store_path() -> Path:
    configured = get_str("agent_tasks", "path") or os.getenv("AGENT_TASKS_PATH", "").strip()
    if configured:
        return Path(configured)
    return _default_store_path()


def _persistence_enabled() -> bool:
    env_val = os.getenv("AGENT_TASKS_PERSIST")
    if env_val is not None:
        return env_val.strip().lower() not in {"0", "false", "no", "off"}
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return get_bool("agent_tasks", "persist", default=False)


def _db_store_reload_ttl_seconds() -> float:
    env_val = os.getenv("AGENT_TASKS_DB_RELOAD_TTL_SECONDS")
    if env_val is not None:
        try:
            return max(0.0, min(float(env_val.strip()), 300.0))
        except ValueError:
            pass
    return max(0.0, min(get_float("agent_tasks", "db_reload_ttl_seconds", 120.0), 300.0))


def _max_task_output_chars() -> int:
    env_val = os.getenv("AGENT_TASK_OUTPUT_MAX_CHARS")
    if env_val is not None:
        try:
            return max(500, min(int(env_val.strip()), 200000))
        except ValueError:
            pass
    return max(500, min(get_int("agent_tasks", "task_output_max_chars", 4000), 200000))


def _sanitize_task_output(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    max_chars = _max_task_output_chars()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in task.items():
        if isinstance(value, (TaskStatus, TaskType)):
            out[key] = value.value
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _deserialize_task(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    task_id = raw.get("id")
    direction = raw.get("direction")
    command = raw.get("command")
    model = raw.get("model")
    if not all(isinstance(v, str) and v.strip() for v in (task_id, direction, model)):
        return None
    if not isinstance(command, str):
        command = ""

    task_type_raw = raw.get("task_type")
    status_raw = raw.get("status")
    try:
        task_type = task_type_raw if isinstance(task_type_raw, TaskType) else TaskType(str(task_type_raw))
        status = status_raw if isinstance(status_raw, TaskStatus) else TaskStatus(str(status_raw))
    except ValueError:
        return None

    created_at = _parse_dt(raw.get("created_at"))
    if created_at is None:
        created_at = _now()

    task: dict[str, Any] = {
        "id": task_id.strip(),
        "direction": direction.strip(),
        "task_type": task_type,
        "status": status,
        "model": model.strip(),
        "command": command.strip() or "PATCH /api/agent/tasks/{task_id}",
        "output": raw.get("output"),
        "context": raw.get("context") if isinstance(raw.get("context"), dict) else None,
        "progress_pct": raw.get("progress_pct"),
        "current_step": raw.get("current_step"),
        "decision_prompt": raw.get("decision_prompt"),
        "decision": raw.get("decision"),
        "claimed_by": raw.get("claimed_by"),
        "claimed_at": _parse_dt(raw.get("claimed_at")),
        "created_at": created_at,
        "updated_at": _parse_dt(raw.get("updated_at")),
        "started_at": _parse_dt(raw.get("started_at")),
        "tier": raw.get("tier") if isinstance(raw.get("tier"), str) else "openrouter",
    }
    return task


def _load_store_from_disk(
    *, include_output: bool = True, path: Path | None = None
) -> dict[str, dict[str, Any]]:
    if not _persistence_enabled() and path is None:
        return {}
    if agent_task_store_service.enabled() and path is None:
        loaded: dict[str, dict[str, Any]] = {}
        for raw in agent_task_store_service.load_tasks(include_output=include_output):
            task = _deserialize_task(raw)
            if not task:
                continue
            loaded[task["id"]] = task
        return loaded
    path = path if path is not None else _store_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    loaded = {}
    for raw in rows:
        task = _deserialize_task(raw)
        if not task:
            continue
        loaded[task["id"]] = task
    return loaded


def _save_store_to_disk() -> None:
    if not _persistence_enabled():
        return
    if agent_task_store_service.enabled():
        for task in _store.values():
            agent_task_store_service.upsert_task(_serialize_task(task))
        return
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tasks": [_serialize_task(task) for task in _store.values()],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_store_loaded(*, force_reload: bool = False, include_output: bool = False) -> None:
    global _store_loaded, _store_loaded_path, _store_loaded_test_context
    global _store_loaded_includes_output, _store_loaded_at_monotonic
    store_path = _store_path()
    current_path = str(store_path)
    current_test = os.getenv("PYTEST_CURRENT_TEST")

    if not _persistence_enabled() and current_test and _store_loaded_test_context != current_test:
        _store.clear()
        _store_loaded = False
        _store_loaded_path = None
        _store_loaded_test_context = current_test
        _store_loaded_includes_output = False
        _store_loaded_at_monotonic = 0.0

    if not _persistence_enabled():
        return

    if agent_task_store_service.enabled():
        now = time.monotonic()
        need_upgrade = include_output and not _store_loaded_includes_output
        expired = (now - _store_loaded_at_monotonic) >= _db_store_reload_ttl_seconds()
        should_reload = force_reload or not _store_loaded or need_upgrade or expired
        if should_reload:
            _store.clear()
            _store.update(_load_store_from_disk(include_output=include_output))
            _store_loaded = True
            _store_loaded_path = current_path
            _store_loaded_test_context = current_test
            _store_loaded_includes_output = include_output
            _store_loaded_at_monotonic = now
        return

    if _store_loaded and _store_loaded_path == current_path and not force_reload:
        return
    _store.clear()
    _store.update(_load_store_from_disk(include_output=include_output, path=store_path))
    _store_loaded = True
    _store_loaded_path = current_path
    _store_loaded_test_context = current_test
    _store_loaded_includes_output = include_output
    _store_loaded_at_monotonic = time.monotonic()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    import secrets
    return f"task_{secrets.token_hex(8)}"


def _load_task_from_db(task_id: str, *, include_output: bool) -> dict[str, Any] | None:
    if not agent_task_store_service.enabled():
        return None
    raw = agent_task_store_service.load_task(task_id, include_output=include_output)
    if not isinstance(raw, dict):
        return None
    task = _deserialize_task(raw)
    if task is None:
        return None
    _store[task["id"]] = task
    return task


def clear_store() -> None:
    """Clear in-memory store (for testing)."""
    _ensure_store_loaded(
        force_reload=agent_task_store_service.enabled(),
        include_output=False,
    )
    _store.clear()
    if agent_task_store_service.enabled():
        agent_task_store_service.clear_tasks()
    else:
        _save_store_to_disk()
