"""Idea portfolio API routes.

Implements: spec-053 (portfolio governance), spec-126 (idea lifecycle)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.middleware.auth import require_api_key
from app.middleware.traceability import traces_to
from app.services.locale_projection import resolve_caller_lang

from app.models.idea import (
    GovernanceHealth,
    IdeaCountResponse,
    IdeaConceptResonanceResponse,
    IdeaCreate,
    IdeaShowcaseResponse,
    IdeaStage,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestionAnswerUpdate,
    IdeaSelectionResult,
    IdeaStorageInfo,
    IdeaTagCatalogResponse,
    IdeaTagUpdateRequest,
    IdeaTagUpdateResponse,
    IdeaTasksResponse,
    IdeaUpdate,
    IdeaWithScore,
    ProgressDashboard,
    RightSizingApplyRequest,
    RightSizingApplyResponse,
    RightSizingHistoryResponse,
    RightSizingReport,
    RollupProgress,
    SlugUpdateRequest,
    SlugUpdateResponse,
    StageSetRequest,
)
from app.models.translation import IdeaTranslationResponse
from app.models.translation import TranslationLens
from app.services import agent_service, concept_translation_service, idea_service, idea_selection_ab_service, inventory_service, stake_compute_service, translate_service
from app.services.workspace_scoped_validation import (
    IdeaCreateValidationContext,
    ValidationError as WorkspaceValidationError,
    validate_idea_create,
)
from app.services import lens_translation_service
from app.services.translate_service import TranslateLens
from app.models.lens_translation import TranslationRegenerateBody

router = APIRouter()


@router.get("/ideas", response_model=IdeaPortfolioResponse, summary="List Ideas")
@traces_to(spec="053", idea="portfolio-governance", description="Browse the idea portfolio ranked by ROI")
async def list_ideas(
    request: Request,
    only_unvalidated: bool = Query(False, description="When true, only return ideas not yet validated."),
    include_internal: bool = Query(True, description="When false, hide system-generated/internal ideas."),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    read_only_guard: bool = Query(False, description="When true, do not persist ensure logic (for invariant/guard runs)."),
    sort: str = Query("free_energy", description="Sort method: 'free_energy' (default, Method A) or 'marginal_cc' (Method B)."),
    tags: str = Query("", description="Comma-separated tag filter. When present, return only ideas matching all normalized tags."),
    curated_only: bool = Query(False, description="When true, only return the 16 curated super-ideas from ideas/*.md."),
    pillar: str | None = Query(None, description="Filter by pillar: realization|pipeline|economics|surfaces|network|foundation."),
    workspace_id: str | None = Query(None, description="Filter by owning workspace. Defaults to all workspaces."),
    lang: str | None = Query(None, description="Target language view. When set and a canonical idea view exists, name/description come from the view."),
) -> IdeaPortfolioResponse:
    raw_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    parsed_tags = idea_service.normalize_tags(raw_tags) if raw_tags else None
    resp = idea_service.list_ideas(
        only_unvalidated=only_unvalidated,
        include_internal=include_internal,
        limit=limit,
        offset=offset,
        read_only_guard=read_only_guard,
        sort_method=sort,
        tags_filter=parsed_tags,
        curated_only=curated_only,
        pillar=pillar,
        workspace_id=workspace_id,
    )
    return _apply_lang_views(resp, resolve_caller_lang(request, lang))


def _apply_lang_views(resp: IdeaPortfolioResponse, lang: str | None) -> IdeaPortfolioResponse:
    """When a language is requested, substitute each idea's name/description
    with the canonical view for that lang (if one exists). Ideas without a
    view in the target language keep the anchor content — the caller can tell
    which is which via a separate view fetch.
    """
    from app.services import translator_service
    from app.services import translation_cache_service as _tcache

    if not lang or not translator_service.is_supported(lang) or lang == translator_service.DEFAULT_LOCALE:
        return resp
    for idea in resp.ideas:
        rec = _tcache.canonical_view("idea", idea.id, lang)
        if rec and rec.content_hash:
            if rec.content_title:
                idea.name = rec.content_title
            if rec.content_description and hasattr(idea, "description"):
                try:
                    idea.description = rec.content_description
                except Exception:
                    pass
    return resp


@router.get("/ideas/tags", response_model=IdeaTagCatalogResponse, summary="Return the normalized idea tag catalog with idea counts (spec 129)")
async def get_idea_tags_catalog() -> IdeaTagCatalogResponse:
    """Return the normalized idea tag catalog with idea counts (spec 129)."""
    return idea_service.get_tag_catalog()


@router.get("/ideas/storage", response_model=IdeaStorageInfo, summary="Get Idea Storage Info")
async def get_idea_storage_info() -> IdeaStorageInfo:
    return idea_service.storage_info()


@router.get("/ideas/cards", summary="List Idea Cards")
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
    try:
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
    except Exception:
        # Fallback: return simple card data from graph when inventory_service fails
        from app.services import graph_service
        search = q.lower() if q else None
        result = graph_service.list_nodes(type="idea", limit=limit, offset=0, search=search)
        items = []
        for n in result.get("items", []):
            items.append({
                "id": n.get("id"),
                "name": n.get("name"),
                "description": (n.get("description") or "")[:200],
                "manifestation_status": n.get("manifestation_status", "none"),
                "free_energy_score": n.get("free_energy_score", 0),
                "roi_cc": n.get("roi_cc", 0),
                "value_gap": n.get("value_gap", 0),
            })
        return {"items": items, "total": result.get("total", len(items)), "cursor": None}


@router.get("/ideas/cards/changes", summary="List Idea Card Changes")
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


@router.get("/ideas/health", response_model=GovernanceHealth, summary="Portfolio governance effectiveness snapshot (spec 126)")
async def get_governance_health(
    window_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> GovernanceHealth:
    """Portfolio governance effectiveness snapshot (spec 126)."""
    return idea_service.compute_governance_health(window_days=window_days)


# ── Right-sizing endpoints (spec 158) ────────────────────────────────────────


@router.get("/ideas/right-sizing", response_model=RightSizingReport, summary="Portfolio right-sizing report with health counts and suggestions (spec 158)")
async def get_right_sizing_report() -> RightSizingReport:
    """Portfolio right-sizing report with health counts and suggestions (spec 158)."""
    from app.services import right_sizing_service
    return right_sizing_service.build_report()


@router.post("/ideas/right-sizing/apply", response_model=RightSizingApplyResponse, summary="Execute a split or merge suggestion, with dry_run support (spec 158)")
async def apply_right_sizing(
    body: RightSizingApplyRequest,
    _key: str = Depends(require_api_key),
) -> RightSizingApplyResponse:
    """Execute a split or merge suggestion, with dry_run support (spec 158)."""
    from app.services import right_sizing_service

    valid_actions = {"split_into_children", "merge_and_archive"}
    if body.action not in valid_actions:
        raise HTTPException(status_code=422, detail=f"Invalid action: {body.action}. Must be one of {sorted(valid_actions)}")

    try:
        return right_sizing_service.apply_suggestion(
            suggestion_type=body.suggestion_type,
            idea_id=body.idea_id,
            action=body.action,
            proposed_children=body.proposed_children,
            overlap_with_id=body.overlap_with_id,
            dry_run=body.dry_run,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/ideas/right-sizing/history", response_model=RightSizingHistoryResponse, summary="Time-series health snapshots for the portfolio (spec 158)")
async def get_right_sizing_history(
    days: int = Query(7, ge=1, le=365, description="Lookback window in days"),
) -> RightSizingHistoryResponse:
    """Time-series health snapshots for the portfolio (spec 158)."""
    from app.services import right_sizing_service
    return right_sizing_service.get_history(days=days)


@router.get("/ideas/showcase", response_model=IdeaShowcaseResponse, summary="Funder-facing idea summaries with ask, budget, proof, and status")
async def list_ideas_showcase() -> IdeaShowcaseResponse:
    """Funder-facing idea summaries with ask, budget, proof, and status."""
    return idea_service.list_showcase_ideas()


@router.get("/ideas/resonance", summary="Return ideas with recent activity, sorted by most-recent-activity-first")
async def get_resonance(
    window_hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = Query(None, description="Target language view — when set, idea names come from canonical views for that lang where available."),
) -> list[dict]:
    """Return ideas with recent activity, sorted by most-recent-activity-first."""
    from app.services import translator_service
    from app.services import translation_cache_service as _tcache

    items = idea_service.get_resonance_feed(window_hours=window_hours, limit=limit)
    if lang and translator_service.is_supported(lang) and lang != translator_service.DEFAULT_LOCALE:
        for it in items:
            iid = it.get("idea_id") or it.get("id")
            if not iid:
                continue
            rec = _tcache.canonical_view("idea", iid, lang)
            if rec and rec.content_title:
                it["name"] = rec.content_title
    return items


@router.get("/ideas/{idea_id}/concept-resonance", response_model=IdeaConceptResonanceResponse, summary="Return conceptually related ideas, preferring matches from different domains")
async def get_idea_concept_resonance(
    idea_id: str,
    limit: int = Query(5, ge=1, le=25),
    min_score: float = Query(0.05, ge=0.0, le=1.0),
) -> IdeaConceptResonanceResponse:
    """Return conceptually related ideas, preferring matches from different domains."""
    result = idea_service.get_concept_resonance_matches(
        idea_id=idea_id,
        limit=limit,
        min_score=min_score,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/translate", response_model=IdeaTranslationResponse, summary="Reframe an idea through a worldview using the ontology graph and resonance edges")
async def translate_idea_view(
    idea_id: str,
    view: TranslationLens = Query(..., description="Worldview lens (conceptual framing, not MT)."),
) -> IdeaTranslationResponse:
    """Reframe an idea through a worldview using the ontology graph and resonance edges."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")

    tags: list[str] = []
    if hasattr(idea, "tags") and idea.tags:
        tags = list(idea.tags)
    elif hasattr(idea, "idea") and hasattr(idea.idea, "tags") and idea.idea.tags:
        tags = list(idea.idea.tags)

    desc = ""
    if hasattr(idea, "description"):
        desc = idea.description or ""
    elif hasattr(idea, "idea") and hasattr(idea.idea, "description"):
        desc = idea.idea.description or ""

    name = ""
    if hasattr(idea, "name"):
        name = idea.name or idea_id
    elif hasattr(idea, "idea") and hasattr(idea.idea, "name"):
        name = idea.idea.name or idea_id

    return concept_translation_service.translate_idea(
        idea_id=idea_id,
        idea_name=name,
        idea_description=desc,
        idea_tags=tags,
        view=view.value,
    )


