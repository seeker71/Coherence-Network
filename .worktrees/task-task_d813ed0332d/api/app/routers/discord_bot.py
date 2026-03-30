"""Discord bot API routes (spec 164).

Provides the vote endpoint for idea questions and embed preview endpoints
used by the Discord bot and web UI.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.discord_bot import VoteCreate, VoteResult
from app.services import discord_bot_service

router = APIRouter()


@router.post("/ideas/{idea_id}/questions/{question_index}/vote", response_model=VoteResult)
async def vote_on_question(
    idea_id: str,
    question_index: int,
    body: VoteCreate,
) -> VoteResult:
    """Cast a vote on an idea question by index.

    Voters can change direction; voting the same direction again is idempotent.
    """
    result = discord_bot_service.cast_vote(
        idea_id=idea_id,
        question_index=question_index,
        voter_id=body.voter_id,
        direction=body.direction,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Idea or question not found")
    return result


@router.get("/ideas/{idea_id}/embed")
async def get_idea_embed(idea_id: str) -> dict:
    """Return a Discord embed payload for an idea (preview / webhook use)."""
    from app.services import idea_service

    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return discord_bot_service.build_discord_embed_dict(idea)


@router.get("/portfolio/status-embed")
async def get_portfolio_status_embed() -> dict:
    """Return a Discord embed payload for portfolio status."""
    return discord_bot_service.build_status_embed()
