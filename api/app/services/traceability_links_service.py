# spec: 181-full-code-traceability
# idea: full-traceability-chain
"""Persisted implementation↔spec links for Phase 1 traceability (full-traceability-chain).

Stores rows from static scans of source files (Python/TS) referencing specs.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String, delete
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


class TraceabilityImplementationLinkRecord(Base):
    """One edge: a source file (optionally a function) claims to implement a spec."""

    __tablename__ = "traceability_implementation_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    spec_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    idea_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    source_file: Mapped[str] = mapped_column(String(1024), nullable=False)
    function_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_type: Mapped[str] = mapped_column(String(64), nullable=False, default="static_comment")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


def replace_all_links(links: list[dict[str, Any]]) -> int:
    """Replace the entire table with a fresh scan result.

    Each dict may contain: spec_id, source_file, line_number, link_type, confidence, idea_id, function_name.
    """
    _ensure_schema()
    now = datetime.now(timezone.utc)
    with _session() as session:
        session.execute(delete(TraceabilityImplementationLinkRecord))
        for row in links:
            session.add(
                TraceabilityImplementationLinkRecord(
                    id=str(uuid4()),
                    spec_id=str(row.get("spec_id") or "")[:512],
                    idea_id=(str(row["idea_id"])[:256] if row.get("idea_id") else None),
                    source_file=str(row.get("source_file") or "")[:1024],
                    function_name=(str(row["function_name"])[:512] if row.get("function_name") else None),
                    line_number=int(row["line_number"]) if row.get("line_number") is not None else None,
                    link_type=str(row.get("link_type") or "static_comment")[:64],
                    confidence=float(row.get("confidence") or 1.0),
                    created_at=now,
                )
            )
        session.commit()
    return len(links)


def list_links(limit: int = 500) -> list[dict[str, Any]]:
    """Return recent rows for API/reporting."""
    _ensure_schema()
    cap = max(1, min(int(limit), 2000))
    with _session() as session:
        rows = (
            session.query(TraceabilityImplementationLinkRecord)
            .order_by(TraceabilityImplementationLinkRecord.created_at.desc())
            .limit(cap)
            .all()
        )
        return [
            {
                "spec_id": r.spec_id,
                "idea_id": r.idea_id,
                "source_file": r.source_file,
                "function_name": r.function_name,
                "line_number": r.line_number,
                "link_type": r.link_type,
                "confidence": r.confidence,
            }
            for r in rows
        ]


def count_links() -> int:
    _ensure_schema()
    from sqlalchemy import func

    with _session() as session:
        return int(session.query(func.count(TraceabilityImplementationLinkRecord.id)).scalar() or 0)
