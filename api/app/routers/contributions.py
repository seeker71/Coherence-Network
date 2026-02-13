from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.contribution import Contribution, ContributionCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


def calculate_coherence(contribution: ContributionCreate, store: GraphStore) -> float:
    """Calculate basic coherence score."""
    score = 0.5  # Baseline

    if contribution.metadata.get("has_tests"):
        score += 0.2

    if contribution.metadata.get("has_docs"):
        score += 0.2

    if contribution.metadata.get("complexity", "medium") == "low":
        score += 0.1

    return min(score, 1.0)


@router.post("/contributions", response_model=Contribution, status_code=201)
async def create_contribution(contribution: ContributionCreate, store: GraphStore = Depends(get_store)) -> Contribution:
    """Record a new contribution."""
    if not store.get_contributor(contribution.contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")

    if not store.get_asset(contribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")

    coherence = calculate_coherence(contribution, store)

    return store.create_contribution(
        contributor_id=contribution.contributor_id,
        asset_id=contribution.asset_id,
        cost_amount=contribution.cost_amount,
        coherence_score=coherence,
        metadata=contribution.metadata,
    )


@router.get(
    "/contributions/{contribution_id}",
    response_model=Contribution,
    responses={404: {"model": ErrorDetail}},
)
async def get_contribution(contribution_id: UUID, store: GraphStore = Depends(get_store)) -> Contribution:
    """Get contribution by ID."""
    contrib = store.get_contribution(contribution_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


@router.get("/assets/{asset_id}/contributions", response_model=list[Contribution])
async def get_asset_contributions(asset_id: UUID, store: GraphStore = Depends(get_store)) -> list[Contribution]:
    """Get all contributions to an asset."""
    if not store.get_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return store.get_asset_contributions(asset_id)


@router.get("/contributors/{contributor_id}/contributions", response_model=list[Contribution])
async def get_contributor_contributions(
    contributor_id: UUID, store: GraphStore = Depends(get_store)
) -> list[Contribution]:
    """Get all contributions by a contributor."""
    if not store.get_contributor(contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")
    return store.get_contributor_contributions(contributor_id)
