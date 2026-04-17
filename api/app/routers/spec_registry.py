"""Spec registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.middleware.auth import require_api_key
from app.models.spec_registry import SpecRegistryCreate, SpecRegistryEntry, SpecRegistryUpdate
from app.services import spec_registry_service
from app.services.workspace_scoped_validation import (
    SpecCreateValidationContext,
    ValidationError as WorkspaceValidationError,
    validate_spec_create,
)

router = APIRouter()


@router.get("/spec-registry", response_model=list[SpecRegistryEntry], summary="List Specs")
async def list_specs(
    request: Request,
    response: Response,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    workspace_id: str | None = Query(None, description="Filter by owning workspace. Defaults to all workspaces."),
    lang: str | None = Query(None, description="Target language view. When set and a canonical spec view exists, title/summary come from the view."),
) -> list[SpecRegistryEntry]:
    from app.services.locale_projection import resolve_caller_lang
    response.headers["x-total-count"] = str(spec_registry_service.count_specs(workspace_id=workspace_id))
    items = spec_registry_service.list_specs(limit=limit, offset=offset, workspace_id=workspace_id)
    return _apply_spec_lang(items, resolve_caller_lang(request, lang))


def _apply_spec_lang(items: list[SpecRegistryEntry], lang: str | None) -> list[SpecRegistryEntry]:
    from app.services import translator_service
    from app.services import translation_cache_service as _tcache
    if not lang or not translator_service.is_supported(lang) or lang == translator_service.DEFAULT_LOCALE:
        return items
    for spec in items:
        rec = _tcache.canonical_view("spec", spec.spec_id, lang)
        if rec and rec.content_title:
            spec.title = rec.content_title
        if rec and rec.content_description:
            try:
                spec.summary = rec.content_description
            except Exception:
                pass
    return items


@router.get("/spec-registry/cards", summary="List Spec Cards")
async def list_spec_cards(
    q: str = Query("", description="Free-text search across spec title/summary/ids/contributors."),
    state: str = Query(
        "all",
        description="One of: all, unlinked, linked, in_progress, implemented, measured.",
    ),
    attention: str = Query(
        "all",
        description="One of: all, none, low, medium, high.",
    ),
    sort: str = Query(
        "attention_desc",
        description="One of: attention_desc, roi_desc, gap_desc, state_desc, updated_desc, name_asc.",
    ),
    cursor: str | None = Query(default=None, description="Offset cursor returned by previous page."),
    limit: int = Query(50, ge=1, le=200),
    linked: str = Query("all", description="One of: all, linked, unlinked."),
    min_roi: float | None = Query(default=None),
    min_value_gap: float | None = Query(default=None),
) -> dict:
    return spec_registry_service.build_spec_cards_feed(
        q=q,
        state=state,
        attention=attention,
        sort=sort,
        cursor=cursor,
        limit=limit,
        linked=linked,
        min_roi=min_roi,
        min_value_gap=min_value_gap,
    )


@router.get("/spec-registry/{spec_id}", response_model=SpecRegistryEntry, summary="Get Spec")
async def get_spec(
    spec_id: str,
    request: Request,
    lang: str | None = Query(None, description="Target language view for spec title/summary."),
) -> SpecRegistryEntry:
    from app.services.localized_errors import caller_lang, localize
    resolved = caller_lang(request, lang)
    found = spec_registry_service.get_spec(spec_id)
    if found is None:
        raise HTTPException(status_code=404, detail=localize("spec_not_found", resolved, id=spec_id))
    return _apply_spec_lang([found], resolved)[0]


@router.post("/spec-registry", response_model=SpecRegistryEntry, status_code=201, summary="Create Spec")
async def create_spec(data: SpecRegistryCreate, _key: str = Depends(require_api_key)) -> SpecRegistryEntry:
    # Layer 1 guardrails — universal across all agent provider CLIs.
    try:
        validate_spec_create(SpecCreateValidationContext(
            workspace_id=data.workspace_id or "coherence-network",
            idea_id=data.idea_id,
        ))
    except WorkspaceValidationError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})

    created = spec_registry_service.create_spec(data)
    if created is None:
        raise HTTPException(status_code=409, detail="Spec already exists")
    return created


@router.delete("/spec-registry/{spec_id}", status_code=204, summary="Delete Spec")
async def delete_spec(spec_id: str, _key: str = Depends(require_api_key)) -> None:
    deleted = spec_registry_service.delete_spec(spec_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Spec not found")
    return None


@router.patch("/spec-registry/{spec_id}", response_model=SpecRegistryEntry, summary="Update Spec")
async def update_spec(spec_id: str, data: SpecRegistryUpdate, _key: str = Depends(require_api_key)) -> SpecRegistryEntry:
    if all(
        value is None
        for value in (
            data.title,
            data.summary,
            data.potential_value,
            data.actual_value,
            data.estimated_cost,
            data.actual_cost,
            data.idea_id,
            data.process_summary,
            data.pseudocode_summary,
            data.implementation_summary,
            data.updated_by_contributor_id,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field is required")
    updated = spec_registry_service.update_spec(spec_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return updated
