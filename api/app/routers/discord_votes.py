"""Discord reaction vote endpoint (spec-164 API Changes).

POST /api/ideas/{idea_id}/questions/{question_index}/vote

Allows the Discord bot to record reaction votes on idea open questions
and return aggregate vote counts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.discord_vote import QuestionVoteCreate, QuestionVoteResponse
from app.services import discord_vote_service, idea_service

router = APIRouter()


@router.post(
    "/ideas/{idea_id}/questions/{question_index}/vote",
    response_model=QuestionVoteResponse,
    status_code=200,
)
async def vote_on_question(
    idea_id: str,
    question_index: int,
    data: QuestionVoteCreate,
) -> QuestionVoteResponse:
    """Record a Discord reaction vote on an idea open question.

    Returns 409 if the user already voted with this polarity (idempotent — bot ignores this).
    Returns 404 if the idea or question index is not found.
    """
    # Validate that the idea and question index exist
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea '{idea_id}' not found")

    if question_index < 0 or question_index >= len(idea.open_questions):
        raise HTTPException(
            status_code=404,
            detail=f"Question index {question_index} not found on idea '{idea_id}' "
                   f"(has {len(idea.open_questions)} questions)",
        )

    result, created = discord_vote_service.vote(
        idea_id=idea_id,
        question_idx=question_index,
        discord_user_id=data.discord_user_id,
        polarity=data.polarity,
    )

    if not created:
        raise HTTPException(
            status_code=409,
            detail="Duplicate vote — user already voted with this polarity",
            headers={"X-Vote-Status": "duplicate"},
        )

    return result
