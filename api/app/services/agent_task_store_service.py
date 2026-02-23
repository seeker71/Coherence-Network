"""Persistent store for agent tasks with shared DB support."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, load_only, mapped_column, sessionmaker
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


def _row_to_payload(row: AgentTaskRecord, *, include_output: bool = True) -> dict[str, Any]:
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
        "output": row.output if include_output else None,
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


def load_tasks(*, include_output: bool = True) -> list[dict[str, Any]]:
    if not enabled():
        return []
    ensure_schema()
    with _session() as session:
        query = session.query(AgentTaskRecord)
        if not include_output:
            query = query.options(
                load_only(
                    AgentTaskRecord.id,
                    AgentTaskRecord.direction,
                    AgentTaskRecord.task_type,
                    AgentTaskRecord.status,
                    AgentTaskRecord.model,
                    AgentTaskRecord.command,
                    AgentTaskRecord.context_json,
                    AgentTaskRecord.progress_pct,
                    AgentTaskRecord.current_step,
                    AgentTaskRecord.decision_prompt,
                    AgentTaskRecord.decision,
                    AgentTaskRecord.claimed_by,
                    AgentTaskRecord.claimed_at,
                    AgentTaskRecord.created_at,
                    AgentTaskRecord.updated_at,
                    AgentTaskRecord.started_at,
                    AgentTaskRecord.tier,
                )
            )
        rows = query.order_by(AgentTaskRecord.created_at.desc()).all()
    return [_row_to_payload(row, include_output=include_output) for row in rows]


def load_task(task_id: str, *, include_output: bool = True) -> dict[str, Any] | None:
    if not enabled():
        return None
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        return None
    ensure_schema()
    with _session() as session:
        query = session.query(AgentTaskRecord)
        if not include_output:
            query = query.options(
                load_only(
                    AgentTaskRecord.id,
                    AgentTaskRecord.direction,
                    AgentTaskRecord.task_type,
                    AgentTaskRecord.status,
                    AgentTaskRecord.model,
                    AgentTaskRecord.command,
                    AgentTaskRecord.context_json,
                    AgentTaskRecord.progress_pct,
                    AgentTaskRecord.current_step,
                    AgentTaskRecord.decision_prompt,
                    AgentTaskRecord.decision,
                    AgentTaskRecord.claimed_by,
                    AgentTaskRecord.claimed_at,
                    AgentTaskRecord.created_at,
                    AgentTaskRecord.updated_at,
                    AgentTaskRecord.started_at,
                    AgentTaskRecord.tier,
                )
            )
        row = query.filter(AgentTaskRecord.id == normalized_task_id).first()
    if row is None:
        return None
    return _row_to_payload(row, include_output=include_output)


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
        incoming_output = payload.get("output")
        if incoming_output is not None:
            row.output = incoming_output
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


def checkpoint() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False, "count": 0, "max_updated_at": None}
    ensure_schema()
    with _session() as session:
        count_raw, max_updated_at = session.query(
            func.count(AgentTaskRecord.id),
            func.max(func.coalesce(AgentTaskRecord.updated_at, AgentTaskRecord.created_at)),
        ).one()
    count = int(count_raw or 0)
    if isinstance(max_updated_at, datetime) and max_updated_at.tzinfo is None:
        max_updated_at = max_updated_at.replace(tzinfo=timezone.utc)
    return {
        "enabled": True,
        "count": count,
        "max_updated_at": _serialize_dt(max_updated_at) if isinstance(max_updated_at, datetime) else None,
    }
