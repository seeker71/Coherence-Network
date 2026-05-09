"""Substrate string-table — cross-process-stable string interning.

The hash-based allocation used previously for string-recipe instances
(`abs(hash(value)) % (10**9) + 1`) works in-process but is NOT cross-
process stable. Python's hash() is salted differently per process by
default — a pattern serialized in process A would not match the same
pattern serialized in process B.

This module is the substrate-resident replacement. Each unique string
gets a sequentially-allocated instance number that persists in the
database. The same string in any process gets the same instance.

Used by:
  - form_rules.py — for IdentCapture name encoding, RepeatedCapture
    name encoding, Sequence/Repeat markers
  - form_builders.py — for Build/CaptureRef name encoding,
    template markers
  - markdown_frontend.py — for frontmatter shape encoding (future)

The legacy `_STRING_CACHE` dict in form_rules.py becomes a per-process
shortcut: populated by interning, consulted by reverse-lookup. The
substrate is the source of truth.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Session

from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM
# ---------------------------------------------------------------------------


class SubstrateStringORM(Base):
    """One row per unique string ever seen.

    The `instance` column is the auto-allocated sequence number.
    `value` is unique and indexed for round-trip lookup.
    """

    __tablename__ = "substrate_strings"

    instance = Column(Integer, primary_key=True, autoincrement=True)
    value = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("value", name="uq_substrate_strings_value"),
    )


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def intern_string_instance(session: Session, value: str) -> int:
    """Get the substrate-resident instance for `value`. Allocates if new.

    Cross-process stable: the same string always returns the same
    instance, regardless of which process or session interned it first.
    Within a single process, the instance is assigned by the database's
    auto-increment counter (or by allocate-on-first-insert when no
    AUTOINCREMENT is available).
    """
    existing = (
        session.query(SubstrateStringORM)
        .filter_by(value=value)
        .one_or_none()
    )
    if existing is not None:
        return existing.instance

    row = SubstrateStringORM(value=value)
    session.add(row)
    try:
        session.flush()
        return row.instance
    except Exception:
        # Race lost — another process inserted the same value.
        session.rollback()
        existing = (
            session.query(SubstrateStringORM)
            .filter_by(value=value)
            .one_or_none()
        )
        if existing is None:
            raise
        return existing.instance


def lookup_string_value(session: Session, instance: int) -> Optional[str]:
    """Reverse lookup: given an instance number, return the original string."""
    row = (
        session.query(SubstrateStringORM)
        .filter_by(instance=instance)
        .one_or_none()
    )
    return row.value if row is not None else None


def list_strings(session: Session) -> list[tuple[int, str]]:
    """Enumerate the string-table for inspection."""
    rows = session.query(SubstrateStringORM).all()
    return [(r.instance, r.value) for r in rows]
