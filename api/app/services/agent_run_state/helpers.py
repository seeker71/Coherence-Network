"""Path, time, lock, and small helpers for agent run state."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-posix fallback
    fcntl = None

_LOCAL_LOCK = threading.Lock()


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    """Resolve repo root; overridable by patching app.services.agent_run_state_service._repo_root."""
    try:
        from app.services import agent_run_state_service as _facade
        if hasattr(_facade, "_repo_root") and _facade._repo_root is not _repo_root:
            return _facade._repo_root()
    except ImportError:
        pass
    return _default_repo_root()


def _fallback_path() -> Path:
    return _repo_root() / "logs" / "agent_run_state.json"


def _fallback_lock_path() -> Path:
    return _repo_root() / "logs" / "agent_run_state.json.lock"


@contextmanager
def _local_file_lock():
    lock_path = _fallback_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return _now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_lease_seconds(value: int | None) -> int:
    lease = 120 if value is None else int(value)
    return max(15, min(3600, lease))


def _terminal_status(status: str) -> bool:
    return status in {"completed", "failed", "cancelled", "needs_decision"}


def _safe_metadata(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def get_local_lock():
    """Return the module-level lock used for local JSON access (for use by local_store)."""
    return _LOCAL_LOCK
