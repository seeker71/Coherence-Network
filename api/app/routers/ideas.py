"""Idea portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.idea import (
    IdeaCreate,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestionAnswerUpdate,
    IdeaStorageInfo,
    IdeaUpdate,
    IdeaWithScore,
)
from app.services import idea_service

router = APIRouter()


@router.get("/ideas", response_model=IdeaPortfolioResponse)
async def list_ideas(
    only_unvalidated: bool = Query(False, description="When true, only return ideas not yet validated."),
    include_internal: bool = Query(True, description="When false, hide system-generated/internal ideas."),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> IdeaPortfolioResponse:
    return idea_service.list_ideas(
        only_unvalidated=only_unvalidated,
        include_internal=include_internal,
        limit=limit,
        offset=offset,
    )


@router.get("/ideas/storage", response_model=IdeaStorageInfo)
async def get_idea_storage_info() -> IdeaStorageInfo:
    return idea_service.storage_info()


@router.get("/ideas/{idea_id}", response_model=IdeaWithScore)
async def get_idea(idea_id: str) -> IdeaWithScore:
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.post("/ideas", response_model=IdeaWithScore, status_code=201)
async def create_idea(data: IdeaCreate) -> IdeaWithScore:
    created = idea_service.create_idea(
        idea_id=data.id,
        name=data.name,
        description=data.description,
        potential_value=data.potential_value,
        estimated_cost=data.estimated_cost,
        confidence=data.confidence,
        interfaces=data.interfaces,
        open_questions=data.open_questions,
    )
    if created is None:
        raise HTTPException(status_code=409, detail="Idea already exists")
    return created


@router.patch("/ideas/{idea_id}", response_model=IdeaWithScore)
async def update_idea(idea_id: str, data: IdeaUpdate) -> IdeaWithScore:
    if all(
        field is None
        for field in (
            data.actual_value,
            data.actual_cost,
            data.potential_value,
            data.estimated_cost,
            data.confidence,
            data.manifestation_status,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")

    updated = idea_service.update_idea(
        idea_id=idea_id,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        potential_value=data.potential_value,
        estimated_cost=data.estimated_cost,
        confidence=data.confidence,
        manifestation_status=data.manifestation_status,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return updated


@router.post("/ideas/{idea_id}/questions", response_model=IdeaWithScore)
async def add_idea_question(idea_id: str, data: IdeaQuestionCreate) -> IdeaWithScore:
    updated, added = idea_service.add_question(
        idea_id=idea_id,
        question=data.question,
        value_to_whole=data.value_to_whole,
        estimated_cost=data.estimated_cost,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    if not added:
        raise HTTPException(status_code=409, detail="Question already exists for idea")
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
