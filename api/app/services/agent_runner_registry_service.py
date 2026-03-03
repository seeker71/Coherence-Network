"""Runner registry for pull-based workers (DB-backed with local fallback)."""

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


class AgentRunnerRecord(Base):
    __tablename__ = "agent_runners"

    runner_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="idle", index=True)
    host: Mapped[str] = mapped_column(String, nullable=False, default="")
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String, nullable=False, default="")
    active_task_id: Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    active_run_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capabilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""
_LOCAL_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fallback_path() -> Path:
    return _repo_root() / "logs" / "agent_runners.json"


def _database_url() -> str:
    return (os.getenv("AGENT_RUNNER_REGISTRY_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return _now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _aware(value).isoformat()


def _parse_dt(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return _aware(raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return _aware(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None


def _normalize_lease_seconds(value: int | None) -> int:
    lease = 90 if value is None else int(value)
    return max(10, min(3600, lease))


def _normalize_status(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"idle", "running", "offline", "degraded"}:
        return candidate
    return "idle"


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value))
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _is_online(lease_expires_at: datetime | None, now: datetime | None = None) -> bool:
    compare_now = now or _now()
    expires = _aware(lease_expires_at)
    return expires > compare_now


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
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = engine
    _ENGINE_CACHE["sessionmaker"] = session_local
    return engine


def _ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        engine = _engine()
        if engine is not None and _table_exists(engine, "agent_runners"):
            return
        _SCHEMA_INITIALIZED = False
        _SCHEMA_INITIALIZED_URL = ""
    engine = _engine()
    if engine is None or not url:
        return
    if not _table_exists(engine, "agent_runners"):
        Base.metadata.create_all(bind=engine)
    _SCHEMA_INITIALIZED = True
    _SCHEMA_INITIALIZED_URL = url


@contextmanager
def _session() -> Session:
    session_local = _ENGINE_CACHE.get("sessionmaker")
    if session_local is None:
        _engine()
        session_local = _ENGINE_CACHE.get("sessionmaker")
    if session_local is None:
        raise RuntimeError("agent runner registry session unavailable")
    session = session_local()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _row_payload(
    *,
    runner_id: str,
    status: str,
    host: str,
    pid: int | None,
    version: str,
    active_task_id: str,
    active_run_id: str,
    last_error: str,
    metadata: dict[str, Any] | None,
    lease_expires_at: datetime | None,
    last_seen_at: datetime | None,
    updated_at: datetime | None,
) -> dict[str, Any]:
    now = _now()
    return {
        "runner_id": runner_id,
        "status": status,
        "online": _is_online(lease_expires_at, now=now),
        "host": host or "",
        "pid": pid,
        "version": version or "",
        "active_task_id": active_task_id or "",
        "active_run_id": active_run_id or "",
        "last_error": last_error or "",
        "lease_expires_at": _iso(lease_expires_at),
        "last_seen_at": _iso(last_seen_at),
        "updated_at": _iso(updated_at),
        "metadata": metadata or {},
    }


def _record_to_payload(record: AgentRunnerRecord) -> dict[str, Any]:
    try:
        metadata = json.loads(record.metadata_json) if record.metadata_json else {}
    except Exception:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return _row_payload(
        runner_id=record.runner_id,
        status=record.status,
        host=record.host,
        pid=record.pid,
        version=record.version,
        active_task_id=record.active_task_id,
        active_run_id=record.active_run_id,
        last_error=record.last_error,
        metadata=metadata,
        lease_expires_at=record.lease_expires_at,
        last_seen_at=record.last_seen_at,
        updated_at=record.updated_at,
    )


def _read_local() -> dict[str, Any]:
    path = _fallback_path()
    if not path.exists():
        return {"runners": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"runners": {}}
    if not isinstance(payload, dict):
        return {"runners": {}}
    if not isinstance(payload.get("runners"), dict):
        payload["runners"] = {}
    return payload


def _write_local(payload: dict[str, Any]) -> None:
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _normalized_heartbeat(
    *,
    runner_id: str,
    status: str,
    lease_seconds: int,
    host: str,
    pid: int | None,
    version: str,
    active_task_id: str,
    active_run_id: str,
    last_error: str,
    capabilities: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _now()
    lease_until = now + timedelta(seconds=_normalize_lease_seconds(lease_seconds))
    normalized_id = str(runner_id or "").strip()[:200]
    if not normalized_id:
        raise ValueError("runner_id is required")
    merged_metadata: dict[str, Any] = {}
    merged_metadata.update(_safe_dict(metadata))
    safe_capabilities = _safe_dict(capabilities)
    if safe_capabilities:
        merged_metadata["capabilities"] = safe_capabilities
    return {
        "runner_id": normalized_id,
        "status": _normalize_status(status),
        "host": str(host or "").strip()[:200],
        "pid": _safe_int(pid),
        "version": str(version or "").strip()[:200],
        "active_task_id": str(active_task_id or "").strip()[:200],
        "active_run_id": str(active_run_id or "").strip()[:200],
        "last_error": str(last_error or "").strip()[:2000],
        "capabilities": safe_capabilities,
        "metadata": merged_metadata,
        "now": now,
        "lease_until": lease_until,
    }


def _heartbeat_local(row: dict[str, Any]) -> dict[str, Any]:
    with _LOCAL_LOCK:
        payload = _read_local()
        runners = payload.setdefault("runners", {})
        runner_id = str(row["runner_id"])
        now_iso = _iso(row["now"])
        runner_row = {
            "runner_id": runner_id,
            "status": row["status"],
            "host": row["host"],
            "pid": row["pid"],
            "version": row["version"],
            "active_task_id": row["active_task_id"],
            "active_run_id": row["active_run_id"],
            "last_error": row["last_error"],
            "metadata": row["metadata"],
            "lease_expires_at": _iso(row["lease_until"]),
            "last_seen_at": now_iso,
            "updated_at": now_iso,
            "created_at": str((runners.get(runner_id) or {}).get("created_at") or now_iso or ""),
        }
        runners[runner_id] = runner_row
        _write_local(payload)
        return {
            "runner_id": runner_row["runner_id"],
            "status": runner_row["status"],
            "online": True,
            "host": runner_row["host"],
            "pid": runner_row["pid"],
            "version": runner_row["version"],
            "active_task_id": runner_row["active_task_id"],
            "active_run_id": runner_row["active_run_id"],
            "last_error": runner_row["last_error"],
            "lease_expires_at": runner_row["lease_expires_at"],
            "last_seen_at": runner_row["last_seen_at"],
            "updated_at": runner_row["updated_at"],
            "metadata": row["metadata"],
        }


def _heartbeat_db(row: dict[str, Any]) -> dict[str, Any]:
    _ensure_schema()
    runner_id = str(row["runner_id"])
    with _session() as session:
        record = session.get(AgentRunnerRecord, runner_id)
        if record is None:
            record = AgentRunnerRecord(
                runner_id=runner_id,
                status=str(row["status"]),
                host=str(row["host"]),
                pid=row["pid"],
                version=str(row["version"]),
                active_task_id=str(row["active_task_id"]),
                active_run_id=str(row["active_run_id"]),
                last_error=str(row["last_error"]),
                capabilities_json=json.dumps(_safe_dict(row.get("capabilities"))),
                metadata_json=json.dumps(_safe_dict(row.get("metadata"))),
                lease_expires_at=_aware(row.get("lease_until")),
                last_seen_at=_aware(row.get("now")),
                created_at=_aware(row.get("now")),
                updated_at=_aware(row.get("now")),
            )
            session.add(record)
        else:
            record.status = str(row["status"])
            record.host = str(row["host"])
            record.pid = row["pid"]
            record.version = str(row["version"])
            record.active_task_id = str(row["active_task_id"])
            record.active_run_id = str(row["active_run_id"])
            record.last_error = str(row["last_error"])
            record.capabilities_json = json.dumps(_safe_dict(row.get("capabilities")))
            record.metadata_json = json.dumps(_safe_dict(row.get("metadata")))
            record.lease_expires_at = _aware(row.get("lease_until"))
            record.last_seen_at = _aware(row.get("now"))
            record.updated_at = _aware(row.get("now"))
        session.flush()
        return _record_to_payload(record)


def heartbeat_runner(
    *,
    runner_id: str,
    status: str = "idle",
    lease_seconds: int = 90,
    host: str = "",
    pid: int | None = None,
    version: str = "",
    active_task_id: str = "",
    active_run_id: str = "",
    last_error: str = "",
    capabilities: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = _normalized_heartbeat(
        runner_id=runner_id,
        status=status,
        lease_seconds=lease_seconds,
        host=host,
        pid=pid,
        version=version,
        active_task_id=active_task_id,
        active_run_id=active_run_id,
        last_error=last_error,
        capabilities=capabilities,
        metadata=metadata,
    )
    if not _database_url():
        return _heartbeat_local(normalized)
    return _heartbeat_db(normalized)


def list_runners(*, include_stale: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    limited = max(1, min(500, int(limit)))
    now = _now()

    if not _database_url():
        with _LOCAL_LOCK:
            payload = _read_local()
            runners = payload.get("runners")
            if not isinstance(runners, dict):
                return []
            rows: list[dict[str, Any]] = []
            for runner_id, raw in runners.items():
                if not isinstance(raw, dict):
                    continue
                lease_expires_at = _parse_dt(raw.get("lease_expires_at"))
                online = _is_online(lease_expires_at, now=now)
                if not include_stale and not online:
                    continue
                row = _row_payload(
                    runner_id=str(runner_id),
                    status=_normalize_status(str(raw.get("status") or "idle")),
                    host=str(raw.get("host") or ""),
                    pid=_safe_int(raw.get("pid")),
                    version=str(raw.get("version") or ""),
                    active_task_id=str(raw.get("active_task_id") or ""),
                    active_run_id=str(raw.get("active_run_id") or ""),
                    last_error=str(raw.get("last_error") or ""),
                    metadata=_safe_dict(raw.get("metadata")),
                    lease_expires_at=lease_expires_at,
                    last_seen_at=_parse_dt(raw.get("last_seen_at")),
                    updated_at=_parse_dt(raw.get("updated_at")),
                )
                rows.append(row)
            rows.sort(key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)
            return rows[:limited]

    _ensure_schema()
    with _session() as session:
        records = (
            session.query(AgentRunnerRecord)
            .order_by(AgentRunnerRecord.last_seen_at.desc())
            .limit(limited * 3)
            .all()
        )
    rows = [_record_to_payload(record) for record in records]
    if not include_stale:
        rows = [row for row in rows if bool(row.get("online"))]
    return rows[:limited]
