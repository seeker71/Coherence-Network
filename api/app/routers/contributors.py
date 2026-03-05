from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.graph_store import GraphStore
from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse

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
    contrib = Contributor(**contributor.model_dump())
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
    store: GraphStore = Depends(get_store),
) -> PaginatedResponse[Contributor]:
    """List contributors with pagination metadata."""
    all_items = store.list_contributors(limit=limit + offset + 1)
    total = len(all_items)
    page = all_items[offset : offset + limit]
    return PaginatedResponse(items=page, total=total, limit=limit, offset=offset)
