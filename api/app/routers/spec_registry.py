"""Spec registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.spec_registry import SpecRegistryCreate, SpecRegistryEntry, SpecRegistryUpdate
from app.services import spec_registry_service

router = APIRouter()


@router.get("/spec-registry", response_model=list[SpecRegistryEntry])
async def list_specs(limit: int = Query(200, ge=1, le=1000)) -> list[SpecRegistryEntry]:
    return spec_registry_service.list_specs(limit=limit)


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
