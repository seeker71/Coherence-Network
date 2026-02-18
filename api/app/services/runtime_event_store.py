"""Persistent runtime event storage backend."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.models.runtime import RuntimeEvent


class Base(DeclarativeBase):
    pass


class RuntimeEventRecord(Base):
    __tablename__ = "runtime_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False, index=True)
    raw_endpoint: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_ms: Mapped[float] = mapped_column(Float, nullable=False)
    idea_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    origin_idea_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    runtime_cost_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""


def _database_url() -> str:
    return (
        os.getenv("RUNTIME_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()


def enabled() -> bool:
    # If a runtime database is configured, prefer DB persistence even when a JSON
    # events path is configured (legacy/optional file store).
    return bool(_database_url())


def backend_info() -> dict[str, Any]:
    url = _database_url()
    backend = "postgresql" if "postgres" in url else ("sqlite" if url else "none")
    return {
        "enabled": enabled(),
        "backend": backend,
        "database_url": _redact_database_url(url) if url else "",
        "events_file_override": bool(os.getenv("RUNTIME_EVENTS_PATH", "").strip()),
    }


def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


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


def _table_exists(engine: Any, table_name: str) -> bool:
    try:
        return table_name in inspect(engine).get_table_names()
    except Exception:
        return False


def ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        engine = _engine()
        if engine is not None and _table_exists(engine, "runtime_events"):
            return
        _SCHEMA_INITIALIZED = False
        _SCHEMA_INITIALIZED_URL = ""
    engine = _engine()
    if engine is None or not url:
        return
    if not _table_exists(engine, "runtime_events"):
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
        raise RuntimeError("runtime event store session unavailable")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def write_event(event: RuntimeEvent) -> None:
    ensure_schema()
    with _session() as session:
        row = RuntimeEventRecord(
            id=event.id,
            source=event.source,
            endpoint=event.endpoint,
            raw_endpoint=event.raw_endpoint or event.endpoint,
            method=event.method,
            status_code=int(event.status_code),
            runtime_ms=float(event.runtime_ms),
            idea_id=event.idea_id,
            origin_idea_id=event.origin_idea_id,
            metadata_json=json.dumps(event.metadata or {}),
            runtime_cost_estimate=float(event.runtime_cost_estimate),
            recorded_at=event.recorded_at,
        )
        session.add(row)


def list_events(limit: int = 100, since: datetime | None = None) -> list[RuntimeEvent]:
    ensure_schema()
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    with _session() as session:
        query = session.query(RuntimeEventRecord)
        if since is not None:
            query = query.filter(RuntimeEventRecord.recorded_at >= since)
        query = query.order_by(RuntimeEventRecord.recorded_at.desc()).limit(max(1, min(limit, 5000)))
        rows = query.all()

    out: list[RuntimeEvent] = []
    for row in rows:
        try:
            metadata = json.loads(row.metadata_json) if row.metadata_json else {}
        except Exception:
            metadata = {}
        recorded_at = row.recorded_at
        if recorded_at.tzinfo is None:
            # SQLite commonly returns naive datetimes even when timezone=True.
            # Normalize to UTC so summary windows can compare safely.
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        out.append(
            RuntimeEvent(
                id=row.id,
                source=row.source,  # type: ignore[arg-type]
                endpoint=row.endpoint,
                raw_endpoint=row.raw_endpoint,
                method=row.method,
                status_code=int(row.status_code),
                runtime_ms=float(row.runtime_ms),
                idea_id=row.idea_id,
                origin_idea_id=row.origin_idea_id,
                metadata=metadata if isinstance(metadata, dict) else {},
                runtime_cost_estimate=float(row.runtime_cost_estimate),
                recorded_at=recorded_at,
            )
        )
    return out


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
