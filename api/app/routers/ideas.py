"""Idea portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import require_api_key

from app.models.idea import (
    GovernanceHealth,
    IdeaCountResponse,
    IdeaCreate,
    IdeaShowcaseResponse,
    IdeaStage,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestionAnswerUpdate,
    IdeaSelectionResult,
    IdeaStorageInfo,
    IdeaTasksResponse,
    IdeaUpdate,
    IdeaWithScore,
    ProgressDashboard,
    StageSetRequest,
)
from app.services import agent_service, idea_service, idea_selection_ab_service, inventory_service, stake_compute_service

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


@router.get("/ideas/health", response_model=GovernanceHealth)
async def get_governance_health(
    window_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> GovernanceHealth:
    """Portfolio governance effectiveness snapshot (spec 126)."""
    return idea_service.compute_governance_health(window_days=window_days)


@router.get("/ideas/showcase", response_model=IdeaShowcaseResponse)
async def list_ideas_showcase() -> IdeaShowcaseResponse:
    """Funder-facing idea summaries with ask, budget, proof, and status."""
    return idea_service.list_showcase_ideas()


@router.get("/ideas/resonance")
async def get_resonance(
    window_hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Return ideas with recent activity, sorted by most-recent-activity-first."""
    return idea_service.get_resonance_feed(window_hours=window_hours, limit=limit)


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


@router.get("/ideas/count", response_model=IdeaCountResponse)
async def count_ideas() -> IdeaCountResponse:
    return idea_service.count_ideas()


@router.get("/ideas/progress", response_model=ProgressDashboard)
async def get_progress_dashboard() -> ProgressDashboard:
    """Per-stage idea counts and completion percentage (spec 138)."""
    return idea_service.compute_progress_dashboard()


@router.post("/ideas/{idea_id}/advance", response_model=IdeaWithScore)
async def advance_idea_stage(idea_id: str, _key: str = Depends(require_api_key)) -> IdeaWithScore:
    """Advance an idea to the next sequential stage (spec 138)."""
    result, error = idea_service.advance_idea_stage(idea_id)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    if error == "already_complete":
        raise HTTPException(status_code=409, detail="Idea is already complete")
    return result


@router.post("/ideas/{idea_id}/stage", response_model=IdeaWithScore)
async def set_idea_stage(idea_id: str, body: StageSetRequest, _key: str = Depends(require_api_key)) -> IdeaWithScore:
    """Set an explicit stage for an idea (admin override, spec 138)."""
    try:
        IdeaStage(body.stage)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid stage value")
    result, error = idea_service.set_idea_stage(idea_id, body.stage)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.post("/ideas/{idea_id}/fork", status_code=201)
async def fork_idea_endpoint(
    idea_id: str,
    forker_id: str | None = Query(default=None, min_length=1),
    provider: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
    adaptation_notes: str | None = Query(default=None),
) -> dict:
    """Fork an existing idea. Identify by forker_id or provider+provider_id."""
    resolved_id = _resolve_contributor(forker_id, provider, provider_id)
    try:
        return idea_service.fork_idea(
            source_idea_id=idea_id,
            forker_id=resolved_id,
            adaptation_notes=adaptation_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class StakeRequest(BaseModel):
    contributor_id: str | None = None
    provider: str | None = None
    provider_id: str | None = None
    amount_cc: float
    rationale: str | None = None


def _resolve_contributor(contributor_id: str | None, provider: str | None, provider_id: str | None) -> str:
    """Resolve contributor from direct ID or provider identity."""
    if contributor_id:
        return contributor_id
    if provider and provider_id:
        from app.services import contributor_identity_service
        found = contributor_identity_service.find_contributor_by_identity(provider, provider_id)
        if found:
            return found
        # Auto-create pending identity
        cid = f"{provider}:{provider_id}"
        contributor_identity_service.link_identity(
            contributor_id=cid, provider=provider, provider_id=provider_id,
            display_name=provider_id, verified=False,
        )
        return cid
    raise HTTPException(status_code=422, detail="Provide contributor_id OR provider+provider_id")


@router.post("/ideas/{idea_id}/stake")
async def stake_on_idea(idea_id: str, body: StakeRequest) -> dict:
    """Stake CC on an idea. Identify by contributor_id or provider+provider_id."""
    staker_id = _resolve_contributor(body.contributor_id, body.provider, body.provider_id)
    try:
        return stake_compute_service.execute_stake(
            idea_id=idea_id,
            staker_id=staker_id,
            amount_cc=body.amount_cc,
            rationale=body.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/ideas/{idea_id}/progress")
async def get_idea_progress(idea_id: str) -> dict:
    """Show idea progress: stage, tasks by phase, CC staked/spent, contributors."""
    result = stake_compute_service.get_idea_progress(idea_id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/activity")
async def get_idea_activity_endpoint(
    idea_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Return activity events for an idea."""
    try:
        return idea_service.get_idea_activity(idea_id=idea_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/ideas/{idea_id}/tasks", response_model=IdeaTasksResponse)
async def list_idea_tasks(idea_id: str) -> IdeaTasksResponse:
    """Return all tasks linked to an idea, grouped by type with status counts."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return agent_service.list_tasks_for_idea(idea_id)


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
            data.stage,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")

    # Handle stage update via dedicated set_idea_stage for sync logic
    if data.stage is not None:
        idea_service.set_idea_stage(idea_id, data.stage)

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
