from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.graph_store import GraphStore
from app.models.contributor import Contributor, ContributorCreate
from app.models.contributor import ContributorType
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services.contributor_hygiene import (
    is_internal_contributor_email,
    normalize_contributor_email,
    validate_real_human_registration,
)

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post(
    "/contributors",
    response_model=Contributor,
    status_code=201,
    summary="Create contributor",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
def create_contributor(contributor: ContributorCreate, store: GraphStore = Depends(get_store)) -> Contributor:
    """Register a new contributor (human or system) in the network."""
    normalized_email = normalize_contributor_email(str(contributor.email))
    if contributor.type == ContributorType.HUMAN:
        valid, reason = validate_real_human_registration(contributor.name, normalized_email)
        if not valid:
            raise HTTPException(status_code=422, detail=reason)
    elif contributor.type == ContributorType.SYSTEM:
        if not is_internal_contributor_email(normalized_email):
            raise HTTPException(status_code=422, detail="System contributor email must be an internal/system email.")
        existing_system = [
            row
            for row in store.list_contributors(limit=1000)
            if str(getattr(row.type, "value", row.type)).upper() == "SYSTEM"
        ]
        if existing_system:
            raise HTTPException(status_code=409, detail="System contributor already exists")
    if hasattr(store, "find_contributor_by_email"):
        existing = store.find_contributor_by_email(normalized_email)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Contributor email already exists")
    payload = contributor.model_dump()
    payload["email"] = normalized_email
    contrib = Contributor(**payload)
    try:
        return store.create_contributor(contrib)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/contributors/{contributor_id}",
    response_model=Contributor,
    summary="Get contributor by ID",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor(contributor_id: UUID, store: GraphStore = Depends(get_store)) -> Contributor:
    """Retrieve a single contributor by their unique identifier."""
    contrib = store.get_contributor(contributor_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return contrib


@router.get(
    "/contributors",
    response_model=PaginatedResponse[Contributor],
    summary="List contributors",
)
def list_contributors(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    include_system: bool = Query(True, description="When false, only include HUMAN contributors."),
    store: GraphStore = Depends(get_store),
) -> PaginatedResponse[Contributor]:
    """List contributors with pagination metadata."""
    all_items = store.list_contributors(limit=limit + offset + 1)
    if not include_system:
        all_items = [row for row in all_items if str(getattr(row.type, "value", row.type)).upper() == "HUMAN"]
    total = len(all_items)
    page = all_items[offset : offset + limit]
    return PaginatedResponse(items=page, total=total, limit=limit, offset=offset)