@router.get("/ideas/selection-ab/stats", summary="Get Selection Ab Stats")
async def get_selection_ab_stats() -> dict:
    return idea_selection_ab_service.get_comparison()


@router.post("/ideas/select", response_model=IdeaSelectionResult, summary="Weighted stochastic idea selection")
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


@router.get("/ideas/count", response_model=IdeaCountResponse, summary="Count Ideas")
async def count_ideas() -> IdeaCountResponse:
    return idea_service.count_ideas()


@router.get("/ideas/progress", response_model=ProgressDashboard, summary="Per-stage idea counts and completion percentage (spec 138)")
async def get_progress_dashboard() -> ProgressDashboard:
    """Per-stage idea counts and completion percentage (spec 138)."""
    return idea_service.compute_progress_dashboard()


@router.get("/ideas/portfolio-summary", summary="Summary of curated super-ideas with spec counts, pillar grouping, and red/yellow/green he…")
async def get_portfolio_summary() -> dict:
    """Summary of curated super-ideas with spec counts, pillar grouping, and red/yellow/green health."""
    return idea_service.get_portfolio_summary()


@router.post("/ideas/{idea_id}/advance", response_model=IdeaWithScore, summary="Advance an idea to the next sequential stage (spec 138)")
async def advance_idea_stage(idea_id: str, _key: str = Depends(require_api_key)) -> IdeaWithScore:
    """Advance an idea to the next sequential stage (spec 138)."""
    result, error = idea_service.advance_idea_stage(idea_id)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    if error == "already_complete":
        raise HTTPException(status_code=409, detail="Idea is already complete")
    return result


