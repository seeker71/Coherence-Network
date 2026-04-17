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
    # When the collective lifted this proposal into a kinetic idea, we record
    # the idea it became and when. One-way link — the idea is the consequence.
    resolved_as_idea_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    _udb.engine()
    _ensure_resolution_columns()


_RESOLUTION_COLS_CHECKED = False


def _ensure_resolution_columns() -> None:
    """Heal live SQLite DBs that predate kinetic resolution columns."""
    global _RESOLUTION_COLS_CHECKED
    if _RESOLUTION_COLS_CHECKED:
        return
    try:
        eng = _udb.engine()
        with eng.connect() as conn:
            if conn.dialect.name != "sqlite":
                _RESOLUTION_COLS_CHECKED = True
                return
            rows = conn.exec_driver_sql("PRAGMA table_info(proposals)").fetchall()
            if not rows:
                _RESOLUTION_COLS_CHECKED = True
                return
            names = {r[1] for r in rows}
            if "resolved_as_idea_id" not in names:
                conn.exec_driver_sql(
                    "ALTER TABLE proposals ADD COLUMN resolved_as_idea_id VARCHAR"
                )
            if "resolved_at" not in names:
                conn.exec_driver_sql(
                    "ALTER TABLE proposals ADD COLUMN resolved_at DATETIME"
                )
            conn.commit()
    except Exception:
        pass
    finally:
        _RESOLUTION_COLS_CHECKED = True


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


def get_proposal_by_idea(idea_id: str) -> Optional[dict]:
    """Reverse lookup: the proposal (if any) that was lifted into this idea.

    Returns the proposal dict with an added ``tally`` summary so the
    consumer can render the origin fully without a second fetch.
    """
    _ensure_schema()
    with _session() as s:
        rec = s.execute(
            select(ProposalRecord).where(
                ProposalRecord.resolved_as_idea_id == idea_id
            )
        ).scalar_one_or_none()
    if not rec:
        return None
    payload = _to_dict(rec)
    payload["tally"] = tally(rec.id)
    return payload


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
    resolved_at = _aware(rec.resolved_at)
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
        "resolved_as_idea_id": rec.resolved_as_idea_id,
        "resolved_at": resolved_at.isoformat() if resolved_at else None,
    }


def resolve_into_idea(proposal_id: str) -> dict:
    """Lift a resonant proposal into a live idea.

    The collective's voices — support + amplify — are the gesture. This
    function reads that gesture from the tally, and when it reads
    ``resonant`` (and the proposal is still open and unresolved), it seeds
    an idea via the idea service and records the link.

    Returns the updated proposal dict (now with ``resolved_as_idea_id``)
    plus the idea payload. Idempotent: if already resolved, returns the
    existing link without reseeding.
    """
    _ensure_schema()
    with _session() as s:
        rec = s.get(ProposalRecord, proposal_id)
        if rec is None:
            raise ValueError("proposal not found")
        if rec.resolved_as_idea_id:
            return {
                "proposal": _to_dict(rec),
                "idea_id": rec.resolved_as_idea_id,
                "already_resolved": True,
            }

    t = tally(proposal_id)
    if t["status"] != "resonant":
        raise ValueError(f"proposal is not resonant (status={t['status']})")

    idea_payload = _seed_idea_from_proposal(proposal_id)
    idea_id = idea_payload.get("id") if isinstance(idea_payload, dict) else None
    if not idea_id:
        raise RuntimeError("idea seed did not return an id")

    now = datetime.now(timezone.utc)
    with _session() as s:
        rec = s.get(ProposalRecord, proposal_id)
        if rec is None:
            raise ValueError("proposal not found (vanished mid-resolve)")
        # Second-writer loses the race gracefully.
        if rec.resolved_as_idea_id:
            return {
                "proposal": _to_dict(rec),
                "idea_id": rec.resolved_as_idea_id,
                "already_resolved": True,
            }
        rec.resolved_as_idea_id = idea_id
        rec.resolved_at = now.replace(tzinfo=None)
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return {
            "proposal": _to_dict(rec),
            "idea_id": idea_id,
            "already_resolved": False,
        }


def _seed_idea_from_proposal(proposal_id: str) -> dict:
    """Seed a graph idea node from the proposal. Best-effort — if the idea
    service errors, we fall back to creating a lightweight graph node so
    the kinetic lift is always observable."""
    from app.services import idea_service, graph_service
    rec = get_proposal(proposal_id)
    if not rec:
        raise ValueError("proposal not found")
    slug = f"prop-{proposal_id[:10]}"
    name = rec["title"][:120]
    description = (
        (rec["body"] or "").strip()
        + f"\n\n(from proposal {proposal_id} — lifted by the collective)"
    ).strip()
    try:
        if hasattr(idea_service, "create_idea"):
            created = idea_service.create_idea(
                slug,
                name,
                description,
                1.0,  # potential_value (nominal — the vote is the real signal)
                1.0,  # estimated_cost (nominal)
                confidence=0.5,
                tags=["from-proposal"],
            )
            # create_idea may return a Pydantic model or dict
            if created is not None:
                created_dict = (
                    created.model_dump() if hasattr(created, "model_dump") else dict(created)
                )
                return {"id": created_dict.get("id") or slug, **created_dict}
    except Exception:
        pass
    # Fallback: create a plain idea node directly on the graph.
    try:
        graph_service.create_node(
            id=slug,
            type="idea",
            name=name,
            description=description,
            properties={
                "source": "proposal",
                "proposal_id": proposal_id,
                "author": rec["author_name"],
                "locale": rec["locale"],
            },
        )
    except Exception:
        # Return the slug anyway; the id is the lift even if storage failed.
        return {"id": slug, "fallback": True, "error": "graph_create_failed"}
    return {"id": slug, "fallback": True}
