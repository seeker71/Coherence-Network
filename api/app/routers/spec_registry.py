"""Spec registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.models.spec_registry import SpecRegistryCreate, SpecRegistryEntry, SpecRegistryUpdate
from app.services import spec_registry_service

router = APIRouter()


@router.get("/spec-registry", response_model=list[SpecRegistryEntry])
async def list_specs(
    response: Response,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[SpecRegistryEntry]:
    response.headers["x-total-count"] = str(spec_registry_service.count_specs())
    return spec_registry_service.list_specs(limit=limit, offset=offset)


@router.get("/spec-registry/cards")
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


@router.get("/spec-registry/{spec_id}", response_model=SpecRegistryEntry)
async def get_spec(spec_id: str) -> SpecRegistryEntry:
    found = spec_registry_service.get_spec(spec_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return found


@router.post("/spec-registry", response_model=SpecRegistryEntry, status_code=201)
async def create_spec(data: SpecRegistryCreate) -> SpecRegistryEntry:
    created = spec_registry_service.create_spec(data)
    if created is None:
        raise HTTPException(status_code=409, detail="Spec already exists")
    return created


@router.patch("/spec-registry/{spec_id}", response_model=SpecRegistryEntry)
async def update_spec(spec_id: str, data: SpecRegistryUpdate) -> SpecRegistryEntry:
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
