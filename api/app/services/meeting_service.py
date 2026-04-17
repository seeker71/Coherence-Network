"""Meeting — the combined-organism sense of viewer + content.

When a viewer lands on an entity, that is not a consumption. It is a
meeting. Two organisms (the reader and the thing being read) come into
contact, and the meeting can grow or shrink the vitality of each.

This service computes the cheap version of that meeting:

- content_vitality: how witnessed this entity has been recently (view
  count, reaction count, voice count, freshness of last touch).
- viewer_vitality: a small estimate of the viewer's current presence
  (reactions they've given, voices they've shared, whether they are a
  contributor at all).
- shared_pulse: a qualitative label describing the meeting — first
  meeting, familiar, resonant, quiet.

The numbers are intentionally small integers (0-100) so the UI can
render them as a pulse ring without math. The point is not metrics; the
point is a visible ledger of felt-ness for both sides of the encounter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select

from app.services import unified_db as _udb


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, n))


def _recent_cutoff(hours: int = 72):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def sense_meeting(
    entity_type: str,
    entity_id: str,
    contributor_id: Optional[str] = None,
) -> dict:
    """Return the felt-state of a viewer meeting an entity right now.

    Shape:
      {
        content: {vitality: int, reactions: int, voices: int, first_meeting: bool},
        viewer:  {vitality: int, reactions_given: int, voices_given: int, is_contributor: bool},
        shared:  {pulse: "resonant" | "familiar" | "first_meeting" | "quiet", hint: str}
      }
    """
    from app.services.reaction_service import ReactionRecord
    from app.services.concept_voice_service import ConceptVoiceRecord

    with _udb.session() as s:
        # --- content side -------------------------------------------------
        total_reactions = s.execute(
            select(func.count(ReactionRecord.id)).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.entity_id == entity_id,
            )
        ).scalar_one()
        recent_reactions = s.execute(
            select(func.count(ReactionRecord.id)).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.entity_id == entity_id,
                ReactionRecord.created_at >= _recent_cutoff(),
            )
        ).scalar_one()
        total_voices = 0
        if entity_type == "concept":
            total_voices = s.execute(
                select(func.count(ConceptVoiceRecord.id)).where(
                    ConceptVoiceRecord.concept_id == entity_id,
                )
            ).scalar_one() or 0

        # --- viewer side --------------------------------------------------
        viewer_reactions = 0
        viewer_voices = 0
        is_contributor = bool(contributor_id)
        if contributor_id:
            viewer_reactions = s.execute(
                select(func.count(ReactionRecord.id)).where(
                    ReactionRecord.author_id == contributor_id,
                )
            ).scalar_one() or 0
            viewer_voices = s.execute(
                select(func.count(ConceptVoiceRecord.id)).where(
                    ConceptVoiceRecord.author_id == contributor_id,
                )
            ).scalar_one() or 0

    # Content vitality: blend of total care and recent freshness
    content_vitality = _clamp(
        20
        + min(50, int(total_reactions) * 5)
        + min(20, int(recent_reactions) * 6)
        + min(20, int(total_voices) * 7)
    )
    first_meeting_for_content = int(total_reactions) + int(total_voices) == 0

    # Viewer vitality: presence grows with their own expressions
    viewer_vitality = _clamp(
        (30 if is_contributor else 15)
        + min(40, int(viewer_reactions) * 3)
        + min(30, int(viewer_voices) * 6)
    )

    # Shared pulse: qualitative label for the UI
    if first_meeting_for_content and not is_contributor:
        pulse = "first_meeting"
        hint = "first_meeting"
    elif int(total_reactions) > 20 and viewer_reactions > 2:
        pulse = "resonant"
        hint = "resonant"
    elif viewer_reactions > 0 or viewer_voices > 0:
        pulse = "familiar"
        hint = "familiar"
    elif int(total_reactions) > 0:
        pulse = "quiet"
        hint = "quiet"
    else:
        pulse = "first_meeting"
        hint = "first_meeting"

    return {
        "content": {
            "vitality": content_vitality,
            "reactions": int(total_reactions),
            "voices": int(total_voices),
            "first_meeting": first_meeting_for_content,
        },
        "viewer": {
            "vitality": viewer_vitality,
            "reactions_given": int(viewer_reactions),
            "voices_given": int(viewer_voices),
            "is_contributor": is_contributor,
        },
        "shared": {
            "pulse": pulse,
            "hint": hint,
        },
    }
