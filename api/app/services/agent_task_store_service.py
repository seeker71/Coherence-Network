"""Persistent store for agent tasks with shared DB support."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class AgentTaskRecord(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    return (
        os.getenv("AGENT_TASKS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()


def enabled() -> bool:
    toggle = os.getenv("AGENT_TASKS_USE_DB")
    if toggle is not None:
        return _truthy(toggle)
    return bool(_database_url())


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


def ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        # Hot path: avoid repeated table introspection for every task poll/update.
        return
    engine = _engine()
    if engine is None or not url:
        return
    if not _table_exists(engine, "agent_tasks"):
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
        raise RuntimeError("agent task store session unavailable")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _parse_dt(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _row_to_payload(row: AgentTaskRecord) -> dict[str, Any]:
    try:
        context = json.loads(row.context_json) if row.context_json else {}
    except Exception:
        context = {}
    if not isinstance(context, dict):
        context = {}
    return {
        "id": row.id,
        "direction": row.direction,
        "task_type": row.task_type,
        "status": row.status,
        "model": row.model,
        "command": row.command,
        "output": row.output,
        "context": context,
        "progress_pct": row.progress_pct,
        "current_step": row.current_step,
        "decision_prompt": row.decision_prompt,
        "decision": row.decision,
        "claimed_by": row.claimed_by,
        "claimed_at": _serialize_dt(row.claimed_at),
        "created_at": _serialize_dt(row.created_at),
        "updated_at": _serialize_dt(row.updated_at),
        "started_at": _serialize_dt(row.started_at),
        "tier": row.tier,
    }


def load_tasks() -> list[dict[str, Any]]:
    if not enabled():
        return []
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(AgentTaskRecord)
            .order_by(AgentTaskRecord.created_at.desc())
            .all()
        )
    return [_row_to_payload(row) for row in rows]


def upsert_task(payload: dict[str, Any]) -> None:
    if not enabled():
        return
    ensure_schema()
    task_id = str(payload.get("id") or "").strip()
    if not task_id:
        return
    with _session() as session:
        row = session.get(AgentTaskRecord, task_id)
        if row is None:
            row = AgentTaskRecord(
                id=task_id,
                direction=str(payload.get("direction") or ""),
                task_type=str(payload.get("task_type") or ""),
                status=str(payload.get("status") or ""),
                model=str(payload.get("model") or ""),
                command=str(payload.get("command") or ""),
                output=payload.get("output"),
                context_json=json.dumps(payload.get("context") if isinstance(payload.get("context"), dict) else {}),
                progress_pct=payload.get("progress_pct"),
                current_step=payload.get("current_step"),
                decision_prompt=payload.get("decision_prompt"),
                decision=payload.get("decision"),
                claimed_by=payload.get("claimed_by"),
                claimed_at=_parse_dt(payload.get("claimed_at")),
                created_at=_parse_dt(payload.get("created_at")) or datetime.now(timezone.utc),
                updated_at=_parse_dt(payload.get("updated_at")),
                started_at=_parse_dt(payload.get("started_at")),
                tier=str(payload.get("tier") or "openrouter"),
            )
            session.add(row)
            return
        row.direction = str(payload.get("direction") or row.direction)
        row.task_type = str(payload.get("task_type") or row.task_type)
        row.status = str(payload.get("status") or row.status)
        row.model = str(payload.get("model") or row.model)
        row.command = str(payload.get("command") or row.command)
        row.output = payload.get("output")
        row.context_json = json.dumps(payload.get("context") if isinstance(payload.get("context"), dict) else {})
        row.progress_pct = payload.get("progress_pct")
        row.current_step = payload.get("current_step")
        row.decision_prompt = payload.get("decision_prompt")
        row.decision = payload.get("decision")
        row.claimed_by = payload.get("claimed_by")
        row.claimed_at = _parse_dt(payload.get("claimed_at"))
        row.created_at = _parse_dt(payload.get("created_at")) or row.created_at
        row.updated_at = _parse_dt(payload.get("updated_at"))
        row.started_at = _parse_dt(payload.get("started_at"))
        row.tier = str(payload.get("tier") or row.tier or "openrouter")


def clear_tasks() -> None:
    if not enabled():
        return
    ensure_schema()
    with _session() as session:
        session.query(AgentTaskRecord).delete()
