"""Personal feed — the contributor's own corner of the organism.

The collective /feed shows what is alive everywhere. This service shows
what is alive for *you*: the voices you gave, the reactions and replies
you wrote, the voices and replies others left on content you touched,
and the proposals you authored or helped lift.

Like the notification service, this is a pure read — no new storage.
Items are unioned across existing tables, deduplicated, and returned
newest first. Each item carries a `reason` describing why it appears
("you voiced this" / "someone replied to you" / ...) so the UI can
render a warm caption next to each entry.
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


_REASON_KEYS = {
    "i_voiced",
    "i_reacted",
    "i_proposed",
    "i_supported",
    "replied_to_me",
    "reaction_on_my_voice",
    "lifted_from_my_proposal",
    "lifted_from_proposal_i_supported",
}


def _reason_body_map(locale: str) -> dict[str, str]:
    """Short localized captions per reason kind."""
    bundle = {
        "en": {
            "i_voiced": "You voiced this",
            "i_reacted": "You reacted here",
            "i_proposed": "You proposed this",
            "i_supported": "You supported this proposal",
            "replied_to_me": "Someone replied to you",
            "reaction_on_my_voice": "Someone reacted to your voice",
            "lifted_from_my_proposal": "Your proposal became this idea",
            "lifted_from_proposal_i_supported": "A proposal you supported became this idea",
        },
        "de": {
            "i_voiced": "Du hast hier gesprochen",
            "i_reacted": "Du hast hier reagiert",
            "i_proposed": "Du hast das vorgeschlagen",
            "i_supported": "Du hast diesen Vorschlag unterstützt",
            "replied_to_me": "Jemand hat dir geantwortet",
            "reaction_on_my_voice": "Jemand hat auf deine Stimme reagiert",
            "lifted_from_my_proposal": "Dein Vorschlag wurde zu dieser Idee",
            "lifted_from_proposal_i_supported": "Ein unterstützter Vorschlag wurde zu dieser Idee",
        },
        "es": {
            "i_voiced": "Tu voz está aquí",
            "i_reacted": "Reaccionaste aquí",
            "i_proposed": "Tú propusiste esto",
            "i_supported": "Apoyaste esta propuesta",
            "replied_to_me": "Alguien te respondió",
            "reaction_on_my_voice": "Alguien reaccionó a tu voz",
            "lifted_from_my_proposal": "Tu propuesta se volvió esta idea",
            "lifted_from_proposal_i_supported": "Una propuesta que apoyaste se volvió esta idea",
        },
        "id": {
            "i_voiced": "Kamu bersuara di sini",
            "i_reacted": "Kamu bereaksi di sini",
            "i_proposed": "Kamu mengusulkan ini",
            "i_supported": "Kamu mendukung usulan ini",
            "replied_to_me": "Seseorang membalasmu",
            "reaction_on_my_voice": "Seseorang bereaksi pada suaramu",
            "lifted_from_my_proposal": "Usulanmu menjadi ide ini",
            "lifted_from_proposal_i_supported": "Usulan yang kamu dukung menjadi ide ini",
        },
    }
    return bundle.get(locale) or bundle["en"]


def build_personal_feed(
    *,
    contributor_id: Optional[str] = None,
    author_name: Optional[str] = None,
    limit: int = 40,
    locale: str = "en",
) -> list[dict]:
    """Assemble the contributor's stream.

    Each item:
      {
        entity_type, entity_id, kind,
        title, snippet,
        actor_name | None,
        reason, reason_label,
        created_at,
      }
    """
    if not contributor_id and not author_name:
        return []

    from app.services.reaction_service import ReactionRecord
    from app.services.concept_voice_service import ConceptVoiceRecord
    from app.services.proposal_service import ProposalRecord

    captions = _reason_body_map(locale)

    items: list[dict] = []

    with _udb.session() as s:
        if contributor_id:
            # 1. Voices I wrote
            rows = s.execute(
                select(ConceptVoiceRecord)
                .where(ConceptVoiceRecord.author_id == contributor_id)
                .order_by(ConceptVoiceRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for v in rows:
                items.append(
                    {
                        "entity_type": "concept",
                        "entity_id": v.concept_id,
                        "kind": "voice",
                        "title": v.concept_id,
                        "snippet": (v.body or "")[:200],
                        "actor_name": v.author_name,
                        "reason": "i_voiced",
                        "reason_label": captions["i_voiced"],
                        "created_at": _iso(v.created_at),
                    }
                )

            # 2. Reactions with comment I wrote
            rows = s.execute(
                select(ReactionRecord)
                .where(
                    ReactionRecord.author_id == contributor_id,
                    ReactionRecord.comment.isnot(None),
                )
                .order_by(ReactionRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for r in rows:
                items.append(
                    {
                        "entity_type": r.entity_type,
                        "entity_id": r.entity_id,
                        "kind": "reaction",
                        "title": r.entity_id,
                        "snippet": (r.comment or r.emoji or "")[:200],
                        "actor_name": r.author_name,
                        "reason": "i_reacted",
                        "reason_label": captions["i_reacted"],
                        "created_at": _iso(r.created_at),
                    }
                )

            # 3. Proposals I authored
            rows = s.execute(
                select(ProposalRecord)
                .where(ProposalRecord.author_id == contributor_id)
                .order_by(ProposalRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for p in rows:
                is_lifted = bool(p.resolved_as_idea_id)
                items.append(
                    {
                        "entity_type": "idea" if is_lifted else "proposal",
                        "entity_id": p.resolved_as_idea_id if is_lifted else p.id,
                        "kind": "proposal",
                        "title": p.title,
                        "snippet": (p.body or "")[:200],
                        "actor_name": p.author_name,
                        "reason": "lifted_from_my_proposal" if is_lifted else "i_proposed",
                        "reason_label": captions[
                            "lifted_from_my_proposal" if is_lifted else "i_proposed"
                        ],
                        "created_at": _iso(p.resolved_at if is_lifted else p.created_at),
                    }
                )

            # 4. Proposals I supported (💛/🔥) but didn't author
            support_rows = s.execute(
                select(ReactionRecord.entity_id).where(
                    ReactionRecord.entity_type == "proposal",
                    ReactionRecord.author_id == contributor_id,
                    ReactionRecord.emoji.in_(["💛", "🔥"]),
                )
            ).all()
            supported_ids = {r[0] for r in support_rows}
            if supported_ids:
                rows = s.execute(
                    select(ProposalRecord).where(
                        ProposalRecord.id.in_(supported_ids),
                        or_(
                            ProposalRecord.author_id.is_(None),
                            ProposalRecord.author_id != contributor_id,
                        ),
                    )
                ).scalars().all()
                for p in rows:
                    is_lifted = bool(p.resolved_as_idea_id)
                    items.append(
                        {
                            "entity_type": "idea" if is_lifted else "proposal",
                            "entity_id": p.resolved_as_idea_id if is_lifted else p.id,
                            "kind": "proposal_i_supported",
                            "title": p.title,
                            "snippet": (p.body or "")[:200],
                            "actor_name": p.author_name,
                            "reason": (
                                "lifted_from_proposal_i_supported" if is_lifted else "i_supported"
                            ),
                            "reason_label": captions[
                                "lifted_from_proposal_i_supported" if is_lifted else "i_supported"
                            ],
                            "created_at": _iso(p.resolved_at if is_lifted else p.created_at),
                        }
                    )

            # 5. Replies directly to my reactions
            my_reaction_ids = s.execute(
                select(ReactionRecord.id).where(ReactionRecord.author_id == contributor_id)
            ).all()
            parent_set = {r[0] for r in my_reaction_ids}
            if parent_set:
                rows = s.execute(
                    select(ReactionRecord)
                    .where(ReactionRecord.parent_reaction_id.in_(parent_set))
                    .order_by(ReactionRecord.created_at.desc())
                    .limit(limit)
                ).scalars().all()
                for r in rows:
                    items.append(
                        {
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "kind": "reply_to_me",
                            "title": r.entity_id,
                            "snippet": (r.comment or r.emoji or "")[:200],
                            "actor_name": r.author_name,
                            "reason": "replied_to_me",
                            "reason_label": captions["replied_to_me"],
                            "created_at": _iso(r.created_at),
                        }
                    )

            # 6. Reactions on concepts I voiced
            my_voices = s.execute(
                select(ConceptVoiceRecord.concept_id).where(
                    ConceptVoiceRecord.author_id == contributor_id
                )
            ).all()
            voiced_cids = {r[0] for r in my_voices}
            if voiced_cids:
                rows = s.execute(
                    select(ReactionRecord)
                    .where(
                        ReactionRecord.entity_type == "concept",
                        ReactionRecord.entity_id.in_(voiced_cids),
                        or_(
                            ReactionRecord.author_id.is_(None),
                            ReactionRecord.author_id != contributor_id,
                        ),
                    )
                    .order_by(ReactionRecord.created_at.desc())
                    .limit(limit)
                ).scalars().all()
                for r in rows:
                    items.append(
                        {
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "kind": "reaction_on_my_voice",
                            "title": r.entity_id,
                            "snippet": (r.comment or r.emoji or "")[:200],
                            "actor_name": r.author_name,
                            "reason": "reaction_on_my_voice",
                            "reason_label": captions["reaction_on_my_voice"],
                            "created_at": _iso(r.created_at),
                        }
                    )

        # Soft-identity branch: when no contributor_id is available but
        # the viewer has a stored author_name (e.g. Mama, invited and
        # pre-registered without a private key), surface voices and
        # reactions she wrote under that name. Her corner no longer
        # lies about being empty when she has spoken.
        if author_name and not contributor_id:
            an = author_name.strip()
            if an:
                v_rows = s.execute(
                    select(ConceptVoiceRecord)
                    .where(ConceptVoiceRecord.author_name == an)
                    .order_by(ConceptVoiceRecord.created_at.desc())
                    .limit(limit)
                ).scalars().all()
                for v in v_rows:
                    items.append(
                        {
                            "entity_type": "concept",
                            "entity_id": v.concept_id,
                            "kind": "voice",
                            "title": v.concept_id,
                            "snippet": (v.body or "")[:200],
                            "actor_name": v.author_name,
                            "reason": "i_voiced",
                            "reason_label": captions["i_voiced"],
                            "created_at": _iso(v.created_at),
                        }
                    )
                r_rows = s.execute(
                    select(ReactionRecord)
                    .where(
                        ReactionRecord.author_name == an,
                        ReactionRecord.comment.isnot(None),
                    )
                    .order_by(ReactionRecord.created_at.desc())
                    .limit(limit)
                ).scalars().all()
                for r in r_rows:
                    items.append(
                        {
                            "entity_type": r.entity_type,
                            "entity_id": r.entity_id,
                            "kind": "reaction",
                            "title": r.entity_id,
                            "snippet": (r.comment or r.emoji or "")[:200],
                            "actor_name": r.author_name,
                            "reason": "i_reacted",
                            "reason_label": captions["i_reacted"],
                            "created_at": _iso(r.created_at),
                        }
                    )

    # Dedup by (entity_type, entity_id, reason, actor_name, created_at)
    seen = set()
    unique: list[dict] = []
    for it in items:
        key = (
            it["entity_type"],
            it["entity_id"],
            it["reason"],
            it.get("actor_name"),
            it.get("created_at"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    unique.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    return unique[:limit]
