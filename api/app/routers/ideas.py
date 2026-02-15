"""Idea portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.idea import (
    IdeaPortfolioResponse,
    IdeaQuestionAnswerUpdate,
    IdeaUpdate,
    IdeaWithScore,
)
from app.services import idea_service

router = APIRouter()


@router.get("/ideas", response_model=IdeaPortfolioResponse)
async def list_ideas(
    only_unvalidated: bool = Query(False, description="When true, only return ideas not yet validated."),
) -> IdeaPortfolioResponse:
    return idea_service.list_ideas(only_unvalidated=only_unvalidated)


@router.get("/ideas/{idea_id}", response_model=IdeaWithScore)
async def get_idea(idea_id: str) -> IdeaWithScore:
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.patch("/ideas/{idea_id}", response_model=IdeaWithScore)
async def update_idea(idea_id: str, data: IdeaUpdate) -> IdeaWithScore:
    if all(
        field is None
        for field in (
            data.actual_value,
            data.actual_cost,
            data.confidence,
            data.manifestation_status,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")

    updated = idea_service.update_idea(
        idea_id=idea_id,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        confidence=data.confidence,
        manifestation_status=data.manifestation_status,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return updated


@router.post("/ideas/{idea_id}/questions/answer", response_model=IdeaWithScore)
async def answer_idea_question(idea_id: str, data: IdeaQuestionAnswerUpdate) -> IdeaWithScore:
    updated, question_found = idea_service.answer_question(
        idea_id=idea_id,
        question=data.question,
        answer=data.answer,
        measured_delta=data.measured_delta,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    if not question_found:
        raise HTTPException(status_code=404, detail="Question not found for idea")
    return updated
