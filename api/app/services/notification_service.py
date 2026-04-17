"""Soft notifications — someone spoke back.

When a contributor voices something or replies to a thread, the other
people in that thread deserve to know — softly, without a ping. This
service computes "since you last checked, someone spoke to you" as a
read over existing tables:

  · someone replied to a reaction whose author_id is yours
  · someone reacted (emoji or comment) to a voice you offered
  · someone mentioned you by author_name in a comment (simple @-match)

Nothing is stored. The only state per viewer is "last_checked_at"
which is the caller's cookie/localStorage timestamp sent on each read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select

from app.services import unified_db as _udb


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def unseen_for(
    contributor_id: Optional[str],
    author_name: Optional[str],
    since: Optional[datetime],
    *,
    limit: int = 50,
) -> list[dict]:
    """Return recent events that mention or respond to this viewer.

    Events, newest first. Each event has a shape ready to display:
      { kind, entity_type, entity_id, body, actor_name, created_at }
    """
    if not contributor_id and not author_name:
        return []
    from app.services.reaction_service import ReactionRecord
    from app.services.concept_voice_service import ConceptVoiceRecord

    # SQLite stores datetimes naive; normalize `since` so comparisons work.
    if since is not None and since.tzinfo is not None:
        since = since.astimezone(timezone.utc).replace(tzinfo=None)

    events: list[dict] = []

    with _udb.session() as s:
        # 1. Replies to reactions authored by this contributor
        if contributor_id:
            mine = s.execute(
                select(ReactionRecord.id).where(
                    ReactionRecord.author_id == contributor_id,
                )
            ).all()
            my_ids = {r[0] for r in mine}
            if my_ids:
                q = select(ReactionRecord).where(
                    ReactionRecord.parent_reaction_id.in_(my_ids),
                )
                if since:
                    q = q.where(ReactionRecord.created_at > since)
                rows = s.execute(q).scalars().all()
                for r in rows:
                    events.append(
                        {
                            "kind": "reply_to_me",
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "body": r.comment or r.emoji or "",
                            "actor_name": r.author_name,
                            "created_at": _iso(r.created_at),
                        }
                    )

        # 2. Reactions on voices I offered
        if contributor_id:
            my_voices = s.execute(
                select(ConceptVoiceRecord).where(
                    ConceptVoiceRecord.author_id == contributor_id,
                )
            ).scalars().all()
            voice_cids = {v.concept_id for v in my_voices}
            if voice_cids:
                q = select(ReactionRecord).where(
                    ReactionRecord.entity_type == "concept",
                    ReactionRecord.entity_id.in_(voice_cids),
                )
                if since:
                    q = q.where(ReactionRecord.created_at > since)
                # Skip self-reactions (anonymous rows have NULL author_id, keep them)
                q = q.where(
                    or_(
                        ReactionRecord.author_id.is_(None),
                        ReactionRecord.author_id != contributor_id,
                    )
                )
                rows = s.execute(q).scalars().all()
                for r in rows:
                    events.append(
                        {
                            "kind": "reaction_to_my_voice",
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "body": r.comment or r.emoji or "",
                            "actor_name": r.author_name,
                            "created_at": _iso(r.created_at),
                        }
                    )

        # 3. @mentions by author_name in any comment
        if author_name:
            mention_token = f"@{author_name}".lower()
            q = select(ReactionRecord).where(
                ReactionRecord.comment.isnot(None),
            )
            if since:
                q = q.where(ReactionRecord.created_at > since)
            if contributor_id:
                q = q.where(
                    or_(
                        ReactionRecord.author_id.is_(None),
                        ReactionRecord.author_id != contributor_id,
                    )
                )
            rows = s.execute(q).scalars().all()
            for r in rows:
                if (r.comment or "").lower().find(mention_token) >= 0:
                    events.append(
                        {
                            "kind": "mention",
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "body": r.comment or "",
                            "actor_name": r.author_name,
                            "created_at": _iso(r.created_at),
                        }
                    )

    # Deduplicate by (kind, entity, actor, created_at)
    seen = set()
    unique: list[dict] = []
    for e in events:
        key = (e["kind"], e["entity_type"], e["entity_id"], e["actor_name"], e["created_at"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    unique.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return unique[:limit]
