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

from app.config_loader import get_bool, get_str


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
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = (
        os.getenv("AGENT_TASKS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or get_str("agent_tasks", "database_url")
        or ""
    ).strip()
    return url


def enabled() -> bool:
    persist_override = os.getenv("AGENT_TASKS_PERSIST", "").strip().lower()
    if persist_override in {"0", "false", "no", "off"}:
        return False
    use_db_override = os.getenv("AGENT_TASKS_USE_DB", "").strip().lower()
    if use_db_override in {"0", "false", "no", "off"}:
        return False
    if not _database_url():
        return False
    if use_db_override in {"1", "true", "yes", "on"}:
        return True
    return get_bool("agent_tasks", "use_db", default=True)


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


def _column_ddl(column: Any) -> str:
    """Render a best-effort ADD COLUMN DDL fragment for a SQLAlchemy Column.

    We stay conservative: always add as NULL so we never fail on tables
    that already have rows. Tenants can backfill later.
    """
    from sqlalchemy.schema import CreateColumn
    try:
        return str(CreateColumn(column).compile(dialect=None)).strip()
    except Exception:
        # Fallback: just name + TEXT, good enough for Postgres/SQLite text.
        return f'"{column.name}" TEXT'


def _sync_missing_columns(engine: Any, table: Any) -> list[str]:
    """Add any columns present in the SQLAlchemy model but missing in the DB.

    Returns the list of column names added. Each column is added as
    NULL-able to avoid NOT NULL migration pain; the application is
    expected to backfill before enforcing constraints.
    """
    try:
        insp = inspect(engine)
        if table.name not in insp.get_table_names():
            return []
        live_cols = {c["name"] for c in insp.get_columns(table.name)}
    except Exception:
        return []
    added: list[str] = []
    with engine.begin() as conn:
        for col in table.columns:
            if col.name in live_cols:
                continue
            try:
                ddl = _column_ddl(col)
                # ADD COLUMN IF NOT EXISTS is Postgres-only; we've already
                # filtered via inspector, so use plain ADD COLUMN.
                conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}')
                added.append(col.name)
            except Exception:
                # Best-effort: continue past failures (e.g. dialect mismatch).
                # A failed auto-migration surfaces the same error as before.
                continue
    return added


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
    else:
        # Auto-migrate: add any model columns that are missing on the live
        # table. Guards against deploy drift (a column added to the model
        # but the live DB never received the ALTER). Always NULL-able,
        # so it's safe on populated tables.
        _sync_missing_columns(engine, AgentTaskRecord.__table__)
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


def _row_to_payload(
    row: AgentTaskRecord,
    *,
    include_output: bool = True,
    include_command: bool = True,
) -> dict[str, Any]:
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
        "command": row.command if include_command else "",
        "output": row.output if include_output else None,
        "output_summary": row.output_summary,
        "context": context,
        "progress_pct": row.progress_pct,
        "current_step": row.current_step,
        "decision_prompt": row.decision_prompt,
        "decision": row.decision,
        "error_summary": row.error_summary,
        "error_category": row.error_category,
        "claimed_by": row.claimed_by,
        "claimed_at": _serialize_dt(row.claimed_at),
        "created_at": _serialize_dt(row.created_at),
        "updated_at": _serialize_dt(row.updated_at),
        "started_at": _serialize_dt(row.started_at),
        "tier": row.tier,
        "workspace_id": row.workspace_id,
    }


def _minimal_columns(*, include_output: bool, include_command: bool) -> tuple[Any, ...]:
    columns: list[Any] = [
        AgentTaskRecord.id,
        AgentTaskRecord.direction,
        AgentTaskRecord.task_type,
        AgentTaskRecord.status,
        AgentTaskRecord.model,
        AgentTaskRecord.output_summary,
        AgentTaskRecord.context_json,
        AgentTaskRecord.progress_pct,
        AgentTaskRecord.current_step,
        AgentTaskRecord.decision_prompt,
        AgentTaskRecord.decision,
        AgentTaskRecord.error_summary,
        AgentTaskRecord.error_category,
        AgentTaskRecord.claimed_by,
        AgentTaskRecord.claimed_at,
        AgentTaskRecord.created_at,
        AgentTaskRecord.updated_at,
        AgentTaskRecord.started_at,
        AgentTaskRecord.tier,
        AgentTaskRecord.workspace_id,
    ]
    if include_command:
        columns.append(AgentTaskRecord.command)
    if include_output:
        columns.append(AgentTaskRecord.output)
    return tuple(columns)


def load_tasks(
    *,
    include_output: bool = True,
    include_command: bool = True,
) -> list[dict[str, Any]]:
    if not enabled():
        return []
    ensure_schema()
    with _session() as session:
        query = session.query(AgentTaskRecord)
        if not include_output or not include_command:
            query = query.options(
                load_only(*_minimal_columns(include_output=include_output, include_command=include_command))
            )
        rows = query.order_by(AgentTaskRecord.created_at.desc()).all()
    return [
        _row_to_payload(
            row,
            include_output=include_output,
            include_command=include_command,
        )
        for row in rows
    ]


