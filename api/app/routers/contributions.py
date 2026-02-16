from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor, ContributorType
from app.models.error import ErrorDetail
from app.services.contribution_cost_service import (
    ESTIMATOR_VERSION,
    estimate_commit_cost,
)

router = APIRouter()


class GitHubContribution(BaseModel):
    """GitHub webhook contribution payload."""

    contributor_email: str
    repository: str
    commit_hash: str
    cost_amount: Decimal
    metadata: dict = {}


class AssetContributorLinks(BaseModel):
    """Bidirectional link view for one asset -> contributors."""

    asset_id: UUID
    contributor_ids: list[UUID]
    contributor_count: int


class ContributorAssetLinks(BaseModel):
    """Bidirectional link view for one contributor -> assets."""

    contributor_id: UUID
    asset_ids: list[UUID]
    asset_count: int


class AssetContributorLinkAudit(BaseModel):
    """Coverage/audit view for asset<->contributor links."""

    total_assets: int
    total_contributors: int
    linked_assets: int
    linked_contributors: int
    missing_asset_links: list[UUID]
    missing_contributor_links: list[UUID]
    coverage_assets_ratio: float
    coverage_contributors_ratio: float
    fully_linked: bool


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


@router.get("/contributions", response_model=list[Contribution])
async def list_contributions(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Contribution]:
    """List all contributions (read-only)."""
    return store.list_contributions(limit=limit)


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


@router.get("/links/assets/{asset_id}/contributors", response_model=list[Contributor])
async def get_asset_contributors(asset_id: UUID, store: GraphStore = Depends(get_store)) -> list[Contributor]:
    """Get unique contributors linked to an asset via contributions."""
    if not store.get_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    rows = store.get_asset_contributions(asset_id)
    out: list[Contributor] = []
    seen: set[UUID] = set()
    for row in rows:
        cid = row.contributor_id
        if cid in seen:
            continue
        seen.add(cid)
        contributor = store.get_contributor(cid)
        if contributor:
            out.append(contributor)
    return out


@router.get("/links/contributors/{contributor_id}/assets", response_model=list[Asset])
async def get_contributor_assets(contributor_id: UUID, store: GraphStore = Depends(get_store)) -> list[Asset]:
    """Get unique assets linked to a contributor via contributions."""
    if not store.get_contributor(contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")
    rows = store.get_contributor_contributions(contributor_id)
    out: list[Asset] = []
    seen: set[UUID] = set()
    for row in rows:
        aid = row.asset_id
        if aid in seen:
            continue
        seen.add(aid)
        asset = store.get_asset(aid)
        if asset:
            out.append(asset)
    return out


@router.get("/links/assets/with-contributors", response_model=list[AssetContributorLinks])
async def list_asset_contributor_links(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[AssetContributorLinks]:
    """List link state for assets -> contributors (resources are tracked as assets)."""
    assets = store.list_assets(limit=limit)
    out: list[AssetContributorLinks] = []
    for asset in assets:
        contributor_ids = sorted({row.contributor_id for row in store.get_asset_contributions(asset.id)})
        out.append(
            AssetContributorLinks(
                asset_id=asset.id,
                contributor_ids=contributor_ids,
                contributor_count=len(contributor_ids),
            )
        )
    return out


@router.get("/links/contributors/with-assets", response_model=list[ContributorAssetLinks])
async def list_contributor_asset_links(
    limit: int = 100, store: GraphStore = Depends(get_store)
) -> list[ContributorAssetLinks]:
    """List link state for contributors -> assets."""
    contributors = store.list_contributors(limit=limit)
    out: list[ContributorAssetLinks] = []
    for contributor in contributors:
        asset_ids = sorted({row.asset_id for row in store.get_contributor_contributions(contributor.id)})
        out.append(
            ContributorAssetLinks(
                contributor_id=contributor.id,
                asset_ids=asset_ids,
                asset_count=len(asset_ids),
            )
        )
    return out


@router.get("/links/asset-contributor/audit", response_model=AssetContributorLinkAudit)
async def audit_asset_contributor_links(store: GraphStore = Depends(get_store)) -> AssetContributorLinkAudit:
    """Audit whether every asset and contributor has at least one bidirectional link."""
    assets = store.list_assets(limit=100000)
    contributors = store.list_contributors(limit=100000)

    missing_asset_links: list[UUID] = []
    for asset in assets:
        rows = store.get_asset_contributions(asset.id)
        if not rows:
            missing_asset_links.append(asset.id)
            continue
        if not any(store.get_contributor(row.contributor_id) for row in rows):
            missing_asset_links.append(asset.id)

    missing_contributor_links: list[UUID] = []
    for contributor in contributors:
        rows = store.get_contributor_contributions(contributor.id)
        if not rows:
            missing_contributor_links.append(contributor.id)
            continue
        if not any(store.get_asset(row.asset_id) for row in rows):
            missing_contributor_links.append(contributor.id)

    total_assets = len(assets)
    total_contributors = len(contributors)
    linked_assets = total_assets - len(missing_asset_links)
    linked_contributors = total_contributors - len(missing_contributor_links)
    coverage_assets_ratio = float(linked_assets / total_assets) if total_assets > 0 else 1.0
    coverage_contributors_ratio = float(linked_contributors / total_contributors) if total_contributors > 0 else 1.0

    return AssetContributorLinkAudit(
        total_assets=total_assets,
        total_contributors=total_contributors,
        linked_assets=linked_assets,
        linked_contributors=linked_contributors,
        missing_asset_links=missing_asset_links,
        missing_contributor_links=missing_contributor_links,
        coverage_assets_ratio=round(coverage_assets_ratio, 4),
        coverage_contributors_ratio=round(coverage_contributors_ratio, 4),
        fully_linked=not missing_asset_links and not missing_contributor_links,
    )


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
        contributor = Contributor(
            type=ContributorType.HUMAN,
            name=contributor_name,
            email=payload.contributor_email
        )
        try:
            contributor = store.create_contributor(contributor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Find or create asset for repository
    asset = None
    if hasattr(store, "find_asset_by_name"):
        asset = store.find_asset_by_name(payload.repository)

    if not asset:
        # Create new asset
        asset = Asset(
            type=AssetType.CODE,
            description=f"GitHub repository: {payload.repository}"
        )
        asset = store.create_asset(asset)

    # Calculate coherence score from metadata
    coherence = calculate_coherence_from_github_metadata(payload.metadata)
    files_changed = payload.metadata.get("files_changed", 0)
    lines_added = payload.metadata.get("lines_added", 0)
    normalized_cost = estimate_commit_cost(
        files_changed=files_changed,
        lines_added=lines_added,
        submitted_cost=payload.cost_amount,
    )

    # Create contribution
    return store.create_contribution(
        contributor_id=contributor.id,
        asset_id=asset.id,
        cost_amount=normalized_cost,
        coherence_score=coherence,
        metadata={
            **payload.metadata,
            "commit_hash": payload.commit_hash,
            "repository": payload.repository,
            "contributor_email": payload.contributor_email,
            "raw_cost_amount": str(payload.cost_amount),
            "normalized_cost_amount": str(normalized_cost),
            "cost_estimator_version": ESTIMATOR_VERSION,
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
            contributor = Contributor(
                type=ContributorType.HUMAN,
                name=contributor_name,
                email=payload.contributor_email
            )
            contributor = store.create_contributor(contributor)

        # Find or create asset
        asset = None
        if hasattr(store, "find_asset_by_name"):
            asset = store.find_asset_by_name(payload.repository)

        if not asset:
            asset = Asset(
                type=AssetType.CODE,
                description=f"GitHub repository: {payload.repository}"
            )
            asset = store.create_asset(asset)

        # Calculate coherence
        coherence = calculate_coherence_from_github_metadata(payload.metadata)
        files_changed = payload.metadata.get("files_changed", 0)
        lines_added = payload.metadata.get("lines_added", 0)
        normalized_cost = estimate_commit_cost(
            files_changed=files_changed,
            lines_added=lines_added,
            submitted_cost=payload.cost_amount,
        )

        # Create contribution
        contrib = store.create_contribution(
            contributor_id=contributor.id,
            asset_id=asset.id,
            cost_amount=normalized_cost,
            coherence_score=coherence,
            metadata={
                **payload.metadata,
                "commit_hash": payload.commit_hash,
                "repository": payload.repository,
                "contributor_email": payload.contributor_email,
                "raw_cost_amount": str(payload.cost_amount),
                "normalized_cost_amount": str(normalized_cost),
                "cost_estimator_version": ESTIMATOR_VERSION,
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
