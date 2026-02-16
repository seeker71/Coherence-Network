"""DB-backed telemetry persistence for automation usage and friction events."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class TelemetryMetaRecord(Base):
    __tablename__ = "telemetry_meta"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class AutomationUsageSnapshotRecord(Base):
    __tablename__ = "telemetry_automation_usage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FrictionEventRecord(Base):
    __tablename__ = "telemetry_friction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    return _repo_root() / "api" / "logs" / "telemetry_store.db"


def database_url() -> str:
    configured = os.getenv("TELEMETRY_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return str(configured).strip()
    sqlite_path = _default_sqlite_path()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{sqlite_path}"


def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


def _engine():
    url = database_url()
    if _ENGINE_CACHE["engine"] is not None and _ENGINE_CACHE["url"] == url:
        return _ENGINE_CACHE["engine"]
    engine = _create_engine(url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = engine
    _ENGINE_CACHE["sessionmaker"] = SessionLocal
    return engine


def _sessionmaker():
    _engine()
    return _ENGINE_CACHE["sessionmaker"]


@contextmanager
def _session() -> Session:
    SessionLocal = _sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema() -> None:
    engine = _engine()
    Base.metadata.create_all(bind=engine)


def backend_info() -> dict[str, Any]:
    ensure_schema()
    url = database_url()
    backend = "postgresql" if "postgres" in url else "sqlite"
    with _session() as session:
        snapshots = int(session.query(func.count(AutomationUsageSnapshotRecord.id)).scalar() or 0)
        friction_events = int(session.query(func.count(FrictionEventRecord.id)).scalar() or 0)
    return {
        "backend": backend,
        "database_url": _redact_database_url(url),
        "automation_snapshot_rows": snapshots,
        "friction_event_rows": friction_events,
    }


def _redact_database_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, remainder = url.split("://", 1)
    if "@" not in remainder:
        return url
    credentials, host = remainder.split("@", 1)
    if ":" in credentials:
        user = credentials.split(":", 1)[0]
        credentials = f"{user}:***"
    else:
        credentials = "***"
    return f"{scheme}://{credentials}@{host}"


def _meta_get(session: Session, key: str) -> str:
    row = session.get(TelemetryMetaRecord, key)
    if row is None:
        return ""
    return str(row.value or "")


def _meta_set(session: Session, key: str, value: str) -> None:
    row = session.get(TelemetryMetaRecord, key)
    if row is None:
        session.add(TelemetryMetaRecord(key=key, value=value))
    else:
        row.value = value
        session.add(row)


def append_automation_snapshot(payload: dict[str, Any], max_rows: int = 800) -> None:
    ensure_schema()
    snapshot_id = str(payload.get("id") or "")
    provider = str(payload.get("provider") or "unknown")
    collected_at_raw = payload.get("collected_at")
    collected_at = _parse_dt(collected_at_raw)
    serialized = json.dumps(payload, default=str)
    with _session() as session:
        session.add(
            AutomationUsageSnapshotRecord(
                snapshot_id=snapshot_id,
                provider=provider,
                collected_at=collected_at,
                payload_json=serialized,
            )
        )
        if max_rows > 0:
            count = int(session.query(func.count(AutomationUsageSnapshotRecord.id)).scalar() or 0)
            over = max(0, count - int(max_rows))
            if over > 0:
                stale = (
                    session.query(AutomationUsageSnapshotRecord)
                    .order_by(AutomationUsageSnapshotRecord.id.asc())
                    .limit(over)
                    .all()
                )
                for row in stale:
                    session.delete(row)


def list_automation_snapshots(limit: int = 200) -> list[dict[str, Any]]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(AutomationUsageSnapshotRecord)
            .order_by(AutomationUsageSnapshotRecord.id.desc())
            .limit(max(1, min(limit, 5000)))
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def import_automation_snapshots_from_file(path: Path) -> dict[str, int]:
    ensure_schema()
    if not path.exists():
        return {"imported": 0, "skipped": 0}
    marker = f"automation_import::{path.resolve()}"
    with _session() as session:
        if _meta_get(session, marker) == "done":
            return {"imported": 0, "skipped": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"imported": 0, "skipped": 0}
    rows = payload.get("snapshots") if isinstance(payload, dict) else []
    snapshots = rows if isinstance(rows, list) else []
    imported = 0
    skipped = 0
    for row in snapshots:
        if not isinstance(row, dict):
            skipped += 1
            continue
        append_automation_snapshot(row, max_rows=0)
        imported += 1
    with _session() as session:
        _meta_set(session, marker, "done")
    return {"imported": imported, "skipped": skipped}


def append_friction_event(payload: dict[str, Any]) -> None:
    ensure_schema()
    event_id = str(payload.get("id") or "")
    timestamp = _parse_dt(payload.get("timestamp"))
    status = str(payload.get("status") or "open")
    serialized = json.dumps(payload, default=str)
    with _session() as session:
        session.add(
            FrictionEventRecord(
                event_id=event_id,
                timestamp=timestamp,
                status=status,
                payload_json=serialized,
            )
        )


def list_friction_events(limit: int = 1000) -> list[dict[str, Any]]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(FrictionEventRecord)
            .order_by(FrictionEventRecord.id.desc())
            .limit(max(1, min(limit, 10000)))
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def import_friction_events_from_file(path: Path) -> dict[str, int]:
    ensure_schema()
    if not path.exists():
        return {"imported": 0, "skipped": 0}
    marker = f"friction_import::{path.resolve()}"
    with _session() as session:
        if _meta_get(session, marker) == "done":
            return {"imported": 0, "skipped": 0}
    imported = 0
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(payload, dict):
            skipped += 1
            continue
        append_friction_event(payload)
        imported += 1
    with _session() as session:
        _meta_set(session, marker, "done")
    return {"imported": imported, "skipped": skipped}


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
