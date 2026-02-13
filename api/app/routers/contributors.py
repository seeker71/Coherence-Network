from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post("/contributors", response_model=Contributor, status_code=201)
async def create_contributor(contributor: ContributorCreate, store: GraphStore = Depends(get_store)) -> Contributor:
    """Create a new contributor."""
    contrib = Contributor(**contributor.model_dump())
    return store.create_contributor(contrib)


@router.get(
    "/contributors/{contributor_id}",
    response_model=Contributor,
    responses={404: {"model": ErrorDetail}},
)
async def get_contributor(contributor_id: UUID, store: GraphStore = Depends(get_store)) -> Contributor:
    """Get contributor by ID."""
    contrib = store.get_contributor(contributor_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return contrib


@router.get("/contributors", response_model=list[Contributor])
async def list_contributors(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Contributor]:
    """List all contributors."""
    return store.list_contributors(limit=limit)