def load_task(
    task_id: str,
    *,
    include_output: bool = True,
    include_command: bool = True,
) -> dict[str, Any] | None:
    if not enabled():
        return None
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        return None
    ensure_schema()
    with _session() as session:
        query = session.query(AgentTaskRecord)
        if not include_output or not include_command:
            query = query.options(
                load_only(*_minimal_columns(include_output=include_output, include_command=include_command))
            )
        row = query.filter(AgentTaskRecord.id == normalized_task_id).first()
    if row is None:
        return None
    return _row_to_payload(
        row,
        include_output=include_output,
        include_command=include_command,
    )


def load_tasks_page(
    *,
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_output: bool = False,
    include_command: bool = False,
    workspace_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    if not enabled():
        return [], 0
    ensure_schema()
    bounded_limit = max(1, min(int(limit), 1000))
    bounded_offset = max(0, int(offset))
    with _session() as session:
        base_query = session.query(AgentTaskRecord)
        if status:
            base_query = base_query.filter(AgentTaskRecord.status == str(status))
        if task_type:
            base_query = base_query.filter(AgentTaskRecord.task_type == str(task_type))
        if workspace_id:
            ws = str(workspace_id).strip()
            if ws:
                # Default workspace also matches NULL workspace_id rows
                # (tasks created before denormalization / upstream still
                # emits None for the default tenant).
                if ws == "coherence-network":
                    base_query = base_query.filter(
                        (AgentTaskRecord.workspace_id == ws) | (AgentTaskRecord.workspace_id.is_(None))
                    )
                else:
                    base_query = base_query.filter(AgentTaskRecord.workspace_id == ws)
        total = int(base_query.count() or 0)
        query = base_query.options(
            load_only(*_minimal_columns(include_output=include_output, include_command=include_command))
        )
        rows = (
            query.order_by(AgentTaskRecord.created_at.desc())
            .offset(bounded_offset)
            .limit(bounded_limit)
            .all()
        )
    return [
        _row_to_payload(
            row,
            include_output=include_output,
            include_command=include_command,
        )
        for row in rows
    ], total


def load_attention_tasks(limit: int = 20) -> tuple[list[dict[str, Any]], int]:
    if not enabled():
        return [], 0
    ensure_schema()
    bounded_limit = max(1, min(int(limit), 1000))
    with _session() as session:
        base_query = session.query(AgentTaskRecord).filter(
            AgentTaskRecord.status.in_(("needs_decision", "failed"))
        )
        total = int(base_query.count() or 0)
        rows = (
            base_query.options(
                load_only(*_minimal_columns(include_output=True, include_command=False))
            )
            .order_by(AgentTaskRecord.created_at.desc())
            .limit(bounded_limit)
            .all()
        )
    return [
        _row_to_payload(
            row,
            include_output=True,
            include_command=False,
        )
        for row in rows
    ], total


def load_status_counts() -> dict[str, Any]:
    if not enabled():
        return {"total": 0, "by_status": {}}
    ensure_schema()
    with _session() as session:
        grouped = (
            session.query(AgentTaskRecord.status, func.count(AgentTaskRecord.id))
            .group_by(AgentTaskRecord.status)
            .all()
        )
    by_status: dict[str, int] = {}
    total = 0
    for status, count in grouped:
        key = str(status or "").strip() or "unknown"
        value = int(count or 0)
        by_status[key] = value
        total += value
    return {"total": total, "by_status": by_status}


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
                output_summary=payload.get("output_summary"),
                context_json=json.dumps(payload.get("context") if isinstance(payload.get("context"), dict) else {}),
                progress_pct=payload.get("progress_pct"),
                current_step=payload.get("current_step"),
                decision_prompt=payload.get("decision_prompt"),
                decision=payload.get("decision"),
                error_summary=payload.get("error_summary"),
                error_category=payload.get("error_category"),
                claimed_by=payload.get("claimed_by"),
                claimed_at=_parse_dt(payload.get("claimed_at")),
                created_at=_parse_dt(payload.get("created_at")) or datetime.now(timezone.utc),
                updated_at=_parse_dt(payload.get("updated_at")),
                started_at=_parse_dt(payload.get("started_at")),
                tier=str(payload.get("tier") or "openrouter"),
                workspace_id=(str(payload.get("workspace_id")).strip() or None) if payload.get("workspace_id") is not None else None,
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
        record_output_summary = payload.get("output_summary")
        if record_output_summary is not None:
            row.output_summary = record_output_summary
        row.context_json = json.dumps(payload.get("context") if isinstance(payload.get("context"), dict) else {})
        row.progress_pct = payload.get("progress_pct")
        row.current_step = payload.get("current_step")
        row.decision_prompt = payload.get("decision_prompt")
        row.decision = payload.get("decision")
        # DG-015 fix: persist error fields when provided (don't overwrite with None)
        incoming_error_summary = payload.get("error_summary")
        if incoming_error_summary is not None:
            row.error_summary = incoming_error_summary
        incoming_error_category = payload.get("error_category")
        if incoming_error_category is not None:
            row.error_category = incoming_error_category
        row.claimed_by = payload.get("claimed_by")
        row.claimed_at = _parse_dt(payload.get("claimed_at"))
        row.created_at = _parse_dt(payload.get("created_at")) or row.created_at
        row.updated_at = _parse_dt(payload.get("updated_at"))
        row.started_at = _parse_dt(payload.get("started_at"))
        row.tier = str(payload.get("tier") or row.tier or "openrouter")
        incoming_workspace_id = payload.get("workspace_id")
        if incoming_workspace_id is not None:
            normalized_ws = str(incoming_workspace_id).strip()
            row.workspace_id = normalized_ws or None


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
