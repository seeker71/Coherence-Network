"""Shared run-state lease tracking for agent workers."""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class AgentRunStateRecord(Base):
    __tablename__ = "agent_run_state"

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    branch: Mapped[str] = mapped_column(String, nullable=False, default="")
    repo_path: Mapped[str] = mapped_column(String, nullable=False, default="")
    head_sha: Mapped[str] = mapped_column(String, nullable=False, default="")
    checkpoint_sha: Mapped[str] = mapped_column(String, nullable=False, default="")
    failure_class: Mapped[str] = mapped_column(String, nullable=False, default="")
    next_action: Mapped[str] = mapped_column(String, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""
_LOCAL_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fallback_path() -> Path:
    return _repo_root() / "logs" / "agent_run_state.json"


def _database_url() -> str:
    return (os.getenv("AGENT_RUN_STATE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


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


def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


def _table_exists(engine: Any, table_name: str) -> bool:
    try:
        return table_name in inspect(engine).get_table_names()
    except Exception:
        return False


def _engine():
    url = _database_url()
    if not url:
        return None
    if _ENGINE_CACHE["engine"] is not None and _ENGINE_CACHE["url"] == url:
        return _ENGINE_CACHE["engine"]
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    _SCHEMA_INITIALIZED = False
    _SCHEMA_INITIALIZED_URL = ""
    engine = _create_engine(url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = engine
    _ENGINE_CACHE["sessionmaker"] = SessionLocal
    return engine


def _ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        engine = _engine()
        if engine is not None and _table_exists(engine, "agent_run_state"):
            return
        _SCHEMA_INITIALIZED = False
        _SCHEMA_INITIALIZED_URL = ""
    engine = _engine()
    if engine is None or not url:
        return
    if not _table_exists(engine, "agent_run_state"):
        Base.metadata.create_all(bind=engine)
    _SCHEMA_INITIALIZED = True
    _SCHEMA_INITIALIZED_URL = url


@contextmanager
def _session() -> Session:
    SessionLocal = _ENGINE_CACHE.get("sessionmaker")
    if SessionLocal is None:
        _engine()
        SessionLocal = _ENGINE_CACHE.get("sessionmaker")
    if SessionLocal is None:
        raise RuntimeError("agent run state session unavailable")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _safe_metadata(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _row_to_payload(row: AgentRunStateRecord, *, claimed: bool, detail: str | None = None) -> dict[str, Any]:
    return {
        "claimed": bool(claimed),
        "task_id": row.task_id,
        "run_id": row.run_id,
        "worker_id": row.worker_id,
        "status": row.status,
        "attempt": int(row.attempt),
        "branch": row.branch or "",
        "repo_path": row.repo_path or "",
        "head_sha": row.head_sha or "",
        "checkpoint_sha": row.checkpoint_sha or "",
        "failure_class": row.failure_class or "",
        "next_action": row.next_action or "",
        "lease_expires_at": _iso(_aware(row.lease_expires_at)),
        "last_heartbeat_at": _iso(_aware(row.last_heartbeat_at)),
        "updated_at": _iso(_aware(row.updated_at)),
        "detail": detail,
    }


def _patch_row(row: AgentRunStateRecord, patch: dict[str, Any]) -> None:
    if "status" in patch:
        row.status = str(patch.get("status") or "").strip() or row.status
    if "attempt" in patch:
        try:
            row.attempt = max(1, int(patch.get("attempt")))
        except Exception:
            pass
    if "branch" in patch:
        row.branch = str(patch.get("branch") or "").strip()
    if "repo_path" in patch:
        row.repo_path = str(patch.get("repo_path") or "").strip()
    if "head_sha" in patch:
        row.head_sha = str(patch.get("head_sha") or "").strip()
    if "checkpoint_sha" in patch:
        row.checkpoint_sha = str(patch.get("checkpoint_sha") or "").strip()
    if "failure_class" in patch:
        row.failure_class = str(patch.get("failure_class") or "").strip()
    if "next_action" in patch:
        row.next_action = str(patch.get("next_action") or "").strip()
    if "metadata" in patch:
        row.metadata_json = json.dumps(_safe_metadata(patch.get("metadata")))
    if "started_at" in patch and isinstance(patch.get("started_at"), str):
        try:
            row.started_at = datetime.fromisoformat(str(patch.get("started_at")))
        except Exception:
            pass
    if "completed_at" in patch and isinstance(patch.get("completed_at"), str):
        try:
            row.completed_at = datetime.fromisoformat(str(patch.get("completed_at")))
        except Exception:
            pass
    if "last_heartbeat_at" in patch and isinstance(patch.get("last_heartbeat_at"), str):
        try:
            row.last_heartbeat_at = datetime.fromisoformat(str(patch.get("last_heartbeat_at")))
        except Exception:
            pass


def _read_local() -> dict[str, Any]:
    path = _fallback_path()
    if not path.exists():
        return {"tasks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": {}}
    if not isinstance(payload, dict):
        return {"tasks": {}}
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        payload["tasks"] = {}
    return payload


def _write_local(payload: dict[str, Any]) -> None:
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _claim_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int,
    attempt: int,
    branch: str,
    repo_path: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _now()
    lease_until = now + timedelta(seconds=lease_seconds)
    with _LOCAL_LOCK:
        payload = _read_local()
        tasks = payload.setdefault("tasks", {})
        current = tasks.get(task_id)
        if isinstance(current, dict):
            owner_run = str(current.get("run_id") or "")
            owner_worker = str(current.get("worker_id") or "")
            owner_status = str(current.get("status") or "")
            expires_raw = str(current.get("lease_expires_at") or "")
            try:
                expires_at = datetime.fromisoformat(expires_raw) if expires_raw else now - timedelta(seconds=1)
            except Exception:
                expires_at = now - timedelta(seconds=1)
            active_owner = expires_at > now and not _terminal_status(owner_status)
            if active_owner and (owner_run != run_id or owner_worker != worker_id):
                return {
                    "claimed": False,
                    "task_id": task_id,
                    "run_id": owner_run,
                    "worker_id": owner_worker,
                    "status": owner_status,
                    "attempt": int(current.get("attempt") or 0) or None,
                    "branch": str(current.get("branch") or ""),
                    "repo_path": str(current.get("repo_path") or ""),
                    "head_sha": str(current.get("head_sha") or ""),
                    "checkpoint_sha": str(current.get("checkpoint_sha") or ""),
                    "failure_class": str(current.get("failure_class") or ""),
                    "next_action": str(current.get("next_action") or ""),
                    "lease_expires_at": _iso(expires_at),
                    "last_heartbeat_at": str(current.get("last_heartbeat_at") or ""),
                    "updated_at": str(current.get("updated_at") or ""),
                    "detail": "lease_owned_by_other_worker",
                }

        row = {
            "task_id": task_id,
            "run_id": run_id,
            "worker_id": worker_id,
            "status": "running",
            "attempt": int(attempt),
            "branch": branch,
            "repo_path": repo_path,
            "head_sha": "",
            "checkpoint_sha": "",
            "failure_class": "",
            "next_action": "execute_command",
            "metadata": metadata or {},
            "lease_expires_at": _iso(lease_until),
            "last_heartbeat_at": _iso(now),
            "started_at": _iso(now),
            "updated_at": _iso(now),
            "completed_at": None,
        }
        tasks[task_id] = row
        _write_local(payload)
        return {**row, "claimed": True, "detail": None}


def claim_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int = 120,
    attempt: int = 1,
    branch: str = "",
    repo_path: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lease_seconds = _normalize_lease_seconds(lease_seconds)
    if not _database_url():
        return _claim_local(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            attempt=attempt,
            branch=branch,
            repo_path=repo_path,
            metadata=metadata,
        )

    _ensure_schema()
    now = _now()
    lease_until = now + timedelta(seconds=lease_seconds)
    with _session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is not None:
            owner_active = _aware(row.lease_expires_at) > now and not _terminal_status(row.status)
            owner_same = row.run_id == run_id and row.worker_id == worker_id
            if owner_active and not owner_same:
                return _row_to_payload(row, claimed=False, detail="lease_owned_by_other_worker")

        if row is None:
            row = AgentRunStateRecord(
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                status="running",
                attempt=max(1, int(attempt)),
                branch=branch,
                repo_path=repo_path,
                head_sha="",
                checkpoint_sha="",
                failure_class="",
                next_action="execute_command",
                metadata_json=json.dumps(metadata or {}),
                lease_expires_at=lease_until,
                last_heartbeat_at=now,
                started_at=now,
                updated_at=now,
                completed_at=None,
            )
            session.add(row)
        else:
            row.run_id = run_id
            row.worker_id = worker_id
            row.status = "running"
            row.attempt = max(1, int(attempt))
            row.branch = branch
            row.repo_path = repo_path
            row.metadata_json = json.dumps(metadata or {})
            row.lease_expires_at = lease_until
            row.last_heartbeat_at = now
            row.updated_at = now
            if row.started_at is None:
                row.started_at = now
        session.flush()
        return _row_to_payload(row, claimed=True)


def _update_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any],
    lease_seconds: int | None,
    require_owner: bool,
) -> dict[str, Any]:
    now = _now()
    with _LOCAL_LOCK:
        payload = _read_local()
        tasks = payload.setdefault("tasks", {})
        row = tasks.get(task_id)
        if not isinstance(row, dict):
            return {"claimed": False, "task_id": task_id, "detail": "run_state_not_found"}
        owner_ok = str(row.get("run_id") or "") == run_id and str(row.get("worker_id") or "") == worker_id
        if require_owner and not owner_ok:
            return {"claimed": False, "task_id": task_id, "detail": "lease_owner_mismatch"}
        if "status" in patch:
            row["status"] = str(patch.get("status") or row.get("status") or "").strip() or row.get("status", "")
        for key in ("attempt", "branch", "repo_path", "head_sha", "checkpoint_sha", "failure_class", "next_action"):
            if key in patch:
                row[key] = patch.get(key)
        if "metadata" in patch and isinstance(patch.get("metadata"), dict):
            row["metadata"] = patch.get("metadata")
        if "completed_at" in patch:
            row["completed_at"] = patch.get("completed_at")
        row["last_heartbeat_at"] = _iso(now)
        if lease_seconds is not None:
            row["lease_expires_at"] = _iso(now + timedelta(seconds=_normalize_lease_seconds(lease_seconds)))
        if _terminal_status(str(row.get("status") or "")):
            row["lease_expires_at"] = _iso(now)
        row["updated_at"] = _iso(now)
        tasks[task_id] = row
        _write_local(payload)
        return {**row, "claimed": True, "detail": None}


def update_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any] | None = None,
    lease_seconds: int | None = None,
    require_owner: bool = True,
) -> dict[str, Any]:
    patch = patch or {}
    if not _database_url():
        return _update_local(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch=patch,
            lease_seconds=lease_seconds,
            require_owner=require_owner,
        )

    _ensure_schema()
    now = _now()
    with _session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is None:
            return {"claimed": False, "task_id": task_id, "detail": "run_state_not_found"}
        if require_owner and (row.run_id != run_id or row.worker_id != worker_id):
            return _row_to_payload(row, claimed=False, detail="lease_owner_mismatch")
        _patch_row(row, patch)
        row.updated_at = now
        row.last_heartbeat_at = now
        if lease_seconds is not None:
            row.lease_expires_at = now + timedelta(seconds=_normalize_lease_seconds(lease_seconds))
        if _terminal_status(row.status):
            row.lease_expires_at = now
            if row.completed_at is None:
                row.completed_at = now
        session.flush()
        return _row_to_payload(row, claimed=True)


def heartbeat_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int = 120,
) -> dict[str, Any]:
    return update_run_state(
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch={"status": "running", "next_action": "execute_command", "last_heartbeat_at": _iso(_now())},
        lease_seconds=lease_seconds,
        require_owner=True,
    )


def get_run_state(task_id: str) -> dict[str, Any] | None:
    if not _database_url():
        with _LOCAL_LOCK:
            payload = _read_local()
            tasks = payload.get("tasks")
            if not isinstance(tasks, dict):
                return None
            row = tasks.get(task_id)
            if not isinstance(row, dict):
                return None
            return {"claimed": True, **row}

    _ensure_schema()
    with _session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is None:
            return None
        return _row_to_payload(row, claimed=True)
