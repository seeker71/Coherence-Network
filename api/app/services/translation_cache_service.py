"""Concept views — equal-status language renderings of a concept, idea, or
contribution. No privileged source language. The anchor (freshest expression)
is whichever view was most recently touched by a human. Stale views re-attune
from the anchor.

Every view row carries:
  - content_hash: sha256 of its own current content (title + description + markdown)
  - translated_from_hash: the content_hash of the view this was rendered from
    (null when the view was authored directly in that language)
  - author_type: original_human | translation_human | translation_machine

Anchor discovery at read time:
  1. Consider all views whose author_type is original_human or translation_human
  2. Pick the one with the latest updated_at
  3. Ties broken by: original_human over translation_human
  The anchor is the living centre. Other views are stale if their
  translated_from_hash doesn't equal the anchor's current content_hash.

History-preserving: every write creates a new row. Prior rows for the same
(entity, lang) flip to status='superseded' but remain for the edit history.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class EntityViewRecord(Base):
    """One language rendering of a concept/idea/contribution. Every language
    is a view; no language is privileged. The anchor emerges from updated_at
    and author_type, not from a hardcoded source.
    """

    __tablename__ = "entity_views"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String, nullable=False, index=True)

    content_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Author of this specific view write
    author_type: Mapped[str] = mapped_column(String, nullable=False)  # see AUTHOR_TYPE_*
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    translator_model: Mapped[str | None] = mapped_column(String, nullable=True)

    # When this view was translated/attuned from another view, point at it
    translated_from_lang: Mapped[str | None] = mapped_column(String, nullable=True)
    translated_from_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # canonical | superseded — always preserved for history
    status: Mapped[str] = mapped_column(String, nullable=False, default="canonical", index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class GlossaryEntryRecord(Base):
    """Per-language felt-sense equivalent for an anchor term — the frequency
    spine of translation.
    """

    __tablename__ = "translation_glossary"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lang: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_term: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_term: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTHOR_TYPE_ORIGINAL_HUMAN = "original_human"
AUTHOR_TYPE_TRANSLATION_HUMAN = "translation_human"
AUTHOR_TYPE_TRANSLATION_MACHINE = "translation_machine"

HUMAN_AUTHOR_TYPES = {AUTHOR_TYPE_ORIGINAL_HUMAN, AUTHOR_TYPE_TRANSLATION_HUMAN}

STATUS_CANONICAL = "canonical"
STATUS_SUPERSEDED = "superseded"


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def content_hash_of(markdown: str, title: str = "", description: str = "") -> str:
    """Deterministic hash across the translatable surface of a view."""
    payload = f"{title}\n\n{description}\n\n{markdown}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def write_view(
    *,
    entity_type: str,
    entity_id: str,
    lang: str,
    content_title: str,
    content_description: str,
    content_markdown: str,
    author_type: str,
    author_id: str | None = None,
    translator_model: str | None = None,
    translated_from_lang: str | None = None,
    translated_from_hash: str | None = None,
    notes: str | None = None,
) -> EntityViewRecord:
    """Write a new view. Any prior canonical row for the same (entity, lang)
    becomes superseded. History preserved.
    """
    _ensure_schema()
    content_hash = content_hash_of(content_markdown, content_title, content_description)
    with _session() as s:
        prior = list(s.scalars(
            select(EntityViewRecord).where(
                EntityViewRecord.entity_type == entity_type,
                EntityViewRecord.entity_id == entity_id,
                EntityViewRecord.lang == lang,
                EntityViewRecord.status == STATUS_CANONICAL,
            )
        ))
        for p in prior:
            p.status = STATUS_SUPERSEDED
            p.updated_at = datetime.now(timezone.utc)

        rec = EntityViewRecord(
            id=uuid4().hex,
            entity_type=entity_type,
            entity_id=entity_id,
            lang=lang,
            content_title=content_title,
            content_description=content_description,
            content_markdown=content_markdown,
            content_hash=content_hash,
            author_type=author_type,
            author_id=author_id,
            translator_model=translator_model,
            translated_from_lang=translated_from_lang,
            translated_from_hash=translated_from_hash,
            status=STATUS_CANONICAL,
            notes=notes,
        )
        s.add(rec)
        s.flush()
        s.refresh(rec)
        return rec


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def canonical_view(entity_type: str, entity_id: str, lang: str) -> EntityViewRecord | None:
    """The single current canonical view for (entity, lang)."""
    _ensure_schema()
    with _session() as s:
        rows = list(s.scalars(
            select(EntityViewRecord).where(
                EntityViewRecord.entity_type == entity_type,
                EntityViewRecord.entity_id == entity_id,
                EntityViewRecord.lang == lang,
                EntityViewRecord.status == STATUS_CANONICAL,
            )
        ))
        if not rows:
            return None
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return rows[0]


def all_canonical_views(entity_type: str, entity_id: str) -> list[EntityViewRecord]:
    """Every canonical view for an entity (one per language)."""
    _ensure_schema()
    with _session() as s:
        rows = list(s.scalars(
            select(EntityViewRecord).where(
                EntityViewRecord.entity_type == entity_type,
                EntityViewRecord.entity_id == entity_id,
                EntityViewRecord.status == STATUS_CANONICAL,
            )
        ))
        # One canonical per (lang) — keep most recent if duplicates slipped in
        by_lang: dict[str, EntityViewRecord] = {}
        for r in rows:
            prev = by_lang.get(r.lang)
            if prev is None or (r.updated_at or datetime.min.replace(tzinfo=timezone.utc)) > (prev.updated_at or datetime.min.replace(tzinfo=timezone.utc)):
                by_lang[r.lang] = r
        return list(by_lang.values())


def find_anchor(views: list[EntityViewRecord]) -> EntityViewRecord | None:
    """The anchor is the most recently human-touched view. Original authoring
    wins ties with translation-human at the same updated_at.
    """
    humans = [v for v in views if v.author_type in HUMAN_AUTHOR_TYPES]
    if not humans:
        return None

    def rank(v: EntityViewRecord) -> tuple:
        origin_rank = 1 if v.author_type == AUTHOR_TYPE_ORIGINAL_HUMAN else 0
        return (v.updated_at, origin_rank)

    humans.sort(key=rank, reverse=True)
    return humans[0]


def is_stale(view: EntityViewRecord, anchor: EntityViewRecord | None) -> bool:
    """A view is stale when it was attuned from an earlier state of the anchor
    and the anchor has since moved. An originally-authored view (no
    translated_from) is never stale — it's a standalone expression in its
    language, not a projection of another view.

    Rules:
    - If this view IS the anchor → not stale
    - If this view was authored directly (translated_from_lang is None) → not stale
    - If translated_from_lang points at the anchor's lang AND the
      translated_from_hash matches the anchor's current content_hash → not stale
    - Otherwise → stale (needs re-attunement from the current anchor)
    """
    if anchor is None or view.id == anchor.id:
        return False
    if view.translated_from_lang is None:
        return False
    if view.translated_from_lang != anchor.lang:
        return True
    return view.translated_from_hash != anchor.content_hash


def list_history(entity_type: str, entity_id: str, lang: str) -> list[EntityViewRecord]:
    """All views for (entity, lang), newest first — canonical + superseded."""
    _ensure_schema()
    with _session() as s:
        rows = list(s.scalars(
            select(EntityViewRecord).where(
                EntityViewRecord.entity_type == entity_type,
                EntityViewRecord.entity_id == entity_id,
                EntityViewRecord.lang == lang,
            )
        ))
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return rows


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

def glossary_for(lang: str) -> list[GlossaryEntryRecord]:
    _ensure_schema()
    with _session() as s:
        rows = list(s.scalars(
            select(GlossaryEntryRecord).where(GlossaryEntryRecord.lang == lang)
        ))
        return rows


def upsert_glossary_entry(
    lang: str, source_term: str, target_term: str, notes: str | None = None
) -> GlossaryEntryRecord:
    _ensure_schema()
    with _session() as s:
        existing = list(s.scalars(
            select(GlossaryEntryRecord).where(
                GlossaryEntryRecord.lang == lang,
                GlossaryEntryRecord.source_term == source_term,
            )
        ))
        if existing:
            rec = existing[0]
            rec.target_term = target_term
            rec.notes = notes
        else:
            rec = GlossaryEntryRecord(
                id=uuid4().hex,
                lang=lang,
                source_term=source_term,
                target_term=target_term,
                notes=notes,
            )
            s.add(rec)
        s.flush()
        s.refresh(rec)
        return rec
