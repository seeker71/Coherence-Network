"""Structured spec registry persistence service."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, create_engine, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.models.spec_registry import SpecRegistryCreate, SpecRegistryEntry, SpecRegistryUpdate
from app.services.spec_cards_service import build_spec_cards_feed_payload
from app.services.unified_db import Base


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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    content_path: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


from app.services import unified_db as _udb

_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""
_LIST_SPECS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "items_by_limit": {},
}
_LIST_SPECS_CACHE_TTL_SECONDS = 60.0


def _database_url() -> str:
    return _udb.database_url()


def _engine():
    return _udb.engine()


def _table_exists(engine_obj: Any, table_name: str) -> bool:
    try:
        return table_name in inspect(engine_obj).get_table_names()
    except Exception:
        return False


def _sessionmaker():
    return _udb.get_sessionmaker()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


def ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        eng = _engine()
        if eng is not None and _table_exists(eng, "spec_registry_entries"):
            return
        _SCHEMA_INITIALIZED = False
        _SCHEMA_INITIALIZED_URL = ""
    if not url:
        return
    eng = _engine()
    if not _table_exists(eng, "spec_registry_entries"):
        _udb.ensure_schema()
    _ensure_runtime_columns(eng)
    _SCHEMA_INITIALIZED = True
    _SCHEMA_INITIALIZED_URL = url


def _invalidate_spec_cache() -> None:
    _LIST_SPECS_CACHE["expires_at"] = 0.0
    _LIST_SPECS_CACHE["items_by_limit"] = {}


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
        "content_path": "VARCHAR NULL",
        "content_hash": "VARCHAR(64) NULL",
    }
    missing = {name: ddl for name, ddl in required.items() if name not in existing}
    if not missing:
        return
    _ALLOWED_DDL_TYPES = {
        "FLOAT NOT NULL DEFAULT 0.0",
        "VARCHAR NULL",
        "VARCHAR(64) NULL",
    }
    with engine.begin() as conn:
        for name, ddl in missing.items():
            assert name.isidentifier(), f"Invalid column name: {name}"
            assert ddl in _ALLOWED_DDL_TYPES, f"Invalid DDL type: {ddl}"
            conn.execute(text(f"ALTER TABLE spec_registry_entries ADD COLUMN {name} {ddl}"))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _graph_node_to_spec(node: dict) -> SpecRegistryEntry:
    """Convert a graph node (type=spec) to a SpecRegistryEntry."""
    potential_value = float(node.get("potential_value") or 0.0)
    actual_value = float(node.get("actual_value") or 0.0)
    estimated_cost = float(node.get("estimated_cost") or 0.0)
    actual_cost = float(node.get("actual_cost") or 0.0)
    value_gap = max(potential_value - actual_value, 0.0)
    cost_gap = actual_cost - estimated_cost
    spec_id = node.get("spec_id") or node.get("id", "").replace("spec-", "")
    return SpecRegistryEntry(
        spec_id=spec_id,
        title=node.get("name", spec_id),
        summary=node.get("description", ""),
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        value_gap=round(value_gap, 4),
        cost_gap=round(cost_gap, 4),
        estimated_roi=_safe_ratio(potential_value, estimated_cost),
        actual_roi=_safe_ratio(actual_value, actual_cost),
        idea_id=node.get("idea_id"),
        process_summary=node.get("process_summary"),
        pseudocode_summary=node.get("pseudocode_summary"),
        implementation_summary=node.get("implementation_summary"),
        created_by_contributor_id=node.get("created_by_contributor_id"),
        updated_by_contributor_id=node.get("updated_by_contributor_id"),
        created_at=node.get("created_at"),
        updated_at=node.get("updated_at"),
        content_path=node.get("content_path"),
        content_hash=node.get("content_hash"),
    )


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
        content_path=getattr(row, "content_path", None),
        content_hash=getattr(row, "content_hash", None),
    )


def count_specs() -> int:
    from app.services import graph_service
    return graph_service.count_nodes(type="spec").get("total", 0)


def list_specs(limit: int = 200, offset: int = 0) -> list[SpecRegistryEntry]:
    from app.services import graph_service
    requested_limit = max(1, min(int(limit), 1000))
    requested_offset = max(0, int(offset))
    result = graph_service.list_nodes(type="spec", limit=requested_limit, offset=requested_offset)
    return [_graph_node_to_spec(n) for n in result.get("items", [])]


def list_specs_for_idea(idea_id: str) -> list[SpecRegistryEntry]:
    """Return all spec nodes whose idea_id property matches the given idea.

    This is the direct spec->idea link: spec frontmatter `idea_id:` is stored
    on the spec node as a property and we query for matches.
    """
    from app.services import graph_service
    result = graph_service.list_nodes(type="spec", limit=1000, offset=0)
    matches = [n for n in result.get("items", []) if n.get("idea_id") == idea_id]
    return [_graph_node_to_spec(n) for n in matches]


def get_spec(spec_id: str) -> SpecRegistryEntry | None:
    from app.services import graph_service
    # Try with and without spec- prefix
    node = graph_service.get_node(f"spec-{spec_id}") or graph_service.get_node(spec_id)
    if not node or node.get("type") != "spec":
        return None
    return _graph_node_to_spec(node)


def create_spec(data: SpecRegistryCreate) -> SpecRegistryEntry | None:
    from app.services import graph_service
    node_id = f"spec-{data.spec_id}"
    if graph_service.get_node(node_id):
        return None  # already exists
    node = graph_service.create_node(
        id=node_id, type="spec", name=data.title,
        description=data.summary or "",
        phase="ice",
        properties={
            "spec_id": data.spec_id,
            "potential_value": float(data.potential_value),
            "actual_value": float(data.actual_value),
            "estimated_cost": float(data.estimated_cost),
            "actual_cost": float(data.actual_cost),
            "idea_id": data.idea_id,
            "process_summary": data.process_summary,
            "pseudocode_summary": data.pseudocode_summary,
            "implementation_summary": data.implementation_summary,
            "created_by_contributor_id": data.created_by_contributor_id,
            "content_path": getattr(data, "content_path", None),
            "content_hash": getattr(data, "content_hash", None),
        },
    )
    _invalidate_spec_cache()
    return _graph_node_to_spec(node) if node else None


def update_spec(spec_id: str, data: SpecRegistryUpdate) -> SpecRegistryEntry | None:
    from app.services import graph_service
    node_id = f"spec-{spec_id}"
    node = graph_service.get_node(node_id)
    if not node:
        return None
    updates = {}
    if data.title is not None:
        updates["name"] = data.title
    if data.summary is not None:
        updates["description"] = data.summary
    for field in ["potential_value", "actual_value", "estimated_cost", "actual_cost",
                   "idea_id", "process_summary", "pseudocode_summary", "implementation_summary",
                   "updated_by_contributor_id", "content_path", "content_hash"]:
        val = getattr(data, field, None)
        if val is not None:
            updates[field] = float(val) if field.endswith("_value") or field.endswith("_cost") else val
    # Separate top-level node fields from properties
    node_updates = {}
    prop_updates = {}
    for k, v in updates.items():
        if k in ("name", "description", "phase"):
            node_updates[k] = v
        else:
            prop_updates[k] = v
    if prop_updates:
        node_updates["properties"] = prop_updates
    updated = graph_service.update_node(node_id, **node_updates)
    _invalidate_spec_cache()
    return _graph_node_to_spec(updated) if updated else None


def build_spec_cards_feed(
    *,
    q: str = "",
    state: str = "all",
    attention: str = "all",
    sort: str = "attention_desc",
    cursor: str | None = None,
    limit: int = 50,
    linked: str = "all",
    min_roi: float | None = None,
    min_value_gap: float | None = None,
) -> dict[str, Any]:
    return build_spec_cards_feed_payload(
        list_specs_fn=lambda limit_arg, offset_arg: list_specs(limit=limit_arg, offset=offset_arg),
        q=q,
        state=state,
        attention=attention,
        sort=sort,
        cursor=cursor,
        limit=limit,
        linked=linked,
        min_roi=min_roi,
        min_value_gap=min_value_gap,
    )


def summary() -> dict[str, Any]:
    ensure_schema()
    with _session() as session:
        count = int(session.query(func.count(SpecRegistryRecord.spec_id)).scalar() or 0)
    return {"count": count}


def storage_info() -> dict[str, Any]:
    ensure_schema()
    url = _database_url()
    with _session() as session:
        count = int(session.query(func.count(SpecRegistryRecord.spec_id)).scalar() or 0)
    backend = "postgresql" if "postgres" in url else "sqlite"
    return {
        "backend": backend,
        "database_url": _redact_database_url(url),
        "spec_count": count,
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
