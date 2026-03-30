"""Discord bot service — formatting and vote management (spec 164).

This module provides:
- Vote recording and tallying for idea questions
- Discord embed formatting for ideas and portfolio status
- Slash command response builders for /cc-idea, /cc-status, /cc-stake
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.models.discord_bot import IdeaEmbed, PortfolioSummary, VoteResult
from app.models.idea import IdeaWithScore, ManifestationStatus

logger = logging.getLogger(__name__)

# Thread-safe in-memory vote store.
# Structure: { "idea_id:question_idx": { "up": set(voter_ids), "down": set(voter_ids) } }
_vote_store: dict[str, dict[str, set[str]]] = {}
_vote_lock = threading.Lock()

# Colour codes for Discord embeds by manifestation status
STATUS_COLOURS = {
    "none": 0x95A5A6,       # Grey
    "partial": 0xF39C12,    # Orange
    "validated": 0x2ECC71,  # Green
}


def cast_vote(idea_id: str, question_index: int, voter_id: str, direction: str = "up") -> VoteResult | None:
    """Record a vote on an idea question.

    Returns VoteResult with current tallies, or None if idea/question not found.
    """
    from app.services import idea_service

    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None

    if question_index < 0 or question_index >= len(idea.open_questions):
        return None

    question = idea.open_questions[question_index]
    key = f"{idea_id}:{question_index}"

    with _vote_lock:
        if key not in _vote_store:
            _vote_store[key] = {"up": set(), "down": set()}

        bucket = _vote_store[key]

        # Remove voter from opposite direction (toggle behaviour)
        opposite = "down" if direction == "up" else "up"
        bucket[opposite].discard(voter_id)

        # Add vote
        bucket[direction].add(voter_id)

        votes_up = len(bucket["up"])
        votes_down = len(bucket["down"])

    return VoteResult(
        idea_id=idea_id,
        question_index=question_index,
        question=question.question,
        votes_up=votes_up,
        votes_down=votes_down,
        voter_id=voter_id,
    )


def get_vote_tally(idea_id: str, question_index: int) -> dict[str, int]:
    """Return current vote counts for a question."""
    key = f"{idea_id}:{question_index}"
    with _vote_lock:
        bucket = _vote_store.get(key, {"up": set(), "down": set()})
        return {"up": len(bucket["up"]), "down": len(bucket["down"])}


def format_idea_embed(idea: IdeaWithScore) -> IdeaEmbed:
    """Convert an IdeaWithScore into a Discord-ready embed model."""
    colour = STATUS_COLOURS.get(idea.manifestation_status.value, 0x5865F2)
    return IdeaEmbed(
        id=idea.id,
        name=idea.name,
        description=idea.description[:200] if len(idea.description) > 200 else idea.description,
        stage=idea.stage.value,
        manifestation_status=idea.manifestation_status.value,
        free_energy_score=idea.free_energy_score,
        roi_cc=idea.roi_cc,
        value_gap=idea.value_gap,
        open_questions_count=len(idea.open_questions),
        colour=colour,
    )


def build_discord_embed_dict(idea: IdeaWithScore) -> dict[str, Any]:
    """Build a Discord API embed payload dict for an idea."""
    embed = format_idea_embed(idea)
    fields = [
        {"name": "Stage", "value": embed.stage, "inline": True},
        {"name": "Status", "value": embed.manifestation_status, "inline": True},
        {"name": "ROI (CC)", "value": f"{embed.roi_cc:.2f}", "inline": True},
        {"name": "Free Energy", "value": f"{embed.free_energy_score:.2f}", "inline": True},
        {"name": "Value Gap", "value": f"{embed.value_gap:.2f}", "inline": True},
        {"name": "Open Questions", "value": str(embed.open_questions_count), "inline": True},
    ]
    return {
        "title": f"💡 {embed.name}",
        "description": embed.description,
        "color": embed.colour,
        "fields": fields,
        "footer": {"text": f"Idea ID: {embed.id}"},
    }


def build_portfolio_summary() -> PortfolioSummary:
    """Build summary data for /cc-status command."""
    from app.services import idea_service

    portfolio = idea_service.list_ideas(limit=500, read_only_guard=True)
    ideas = portfolio.ideas

    validated = sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED)
    total_gap = sum(i.value_gap for i in ideas)

    top_roi_idea = None
    top_roi_value = 0.0
    for idea in ideas:
        if idea.roi_cc > top_roi_value:
            top_roi_value = idea.roi_cc
            top_roi_idea = idea.name

    return PortfolioSummary(
        total_ideas=len(ideas),
        validated_ideas=validated,
        top_roi_idea=top_roi_idea,
        top_roi_value=top_roi_value,
        total_value_gap=total_gap,
    )


def build_status_embed() -> dict[str, Any]:
    """Build a Discord embed payload for portfolio status."""
    summary = build_portfolio_summary()
    fields = [
        {"name": "Total Ideas", "value": str(summary.total_ideas), "inline": True},
        {"name": "Validated", "value": str(summary.validated_ideas), "inline": True},
        {"name": "Total Value Gap", "value": f"{summary.total_value_gap:.2f} CC", "inline": True},
    ]
    if summary.top_roi_idea:
        fields.append({
            "name": "Top ROI Idea",
            "value": f"{summary.top_roi_idea} ({summary.top_roi_value:.2f}x)",
            "inline": False,
        })
    return {
        "title": "📊 Coherence Network Portfolio",
        "color": 0x5865F2,
        "fields": fields,
    }


def reset_votes() -> None:
    """Clear all votes — used in tests."""
    with _vote_lock:
        _vote_store.clear()
