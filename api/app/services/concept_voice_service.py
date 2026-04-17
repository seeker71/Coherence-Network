"""Concept voices — community write-back on the Living Collective KB.

The 51 Living Collective concepts came to life as broadcast: visuals, stories,
aligned places. A voice closes the loop. Anyone can say "this is how we live
it here" and the concept page carries that testimony alongside the curated
story. Trust-by-default: no moderation queue, no paywall, no gate. A voice
is a short text + an author name + a locale + a timestamp.

This is the organism listening back.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, desc, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


class ConceptVoiceRecord(Base):
    """One lived-experience testimony tied to a concept."""

    __tablename__ = "concept_voices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    locale: Mapped[str] = mapped_column(String, nullable=False, default="en", index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    # Engine creation auto-creates tables (checkfirst=True).
    _udb.engine()


def add_voice(
    *,
    concept_id: str,
    author_name: str,
    body: str,
    locale: str = "en",
    author_id: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    _ensure_schema()
    if not concept_id or not body.strip() or not author_name.strip():
        raise ValueError("concept_id, author_name, and body are required")
    rec = ConceptVoiceRecord(
        id=uuid4().hex,
        concept_id=concept_id,
        author_name=author_name.strip(),
        author_id=author_id,
        locale=locale or "en",
        body=body.strip(),
        location=(location or "").strip() or None,
    )
    with _session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
    return _to_dict(rec)


def list_voices(concept_id: str, limit: int = 50) -> list[dict]:
    _ensure_schema()
    with _session() as s:
        rows = (
            s.execute(
                select(ConceptVoiceRecord)
                .where(ConceptVoiceRecord.concept_id == concept_id)
                .order_by(desc(ConceptVoiceRecord.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [_to_dict(r) for r in rows]


def recent_voices(limit: int = 20) -> list[dict]:
    _ensure_schema()
    with _session() as s:
        rows = (
            s.execute(
                select(ConceptVoiceRecord)
                .order_by(desc(ConceptVoiceRecord.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [_to_dict(r) for r in rows]


def _to_dict(rec: ConceptVoiceRecord) -> dict:
    return {
        "id": rec.id,
        "concept_id": rec.concept_id,
        "author_name": rec.author_name,
        "author_id": rec.author_id,
        "locale": rec.locale,
        "body": rec.body,
        "location": rec.location,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }
