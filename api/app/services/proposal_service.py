"""Proposals — short suggestions the collective can vote on by meeting.

A proposal is a tiny piece of content: a title, a body, an author, an
optional linked entity (idea, concept, spec) and a lifespan. It's not
heavy governance — it's a way for anyone to say "what if we tried this"
and let the collective express resonance through the same meeting
gesture used for every other entity.

Voting happens via reactions on the proposal:
  · care  (💛)  = support
  · amplify (🔥) = strong support
  · move on (➡️)  = decline
Anything else is expression, not vote — it still enters the tally as a
signal but not as yes/no.

The proposal status is computed from the tally, not stored separately,
so there is nothing to stale. When the window closes (resolve_at) the
proposal is *resolved* but reactions keep flowing as commentary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, desc, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


VOTE_EMOJI = {
    "💛": "support",
    "🔥": "amplify",
    "➡️": "decline",
}


class ProposalRecord(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Optional link to an existing entity (e.g. an idea this proposal would change)
    linked_entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    locale: Mapped[str] = mapped_column(String, nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    # Window during which votes actively count. After this, the proposal is
    # "resolved" but the record and reactions stay.
    resolve_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc) + timedelta(days=14)
    )


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    _udb.engine()


def create_proposal(
    *,
    title: str,
    body: str = "",
    author_name: str,
    author_id: Optional[str] = None,
    linked_entity_type: Optional[str] = None,
    linked_entity_id: Optional[str] = None,
    locale: str = "en",
    window_days: int = 14,
) -> dict:
    _ensure_schema()
    if not title.strip():
        raise ValueError("title required")
    if not author_name.strip():
        raise ValueError("author_name required")
    now = datetime.now(timezone.utc)
    rec = ProposalRecord(
        id=uuid4().hex,
        title=title.strip()[:200],
        body=body.strip(),
        author_name=author_name.strip(),
        author_id=author_id,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        locale=locale or "en",
        resolve_at=now + timedelta(days=max(1, window_days)),
    )
    with _session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
    return _to_dict(rec)


def get_proposal(proposal_id: str) -> Optional[dict]:
    _ensure_schema()
    with _session() as s:
        rec = s.get(ProposalRecord, proposal_id)
    return _to_dict(rec) if rec else None


def list_proposals(
    *, limit: int = 50, only_open: bool = True
) -> list[dict]:
    _ensure_schema()
    now = datetime.now(timezone.utc)
    with _session() as s:
        q = select(ProposalRecord).order_by(desc(ProposalRecord.created_at)).limit(limit)
        if only_open:
            q = q.where(ProposalRecord.resolve_at > now).order_by(
                desc(ProposalRecord.created_at)
            ).limit(limit)
        rows = s.execute(q).scalars().all()
    return [_to_dict(r) for r in rows]


def tally(proposal_id: str) -> dict:
    """Read votes from the reactions table, classified by emoji."""
    _ensure_schema()
    from app.services.reaction_service import ReactionRecord
    counts = {"support": 0, "amplify": 0, "decline": 0, "expression": 0}
    with _session() as s:
        rows = s.execute(
            select(ReactionRecord.emoji, func.count(ReactionRecord.id))
            .where(
                ReactionRecord.entity_type == "proposal",
                ReactionRecord.entity_id == proposal_id,
                ReactionRecord.emoji.isnot(None),
            )
            .group_by(ReactionRecord.emoji)
        ).all()
    for emoji, n in rows:
        bucket = VOTE_EMOJI.get(emoji, "expression")
        counts[bucket] = counts.get(bucket, 0) + int(n)
    # Weighted signal: amplify counts double on the support side.
    weighted = {
        "yes": counts["support"] + 2 * counts["amplify"],
        "no": counts["decline"],
    }
    status = _status_from(weighted, counts)
    return {
        "proposal_id": proposal_id,
        "counts": counts,
        "weighted": weighted,
        "status": status,
    }


def _status_from(weighted: dict, counts: dict) -> str:
    total_votes = weighted["yes"] + weighted["no"]
    if total_votes == 0:
        return "quiet"
    if weighted["yes"] >= 3 * max(1, weighted["no"]) and counts["amplify"] > 0:
        return "resonant"
    if weighted["yes"] > weighted["no"]:
        return "warming"
    if weighted["no"] > weighted["yes"]:
        return "cooling"
    return "balanced"


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; normalize to UTC-aware for comparisons."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _to_dict(rec: ProposalRecord) -> dict:
    now = datetime.now(timezone.utc)
    resolve_at = _aware(rec.resolve_at)
    created_at = _aware(rec.created_at)
    return {
        "id": rec.id,
        "title": rec.title,
        "body": rec.body,
        "author_name": rec.author_name,
        "author_id": rec.author_id,
        "linked_entity_type": rec.linked_entity_type,
        "linked_entity_id": rec.linked_entity_id,
        "locale": rec.locale,
        "created_at": created_at.isoformat() if created_at else None,
        "resolve_at": resolve_at.isoformat() if resolve_at else None,
        "open": bool(resolve_at and resolve_at > now),
    }
