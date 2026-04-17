"""Reactions — a lightweight surface for expressing care on anything.

Any contributor can attach an emoji, a short comment, or both to any
concept, idea, spec, contributor, community, workspace, asset, or
contribution. No moderation queue, no sign-in wall, trust-by-default.

The point is not to build an engagement metric. The point is to give
readers a way to say "I'm here, this reached me" — and give writers a
pulse of felt-ness on their work. Emoji alone is a smile. Comment alone
is a thought. Both together is a small gift.

Storage is a single table keyed by (entity_type, entity_id). Aggregates
(emoji → count) are computed on read; the raw feed is available for the
human detail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, desc, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


# Entity types that accept reactions. Stay permissive — the point is
# expression, not a closed taxonomy. Extend when a new surface wants one.
SUPPORTED_ENTITY_TYPES = {
    "concept",
    "idea",
    "spec",
    "contributor",
    "community",
    "workspace",
    "asset",
    "contribution",
    "story",
    # Every piece of content in the system is meetable — config keys,
    # insights from agent orchestration, running tasks, completed runs.
    "config",
    "insight",
    "agent_task",
    "agent_run",
    # Proposals — the collective votes on them through the same meeting gesture
    "proposal",
}


class ReactionRecord(Base):
    """One reaction tied to one entity. Either emoji or comment (or both)."""

    __tablename__ = "reactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    emoji: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String, nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    _udb.engine()


def add_reaction(
    *,
    entity_type: str,
    entity_id: str,
    author_name: str,
    emoji: Optional[str] = None,
    comment: Optional[str] = None,
    author_id: Optional[str] = None,
    locale: str = "en",
) -> dict:
    _ensure_schema()
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    if not entity_id:
        raise ValueError("entity_id required")
    if not author_name or not author_name.strip():
        raise ValueError("author_name required")
    emoji_v = (emoji or "").strip() or None
    comment_v = (comment or "").strip() or None
    if not emoji_v and not comment_v:
        raise ValueError("reaction needs either emoji or comment")
    # Keep emoji short — stored as a varchar, but also guards against a whole
    # paragraph being slipped into the emoji field.
    if emoji_v and len(emoji_v) > 16:
        raise ValueError("emoji should be short (under 16 characters)")
    rec = ReactionRecord(
        id=uuid4().hex,
        entity_type=entity_type,
        entity_id=entity_id,
        author_name=author_name.strip(),
        author_id=author_id,
        emoji=emoji_v,
        comment=comment_v,
        locale=locale or "en",
    )
    with _session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
    return _to_dict(rec)


def list_reactions(
    entity_type: str, entity_id: str, limit: int = 100
) -> list[dict]:
    _ensure_schema()
    with _session() as s:
        rows = (
            s.execute(
                select(ReactionRecord)
                .where(
                    ReactionRecord.entity_type == entity_type,
                    ReactionRecord.entity_id == entity_id,
                )
                .order_by(desc(ReactionRecord.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [_to_dict(r) for r in rows]


def summarise(entity_type: str, entity_id: str) -> dict:
    """Emoji aggregate + comment count for quick display."""
    _ensure_schema()
    with _session() as s:
        emoji_rows = (
            s.execute(
                select(ReactionRecord.emoji, func.count(ReactionRecord.id))
                .where(
                    ReactionRecord.entity_type == entity_type,
                    ReactionRecord.entity_id == entity_id,
                    ReactionRecord.emoji.isnot(None),
                )
                .group_by(ReactionRecord.emoji)
            ).all()
        )
        comment_count = s.execute(
            select(func.count(ReactionRecord.id)).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.entity_id == entity_id,
                ReactionRecord.comment.isnot(None),
            )
        ).scalar_one()
    emojis = sorted(
        ({"emoji": e, "count": int(n)} for e, n in emoji_rows if e),
        key=lambda r: (-r["count"], r["emoji"]),
    )
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "emojis": emojis,
        "comment_count": int(comment_count),
        "total": sum(r["count"] for r in emojis) + int(comment_count),
    }


def recent_reactions(limit: int = 20) -> list[dict]:
    _ensure_schema()
    with _session() as s:
        rows = (
            s.execute(
                select(ReactionRecord)
                .order_by(desc(ReactionRecord.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [_to_dict(r) for r in rows]


def _to_dict(rec: ReactionRecord) -> dict:
    return {
        "id": rec.id,
        "entity_type": rec.entity_type,
        "entity_id": rec.entity_id,
        "author_name": rec.author_name,
        "author_id": rec.author_id,
        "emoji": rec.emoji,
        "comment": rec.comment,
        "locale": rec.locale,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }
