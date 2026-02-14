from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor
from app.models.error import ErrorDetail

router = APIRouter()


class GitHubContribution(BaseModel):
    """GitHub webhook contribution payload."""

    contributor_email: str
    repository: str
    commit_hash: str
    cost_amount: Decimal
    metadata: dict = {}


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


@router.post("/contributions/github", response_model=Contribution, status_code=201)
async def track_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> Contribution:
    """Track contribution from GitHub webhook.

    Auto-creates contributor and asset if they don't exist.
    """
    # Find or create contributor by email
    contributor = None
    if hasattr(store, "find_contributor_by_email"):
        contributor = store.find_contributor_by_email(payload.contributor_email)

    if not contributor:
        # Create new contributor
        contributor_name = payload.contributor_email.split("@")[0]
        contributor = Contributor(name=contributor_name, email=payload.contributor_email)
        contributor = store.create_contributor(contributor)

    # Find or create asset for repository
    asset = None
    if hasattr(store, "find_asset_by_name"):
        asset = store.find_asset_by_name(payload.repository)

    if not asset:
        # Create new asset
        asset = Asset(name=payload.repository, asset_type="REPOSITORY")
        asset = store.create_asset(asset)

    # Calculate coherence score from metadata
    coherence = calculate_coherence_from_github_metadata(payload.metadata)

    # Create contribution
    return store.create_contribution(
        contributor_id=contributor.id,
        asset_id=asset.id,
        cost_amount=payload.cost_amount,
        coherence_score=coherence,
        metadata={
            **payload.metadata,
            "commit_hash": payload.commit_hash,
            "repository": payload.repository,
            "contributor_email": payload.contributor_email,
        },
    )


def calculate_coherence_from_github_metadata(metadata: dict) -> float:
    """Calculate coherence score from GitHub commit metadata."""
    score = 0.5  # Baseline

    # Check for test files
    files_changed = metadata.get("files_changed", 0)
    if files_changed > 0:
        score += 0.1

    # Check for documentation
    lines_added = metadata.get("lines_added", 0)
    if lines_added > 0 and lines_added < 100:
        score += 0.2  # Well-scoped changes
    elif lines_added >= 100:
        score += 0.1  # Large changes

    return min(score, 1.0)


@router.post("/contributions/github/debug", response_model=dict, status_code=200)
async def debug_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> dict:
    """Debug version that returns detailed error info instead of raising."""
    import traceback
    try:
        # Find or create contributor by email
        contributor = None
        if hasattr(store, "find_contributor_by_email"):
            contributor = store.find_contributor_by_email(payload.contributor_email)

        if not contributor:
            contributor_name = payload.contributor_email.split("@")[0]
            contributor = Contributor(name=contributor_name, email=payload.contributor_email)
            contributor = store.create_contributor(contributor)

        # Find or create asset
        asset = None
        if hasattr(store, "find_asset_by_name"):
            asset = store.find_asset_by_name(payload.repository)

        if not asset:
            asset = Asset(name=payload.repository, asset_type="REPOSITORY")
            asset = store.create_asset(asset)

        # Calculate coherence
        coherence = calculate_coherence_from_github_metadata(payload.metadata)

        # Create contribution
        contrib = store.create_contribution(
            contributor_id=contributor.id,
            asset_id=asset.id,
            cost_amount=payload.cost_amount,
            coherence_score=coherence,
            metadata={
                **payload.metadata,
                "commit_hash": payload.commit_hash,
                "repository": payload.repository,
                "contributor_email": payload.contributor_email,
            }
        )

        return {
            "success": True,
            "contribution_id": str(contrib.id),
            "contributor_id": str(contributor.id),
            "asset_id": str(asset.id)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