@router.post("/ideas/{idea_id}/stage", response_model=IdeaWithScore, summary="Set an explicit stage for an idea (admin override, spec 138)")
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


@router.post("/ideas/{idea_id}/fork", status_code=201, summary="Fork an existing idea. Identify by forker_id or provider+provider_id")
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


@router.post("/ideas/{idea_id}/stake", summary="Stake CC on an idea. Identify by contributor_id or provider+provider_id")
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


@router.get("/ideas/{idea_id}/progress", summary="Show idea progress: stage, tasks by phase, CC staked/spent, contributors")
async def get_idea_progress(idea_id: str) -> dict:
    """Show idea progress: stage, tasks by phase, CC staked/spent, contributors."""
    result = stake_compute_service.get_idea_progress(idea_id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/activity", summary="Return activity events for an idea")
async def get_idea_activity_endpoint(
    idea_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Return activity events for an idea."""
    try:
        return idea_service.get_idea_activity(idea_id=idea_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/ideas/{idea_id}/tasks", response_model=IdeaTasksResponse, summary="Return all tasks linked to an idea, grouped by type with status counts")
async def list_idea_tasks(idea_id: str) -> IdeaTasksResponse:
    """Return all tasks linked to an idea, grouped by type with status counts."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return agent_service.list_tasks_for_idea(idea_id)


@router.put("/ideas/{idea_id}/tags", response_model=IdeaTagUpdateResponse, summary="Replace the full tag set for an idea after normalization (spec 129)")
async def put_idea_tags(idea_id: str, body: IdeaTagUpdateRequest) -> IdeaTagUpdateResponse:
    """Replace the full tag set for an idea after normalization (spec 129)."""
    normalized, valid = idea_service.validate_raw_tags(body.tags)
    if not valid:
        raise HTTPException(status_code=422, detail="One or more tag values are invalid")
    result = idea_service.set_idea_tags(idea_id, normalized)
    if result is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/translations", summary="All worldview translations for an idea (spec-181 batch)")
async def list_idea_translations_all(idea_id: str) -> dict:
    """All worldview translations for an idea (spec-181 batch)."""
    out = lens_translation_service.list_translations_for_idea(idea_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return out


@router.get("/ideas/{idea_id}/translations/{lens_id}", summary="Single lens translation with optional belief resonance (spec-181)")
async def get_idea_translation_spec181(
    idea_id: str,
    lens_id: str,
    contributor_id: str | None = Query(None, description="Optional contributor for resonance_delta"),
) -> dict:
    """Single lens translation with optional belief resonance (spec-181)."""
    if translate_service.get_lens_meta(lens_id) is None:
        raise HTTPException(status_code=404, detail=f"Lens '{lens_id}' not found")
    result = lens_translation_service.build_idea_translation(
        idea_id,
        lens_id,
        contributor_id=contributor_id,
        force_regenerate=False,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.post("/ideas/{idea_id}/translations/{lens_id}", summary="Force-regenerate cached translation (spec-181)")
async def post_idea_translation_regenerate(
    idea_id: str,
    lens_id: str,
    body: TranslationRegenerateBody,
    _key: str = Depends(require_api_key),
) -> dict:
    """Force-regenerate cached translation (spec-181)."""
    if translate_service.get_lens_meta(lens_id) is None:
        raise HTTPException(status_code=404, detail=f"Lens '{lens_id}' not found")
    result = lens_translation_service.build_idea_translation(
        idea_id,
        lens_id,
        contributor_id=body.contributor_id,
        force_regenerate=body.force_regenerate,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/translate", summary="Translate an idea's conceptual framing through a worldview lens")
async def translate_idea_view(
    idea_id: str,
    view: TranslateLens = Query(..., description="Target worldview lens"),
) -> dict:
    """Translate an idea's conceptual framing through a worldview lens.

    Not machine translation of language — translation of conceptual framework.
    Uses ontology concept graph and resonance edges to generate framing.
    """
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")

    tags: list[str] = []
    if hasattr(idea, "tags") and idea.tags:
        tags = list(idea.tags)
    elif hasattr(idea, "idea") and hasattr(idea.idea, "tags") and idea.idea.tags:
        tags = list(idea.idea.tags)

    desc = ""
    if hasattr(idea, "description"):
        desc = idea.description or ""
    elif hasattr(idea, "idea") and hasattr(idea.idea, "description"):
        desc = idea.idea.description or ""

    name = ""
    if hasattr(idea, "name"):
        name = idea.name or idea_id
    elif hasattr(idea, "idea") and hasattr(idea.idea, "name"):
        name = idea.idea.name or idea_id

    return translate_service.translate_idea(
        idea_id=idea_id,
        idea_name=name,
        idea_description=desc,
        idea_tags=tags,
        view=view.value,
    )


@router.get("/ideas/{idea_id}/children", response_model=list[IdeaWithScore], summary="Return all child ideas whose parent_idea_id equals {idea_id}")
async def list_idea_children(idea_id: str) -> list[IdeaWithScore]:
    """Return all child ideas whose parent_idea_id equals {idea_id}.

    Used by the idea detail page to render absorbed ideas under a super-idea.
    """
    # Validate that the parent exists (gives 404 rather than empty list for typos)
    if idea_service.get_idea(idea_id) is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea_service.list_children_of(idea_id)


@router.get("/ideas/{idea_id}/specs", summary="Return all specs linked to {idea_id} via their frontmatter idea_id")
async def list_idea_specs(idea_id: str) -> list[dict]:
    """Return all specs linked to {idea_id} via their frontmatter idea_id."""
    from app.services import spec_registry_service
    if idea_service.get_idea(idea_id) is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    specs = spec_registry_service.list_specs_for_idea(idea_id)
    return [s.model_dump(mode="json") for s in specs]


@router.get("/ideas/{idea_id}/lifecycle", summary="Return lifecycle closure state and blockers for an idea")
async def get_idea_lifecycle(idea_id: str) -> dict:
    """Return lifecycle closure state and blockers for an idea."""
    result = idea_service.get_idea_lifecycle(idea_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return result


@router.get("/ideas/{idea_id}/rollup", response_model=RollupProgress, summary="Return rollup progress for a super-idea: children validated / total children (R4)")
@traces_to(spec="super-idea-rollup-criteria", idea="idea-realization-engine", description="Rollup progress for a super-idea")
async def get_idea_rollup(idea_id: str) -> RollupProgress:
    """Return rollup progress for a super-idea: children validated / total children (R4)."""
    progress = idea_service.get_rollup_progress(idea_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return progress


@router.post("/ideas/{idea_id}/validate-rollup", response_model=RollupProgress, summary="Check rollup criteria for a super-idea and auto-update manifestation_status (R2, R3)")
@traces_to(spec="super-idea-rollup-criteria", idea="idea-realization-engine", description="Validate super-idea rollup criteria and auto-update status")
async def validate_super_idea_rollup(idea_id: str, _key: str = Depends(require_api_key)) -> RollupProgress:
    """Check rollup criteria for a super-idea and auto-update manifestation_status (R2, R3)."""
    progress, error = idea_service.validate_super_idea(idea_id)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")
    if error == "not_super":
        raise HTTPException(status_code=422, detail="Idea is not a super-idea; rollup validation only applies to super-ideas")
    return progress


@router.get("/ideas/breath-overview", summary="Portfolio breath overview — gas/water/ice phase distribution for all curated super-ideas")
async def get_breath_overview() -> dict:
    """Portfolio breath overview — gas/water/ice phase distribution for all curated super-ideas."""
    from app.services import breath_service
    return breath_service.compute_breath_overview()


@router.get("/ideas/{idea_id}/resonance", summary="Return top resonant ideas for a given idea, with coherence scores and cross-domain flags")
async def get_idea_resonance(
    idea_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Return top resonant ideas for a given idea, with coherence scores and cross-domain flags."""
    try:
        from app.services import idea_resonance_service
        source_raw = idea_service.get_idea(idea_id)
        if source_raw is None:
            raise HTTPException(status_code=404, detail="Idea not found")

        source_dict = {
            "id": source_raw.id if hasattr(source_raw, "id") else source_raw.get("id", idea_id),
            "name": source_raw.name if hasattr(source_raw, "name") else source_raw.get("name", ""),
            "description": source_raw.description if hasattr(source_raw, "description") else source_raw.get("description", ""),
            "tags": (source_raw.tags if hasattr(source_raw, "tags") else source_raw.get("tags")) or [],
            "interfaces": (source_raw.interfaces if hasattr(source_raw, "interfaces") else source_raw.get("interfaces")) or [],
        }

        portfolio = idea_service.list_ideas(limit=500, offset=0, read_only_guard=True)
        all_ideas_raw = portfolio.ideas if hasattr(portfolio, "ideas") else []
        all_ideas = []
        for item in all_ideas_raw:
            all_ideas.append({
                "id": item.id if hasattr(item, "id") else item.get("id", ""),
                "name": item.name if hasattr(item, "name") else item.get("name", ""),
                "description": item.description if hasattr(item, "description") else item.get("description", ""),
                "tags": (item.tags if hasattr(item, "tags") else item.get("tags")) or [],
                "interfaces": (item.interfaces if hasattr(item, "interfaces") else item.get("interfaces")) or [],
            })

        matches = idea_resonance_service.find_resonant_ideas(
            source_idea=source_dict,
            all_ideas=all_ideas,
            limit=limit,
        )
        return [
            {
                "idea_id": m.idea_id_b if m.idea_id_a == idea_id else m.idea_id_a,
                "name": m.name_b if m.idea_id_a == idea_id else m.name_a,
                "coherence": m.coherence,
                "cross_domain": m.cross_domain,
                "domain": m.domain_b if m.idea_id_a == idea_id else m.domain_a,
            }
            for m in matches
        ]
    except HTTPException:
        raise
    except Exception:
        # Graceful degradation: return empty list on any failure
        return []


@router.get("/ideas/{idea_id}/breath", summary="Return breath analysis (gas/water/ice phase distribution) for an idea")
async def get_idea_breath(idea_id: str) -> dict:
    """Return breath analysis (gas/water/ice phase distribution) for an idea."""
    from app.services import breath_service
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return breath_service.compute_idea_breath(idea_id)


@router.get("/ideas/{idea_id}", response_model=IdeaWithScore, summary="Get Idea")
async def get_idea(idea_id: str) -> IdeaWithScore:
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.post("/ideas", response_model=IdeaWithScore, status_code=201, summary="Create Idea")
async def create_idea(data: IdeaCreate) -> IdeaWithScore:
    # Layer 1 guardrails — universal across all agent provider CLIs.
    try:
        validate_idea_create(IdeaCreateValidationContext(
            workspace_id=data.workspace_id or "coherence-network",
            pillar=data.pillar,
            parent_idea_id=data.parent_idea_id,
        ))
    except WorkspaceValidationError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})

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
        tags=data.tags,
        work_type=data.work_type,
        lifecycle=data.lifecycle,
        duplicate_of=data.duplicate_of,
        workspace_git_url=data.workspace_git_url,
        slug=data.slug,
        pillar=data.pillar,
        workspace_id=data.workspace_id,
        rollup_condition=data.rollup_condition,
    )
    if created is None:
        raise HTTPException(status_code=409, detail="Idea already exists")
    return created


@router.patch("/ideas/{idea_id}", response_model=IdeaWithScore, summary="Update Idea")
async def update_idea(idea_id: str, data: IdeaUpdate, _key: str = Depends(require_api_key)) -> IdeaWithScore:
    if all(
        field is None
        for field in (
            data.actual_value,
            data.actual_cost,
            data.confidence,
            data.manifestation_status,
            data.stage,
            data.parent_idea_id,
            data.potential_value,
            data.estimated_cost,
            data.description,
            data.name,
            data.work_type,
            data.lifecycle,
            data.duplicate_of,
            data.workspace_git_url,
            data.interfaces,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")

    # Handle stage update via dedicated set_idea_stage for sync logic
    if data.stage is not None:
        idea_service.set_idea_stage(idea_id, data.stage)

    # Handle parent_idea_id update directly on the idea object
    if data.parent_idea_id is not None:
        idea_service.set_parent_idea(idea_id, data.parent_idea_id)

    updated = idea_service.update_idea(
        idea_id=idea_id,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        confidence=data.confidence,
        manifestation_status=data.manifestation_status,
        potential_value=data.potential_value,
        estimated_cost=data.estimated_cost,
        description=data.description,
        name=data.name,
        work_type=data.work_type,
        lifecycle=data.lifecycle,
        duplicate_of=data.duplicate_of,
        workspace_git_url=data.workspace_git_url,
        interfaces=data.interfaces,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return updated


@router.patch("/ideas/{idea_id}/slug", response_model=SlugUpdateResponse, summary="Rename an idea's slug. Old slug is kept in slug_history for permanent redirect")
async def update_idea_slug(
    idea_id: str,
    body: SlugUpdateRequest,
    _key: str = Depends(require_api_key),
) -> SlugUpdateResponse:
    """Rename an idea's slug. Old slug is kept in slug_history for permanent redirect."""
    try:
        updated = idea_service.update_idea_slug(idea_id, body.slug)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return SlugUpdateResponse(
        id=updated.id,
        slug=updated.slug,
        slug_history=updated.slug_history,
    )


@router.post("/ideas/{idea_id}/questions", response_model=IdeaWithScore, summary="Add Idea Question")
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


@router.post("/ideas/{idea_id}/questions/answer", response_model=IdeaWithScore, summary="Answer Idea Question")
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
