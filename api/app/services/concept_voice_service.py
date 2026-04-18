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
    """One lived-experience testimony tied to a concept.

    A voice can ripen into a proposal when a reader finds it worth
    offering to the collective for a vote. The ripening records a
    one-way link ``proposed_as_proposal_id`` — the voice stays where
    it was spoken; the proposal walks forward to meet the collective.
    """

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
    proposed_as_proposal_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    # Engine creation auto-creates tables (checkfirst=True).
    _udb.engine()
    _ensure_ripening_column()


_RIPENING_COL_CHECKED = False


def _ensure_ripening_column() -> None:
    """Heal live SQLite *or* Postgres DBs that predate the voice→proposal link.

    Both dialects support an idempotent ADD COLUMN IF NOT EXISTS on
    their own terms — Postgres with the IF NOT EXISTS keyword, SQLite
    via PRAGMA table_info to check first. Indexes use CREATE INDEX IF
    NOT EXISTS which both dialects accept.
    """
    global _RIPENING_COL_CHECKED
    if _RIPENING_COL_CHECKED:
        return
    try:
        eng = _udb.engine()
        with eng.connect() as conn:
            dialect = conn.dialect.name
            if dialect == "sqlite":
                rows = conn.exec_driver_sql(
                    "PRAGMA table_info(concept_voices)"
                ).fetchall()
                if not rows:
                    return
                names = {r[1] for r in rows}
                if "proposed_as_proposal_id" not in names:
                    conn.exec_driver_sql(
                        "ALTER TABLE concept_voices "
                        "ADD COLUMN proposed_as_proposal_id VARCHAR"
                    )
                    conn.exec_driver_sql(
                        "CREATE INDEX IF NOT EXISTS "
                        "ix_concept_voices_proposed_id "
                        "ON concept_voices(proposed_as_proposal_id)"
                    )
                    conn.commit()
            elif dialect == "postgresql":
                conn.exec_driver_sql(
                    "ALTER TABLE concept_voices "
                    "ADD COLUMN IF NOT EXISTS proposed_as_proposal_id VARCHAR"
                )
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_concept_voices_proposed_id "
                    "ON concept_voices(proposed_as_proposal_id)"
                )
                conn.commit()
    except Exception:
        # Best-effort healing — if it fails the ORM will raise a clearer
        # error on first insert.
        pass
    finally:
        _RIPENING_COL_CHECKED = True


def add_voice(
    *,
    concept_id: str,
    author_name: str,
    body: str,
    locale: str = "en",
    author_id: Optional[str] = None,
    location: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    invited_by: Optional[str] = None,
) -> dict:
    """Record a lived-experience voice on a concept.

    Soft-identity auto-graduation: when the caller provides only
    ``author_name`` (no ``author_id``), a contributor graph node is
    quietly created for them — their voice becomes the registration
    event. The returned dict includes ``author_id``; the web client
    writes it back to localStorage so subsequent voices, reactions,
    and proposals attribute correctly. No signup screen, no private
    key, no gate — you become a contributor by caring enough to
    speak.

    ``device_fingerprint`` disambiguates two contributors who share
    a display name. ``invited_by`` preserves the chain lineage.
    Both are stored on the new contributor's graph properties via
    the shared ``graduate_by_name`` helper.
    """
    _ensure_schema()
    if not concept_id or not body.strip() or not author_name.strip():
        raise ValueError("concept_id, author_name, and body are required")
    trimmed_name = author_name.strip()

    # Auto-graduate via the shared helper so voices + reactions mint
    # contributor nodes the same way.
    if not author_id:
        try:
            from app.services import contributor_service
            cid, _created = contributor_service.graduate_by_name(
                author_name=trimmed_name,
                device_fingerprint=device_fingerprint,
                invited_by=invited_by,
            )
            author_id = cid
        except Exception:
            # Best-effort: if graduation fails, the voice still lands
            # with author_name only — soft identity holds.
            author_id = None

    rec = ConceptVoiceRecord(
        id=uuid4().hex,
        concept_id=concept_id,
        author_name=trimmed_name,
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
        "proposed_as_proposal_id": rec.proposed_as_proposal_id,
    }


def get_voice(voice_id: str) -> Optional[dict]:
    _ensure_schema()
    with _session() as s:
        rec = s.get(ConceptVoiceRecord, voice_id)
    return _to_dict(rec) if rec else None


def ripen_into_proposal(
    voice_id: str,
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
    author_id: Optional[str] = None,
) -> dict:
    """Lift a voice into a proposal the collective can vote on.

    Idempotent: if already ripened, returns the existing proposal id.
    The proposal's title defaults to the voice's first sentence (or its
    body truncated); body defaults to the full voice text. The
    proposal is linked back to the concept where the voice was spoken.
    """
    from app.services import proposal_service
    _ensure_schema()
    with _session() as s:
        rec = s.get(ConceptVoiceRecord, voice_id)
        if rec is None:
            raise ValueError("voice not found")
        if rec.proposed_as_proposal_id:
            existing = proposal_service.get_proposal(rec.proposed_as_proposal_id)
            return {
                "voice": _to_dict(rec),
                "proposal_id": rec.proposed_as_proposal_id,
                "proposal": existing,
                "already_ripened": True,
            }
        voice_dict = _to_dict(rec)
        author_name = rec.author_name
        voice_body = rec.body or ""
        concept_id = rec.concept_id
        locale = rec.locale
    derived_title = (title or _derive_title(voice_body))[:200]
    derived_body = (body or voice_body).strip()
    if not derived_title:
        raise ValueError("could not derive proposal title from voice")

    created = proposal_service.create_proposal(
        title=derived_title,
        body=derived_body,
        author_name=author_name,
        author_id=author_id,
        linked_entity_type="concept",
        linked_entity_id=concept_id,
        locale=locale,
    )
    proposal_id = created.get("id")
    if not proposal_id:
        raise RuntimeError("proposal creation did not return an id")

    with _session() as s:
        rec = s.get(ConceptVoiceRecord, voice_id)
        if rec is None:
            raise ValueError("voice vanished mid-ripening")
        if rec.proposed_as_proposal_id:
            # Second-writer loses the race gracefully.
            return {
                "voice": _to_dict(rec),
                "proposal_id": rec.proposed_as_proposal_id,
                "proposal": proposal_service.get_proposal(rec.proposed_as_proposal_id),
                "already_ripened": True,
            }
        rec.proposed_as_proposal_id = proposal_id
        s.add(rec)
        s.commit()
        s.refresh(rec)
        voice_dict = _to_dict(rec)
    return {
        "voice": voice_dict,
        "proposal_id": proposal_id,
        "proposal": created,
        "already_ripened": False,
    }


def _derive_title(body: str) -> str:
    """Pick a warm one-line title from a voice. First sentence or ~80 chars."""
    s = (body or "").strip()
    if not s:
        return ""
    # First sentence up to a terminator
    for terminator in (". ", "! ", "? ", "\n"):
        idx = s.find(terminator)
        if 0 < idx < 200:
            return s[: idx + 1].strip(".!? ").strip()
    if len(s) <= 120:
        return s
    # Fall back to a gentle truncation at the last word boundary under 120 chars
    truncated = s[:120]
    space = truncated.rfind(" ")
    return (truncated[:space] if space > 40 else truncated).rstrip(".!? ").strip() + "…"
