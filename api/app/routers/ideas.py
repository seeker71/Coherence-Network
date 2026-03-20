"""Idea portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middleware.auth import require_api_key

from app.models.idea import (
    IdeaCreate,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestionAnswerUpdate,
    IdeaSelectionResult,
    IdeaStorageInfo,
    IdeaUpdate,
    IdeaWithScore,
)
from app.services import idea_service, idea_selection_ab_service, inventory_service

router = APIRouter()


@router.get("/ideas", response_model=IdeaPortfolioResponse)
async def list_ideas(
    only_unvalidated: bool = Query(False, description="When true, only return ideas not yet validated."),
    include_internal: bool = Query(True, description="When false, hide system-generated/internal ideas."),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    read_only_guard: bool = Query(False, description="When true, do not persist ensure logic (for invariant/guard runs)."),
    sort: str = Query("free_energy", description="Sort method: 'free_energy' (default, Method A) or 'marginal_cc' (Method B)."),
) -> IdeaPortfolioResponse:
    return idea_service.list_ideas(
        only_unvalidated=only_unvalidated,
        include_internal=include_internal,
        limit=limit,
        offset=offset,
        read_only_guard=read_only_guard,
        sort_method=sort,
    )


@router.get("/ideas/storage", response_model=IdeaStorageInfo)
async def get_idea_storage_info() -> IdeaStorageInfo:
    return idea_service.storage_info()


@router.get("/ideas/cards")
async def list_idea_cards(
    q: str = Query("", description="Free-text search across idea title/description/spec IDs."),
    state: str = Query(
        "all",
        description="One of: all, none, spec, implemented, validated, measured.",
    ),
    attention: str = Query(
        "all",
        description="One of: all, none, low, medium, high.",
    ),
    sort: str = Query(
        "attention_desc",
        description="One of: attention_desc, roi_desc, gap_desc, state_desc, name_asc.",
    ),
    cursor: str | None = Query(default=None, description="Offset cursor returned by previous page."),
    limit: int = Query(50, ge=1, le=200),
    include_internal_ideas: bool = Query(True),
    only_actionable: bool = Query(False),
    min_roi: float | None = Query(default=None),
    min_value_gap: float | None = Query(default=None),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_idea_cards_feed(
        q=q,
        state=state,
        attention=attention,
        sort=sort,
        cursor=cursor,
        limit=limit,
        include_internal_ideas=include_internal_ideas,
        only_actionable=only_actionable,
        min_roi=min_roi,
        min_value_gap=min_value_gap,
        runtime_window_seconds=runtime_window_seconds,
    )


@router.get("/ideas/cards/changes")
async def list_idea_card_changes(
    since_token: str | None = Query(default=None),
    include_internal_ideas: bool = Query(True),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_idea_cards_changes(
        since_token=since_token,
        include_internal_ideas=include_internal_ideas,
        runtime_window_seconds=runtime_window_seconds,
    )


@router.get("/ideas/selection-ab/stats")
async def get_selection_ab_stats() -> dict:
    return idea_selection_ab_service.get_comparison()


@router.post("/ideas/select", response_model=IdeaSelectionResult)
async def select_idea(
    method: str = Query("marginal_cc", description="Score method: free_energy | marginal_cc"),
    temperature: float = Query(1.0, ge=0.0, le=5.0, description="0=deterministic, 1=proportional, 2+=explore"),
    exclude: str = Query("", description="Comma-separated idea IDs to exclude"),
    seed: int | None = Query(None, description="RNG seed for reproducibility"),
    _key: str = Depends(require_api_key),
) -> IdeaSelectionResult:
    """Weighted stochastic idea selection.

    Picks one idea from the portfolio. Probability distribution is softmax
    over scores with the given temperature. Higher temperature = more exploration.
    On average the distribution matches the ranking, but any single call may
    pick a lower-ranked idea — this is by design for A/B exploration.
    """
    exclude_ids = [e.strip() for e in exclude.split(",") if e.strip()] if exclude else None
    try:
        return idea_service.select_idea(
            method=method,
            temperature=temperature,
            exclude_ids=exclude_ids,
            seed=seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/ideas/{idea_id}", response_model=IdeaWithScore)
async def get_idea(idea_id: str) -> IdeaWithScore:
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.post("/ideas", response_model=IdeaWithScore, status_code=201)
async def create_idea(data: IdeaCreate, _key: str = Depends(require_api_key)) -> IdeaWithScore:
    created = idea_service.create_idea(
        idea_id=data.id,
        name=data.name,
        description=data.description,
        potential_value=data.potential_value,
        estimated_cost=data.estimated_cost,
        confidence=data.confidence,
        interfaces=data.interfaces,
        open_questions=data.open_questions,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        resistance_risk=data.resistance_risk,
        idea_type=data.idea_type,
        parent_idea_id=data.parent_idea_id,
        child_idea_ids=data.child_idea_ids,
        manifestation_status=data.manifestation_status,
        value_basis=data.value_basis,
    )
    if created is None:
        raise HTTPException(status_code=409, detail="Idea already exists")
    return created


@router.patch("/ideas/{idea_id}", response_model=IdeaWithScore)
async def update_idea(idea_id: str, data: IdeaUpdate, _key: str = Depends(require_api_key)) -> IdeaWithScore:
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


@router.post("/ideas/{idea_id}/questions", response_model=IdeaWithScore)
async def add_idea_question(idea_id: str, data: IdeaQuestionCreate, _key: str = Depends(require_api_key)) -> IdeaWithScore:
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
async def answer_idea_question(idea_id: str, data: IdeaQuestionAnswerUpdate, _key: str = Depends(require_api_key)) -> IdeaWithScore:
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
