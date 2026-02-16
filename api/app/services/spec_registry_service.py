"""Structured spec registry persistence service."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, create_engine, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.models.spec_registry import SpecRegistryCreate, SpecRegistryEntry, SpecRegistryUpdate


class Base(DeclarativeBase):
    pass


class SpecRegistryRecord(Base):
    __tablename__ = "spec_registry_entries"

    spec_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    potential_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    idea_id: Mapped[str | None] = mapped_column(String, nullable=True)
    process_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    pseudocode_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_contributor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by_contributor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    configured_portfolio = os.getenv("IDEA_PORTFOLIO_PATH")
    if configured_portfolio:
        base = Path(configured_portfolio)
        if base.suffix.lower() == ".json":
            return base.with_suffix(".governance.db")
        return Path(f"{base}.governance.db")
    return _repo_root() / "api" / "logs" / "governance_registry.db"


def _database_url() -> str:
    configured = (
        os.getenv("GOVERNANCE_DATABASE_URL")
        or os.getenv("GOVERNANCE_DB_URL")
        or os.getenv("DATABASE_URL")
    )
    if configured:
        return configured
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
    url = _database_url()
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
    _ensure_runtime_columns(engine)


def _ensure_runtime_columns(engine: Any) -> None:
    """Backfill newly added tracking columns for existing databases."""
    inspector = inspect(engine)
    if "spec_registry_entries" not in inspector.get_table_names():
        return
    existing = {str(col.get("name")) for col in inspector.get_columns("spec_registry_entries")}
    required: dict[str, str] = {
        "potential_value": "FLOAT NOT NULL DEFAULT 0.0",
        "actual_value": "FLOAT NOT NULL DEFAULT 0.0",
        "estimated_cost": "FLOAT NOT NULL DEFAULT 0.0",
        "actual_cost": "FLOAT NOT NULL DEFAULT 0.0",
    }
    missing = {name: ddl for name, ddl in required.items() if name not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE spec_registry_entries ADD COLUMN {name} {ddl}"))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _to_model(row: SpecRegistryRecord) -> SpecRegistryEntry:
    potential_value = float(row.potential_value or 0.0)
    actual_value = float(row.actual_value or 0.0)
    estimated_cost = float(row.estimated_cost or 0.0)
    actual_cost = float(row.actual_cost or 0.0)
    value_gap = max(potential_value - actual_value, 0.0)
    cost_gap = actual_cost - estimated_cost
    return SpecRegistryEntry(
        spec_id=row.spec_id,
        title=row.title,
        summary=row.summary,
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        value_gap=round(value_gap, 4),
        cost_gap=round(cost_gap, 4),
        estimated_roi=_safe_ratio(potential_value, estimated_cost),
        actual_roi=_safe_ratio(actual_value, actual_cost),
        idea_id=row.idea_id,
        process_summary=row.process_summary,
        pseudocode_summary=row.pseudocode_summary,
        implementation_summary=row.implementation_summary,
        created_by_contributor_id=row.created_by_contributor_id,
        updated_by_contributor_id=row.updated_by_contributor_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_specs(limit: int = 200) -> list[SpecRegistryEntry]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(SpecRegistryRecord)
            .order_by(SpecRegistryRecord.updated_at.desc(), SpecRegistryRecord.spec_id.asc())
            .limit(max(1, min(limit, 1000)))
            .all()
        )
    return [_to_model(row) for row in rows]


def get_spec(spec_id: str) -> SpecRegistryEntry | None:
    ensure_schema()
    with _session() as session:
        row = session.get(SpecRegistryRecord, spec_id)
        if row is None:
            return None
    return _to_model(row)


def create_spec(data: SpecRegistryCreate) -> SpecRegistryEntry | None:
    ensure_schema()
    now = datetime.utcnow()
    with _session() as session:
        existing = session.get(SpecRegistryRecord, data.spec_id)
        if existing is not None:
            return None
        row = SpecRegistryRecord(
            spec_id=data.spec_id,
            title=data.title,
            summary=data.summary,
            potential_value=float(data.potential_value),
            actual_value=float(data.actual_value),
            estimated_cost=float(data.estimated_cost),
            actual_cost=float(data.actual_cost),
            idea_id=data.idea_id,
            process_summary=data.process_summary,
            pseudocode_summary=data.pseudocode_summary,
            implementation_summary=data.implementation_summary,
            created_by_contributor_id=data.created_by_contributor_id,
            updated_by_contributor_id=data.created_by_contributor_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
    return _to_model(row)


def update_spec(spec_id: str, data: SpecRegistryUpdate) -> SpecRegistryEntry | None:
    ensure_schema()
    with _session() as session:
        row = session.get(SpecRegistryRecord, spec_id)
        if row is None:
            return None
        if data.title is not None:
            row.title = data.title
        if data.summary is not None:
            row.summary = data.summary
        if data.potential_value is not None:
            row.potential_value = float(data.potential_value)
        if data.actual_value is not None:
            row.actual_value = float(data.actual_value)
        if data.estimated_cost is not None:
            row.estimated_cost = float(data.estimated_cost)
        if data.actual_cost is not None:
            row.actual_cost = float(data.actual_cost)
        if data.idea_id is not None:
            row.idea_id = data.idea_id
        if data.process_summary is not None:
            row.process_summary = data.process_summary
        if data.pseudocode_summary is not None:
            row.pseudocode_summary = data.pseudocode_summary
        if data.implementation_summary is not None:
            row.implementation_summary = data.implementation_summary
        if data.updated_by_contributor_id is not None:
            row.updated_by_contributor_id = data.updated_by_contributor_id
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.flush()
        session.refresh(row)
    return _to_model(row)


def summary() -> dict[str, Any]:
    ensure_schema()
    with _session() as session:
        count = int(session.query(func.count(SpecRegistryRecord.spec_id)).scalar() or 0)
    return {"count": count}
