from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.graph_store import GraphStore
from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.services.contributor_hygiene import normalize_contributor_email

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post("/contributors", response_model=Contributor, status_code=201)
def create_contributor(contributor: ContributorCreate, store: GraphStore = Depends(get_store)) -> Contributor:
    """Create a new contributor."""
    normalized_email = normalize_contributor_email(str(contributor.email))
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
    responses={404: {"model": ErrorDetail}},
)
def get_contributor(contributor_id: UUID, store: GraphStore = Depends(get_store)) -> Contributor:
    """Get contributor by ID."""
    contrib = store.get_contributor(contributor_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return contrib


@router.get("/contributors", response_model=list[Contributor])
def list_contributors(
    limit: int = 100,
    include_system: bool = Query(True, description="When false, only include HUMAN contributors."),
    store: GraphStore = Depends(get_store),
) -> list[Contributor]:
    """List all contributors."""
    rows = store.list_contributors(limit=limit)
    if include_system:
        return rows
    return [row for row in rows if str(getattr(row.type, "value", row.type)).upper() == "HUMAN"]
