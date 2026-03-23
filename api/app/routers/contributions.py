from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor, ContributorType
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services.contribution_cost_service import (
    ACTUAL_VERIFICATION_KEYS,
    ESTIMATOR_VERSION,
    estimate_commit_cost_with_provenance,
)

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


def _manual_cost_provenance(metadata: dict, cost_amount: Decimal) -> dict:
    evidence_keys = [key for key in ACTUAL_VERIFICATION_KEYS if metadata.get(key)]
    if evidence_keys:
        return {
            "cost_basis": "actual_verified",
            "cost_confidence": 1.0,
            "estimation_used": False,
            "evidence_keys": evidence_keys,
            "raw_cost_amount": str(cost_amount),
            "normalized_cost_amount": str(cost_amount),
            "cost_estimator_version": "manual_declared_v1",
        }
    return {
        "cost_basis": "declared_unverified",
        "cost_confidence": 0.25,
        "estimation_used": False,
        "evidence_keys": [],
        "raw_cost_amount": str(cost_amount),
        "normalized_cost_amount": str(cost_amount),
        "cost_estimator_version": "manual_declared_v1",
    }


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


@router.post(
    "/contributions",
    response_model=Contribution,
    status_code=201,
    summary="Record a contribution",
    responses={
        404: {"model": ErrorDetail, "description": "Contributor or asset not found"},
        422: {"model": ErrorDetail, "description": "Validation error"},
    },
)
async def create_contribution(contribution: ContributionCreate, store: GraphStore = Depends(get_store)) -> Contribution:
    """Record a new contribution linking a contributor to an asset with cost and coherence scoring."""
    if not store.get_contributor(contribution.contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")

    if not store.get_asset(contribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")

    coherence = calculate_coherence(contribution, store)
    provenance = _manual_cost_provenance(contribution.metadata, contribution.cost_amount)

    return store.create_contribution(
        contributor_id=contribution.contributor_id,
        asset_id=contribution.asset_id,
        cost_amount=contribution.cost_amount,
        coherence_score=coherence,
        metadata={**contribution.metadata, **provenance},
    )


@router.get(
    "/contributions/{contribution_id}",
    response_model=Contribution,
    summary="Get contribution by ID",
    responses={404: {"model": ErrorDetail, "description": "Contribution not found"}},
)
async def get_contribution(contribution_id: UUID, store: GraphStore = Depends(get_store)) -> Contribution:
    """Retrieve a single contribution record by its unique identifier."""
    contrib = store.get_contribution(contribution_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


@router.get("/contributions", response_model=PaginatedResponse[Contribution], summary="List contributions")
def list_contributions(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    store: GraphStore = Depends(get_store),
) -> PaginatedResponse[Contribution]:
    """List all contributions with pagination metadata (read-only)."""
    all_items = store.list_contributions(limit=limit + offset + 1)
    total = len(all_items)
    page = all_items[offset : offset + limit]
    return PaginatedResponse(items=page, total=total, limit=limit, offset=offset)


@router.get(
    "/assets/{asset_id}/contributions",
    response_model=list[Contribution],
    summary="List contributions for an asset",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset_contributions(asset_id: UUID, store: GraphStore = Depends(get_store)) -> list[Contribution]:
    """Get all contributions linked to a specific asset."""
    if not store.get_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return store.get_asset_contributions(asset_id)


@router.get(
    "/contributors/{contributor_id}/contributions",
    response_model=list[Contribution],
    summary="List contributions by a contributor",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
async def get_contributor_contributions(
    contributor_id: UUID, store: GraphStore = Depends(get_store)
) -> list[Contribution]:
    """Get all contributions made by a specific contributor."""
    if not store.get_contributor(contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")
    return store.get_contributor_contributions(contributor_id)


@router.post(
    "/contributions/github",
    response_model=Contribution,
    status_code=201,
    summary="Track GitHub contribution",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def track_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> Contribution:
    """Track a contribution from a GitHub webhook. Auto-creates contributor and asset if they don't exist."""
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
    normalized_cost, provenance = estimate_commit_cost_with_provenance(
        files_changed=files_changed,
        lines_added=lines_added,
        submitted_cost=payload.cost_amount,
        metadata=payload.metadata,
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
            **provenance,
        },
    )


# ---------------------------------------------------------------------------
# Contribution Ledger endpoints (CC staking / resource tracking)
# ---------------------------------------------------------------------------

from app.services import contribution_ledger_service


class OpenContributionRequest(BaseModel):
    """Open contribution recording — anyone can record what they did.

    Identify yourself by contributor_id OR by provider+provider_id (e.g.
    provider="github", provider_id="alice-dev"). The system resolves the
    identity automatically.
    """
    contributor_id: str | None = None
    provider: str | None = None
    provider_id: str | None = None
    type: str
    amount_cc: float = 1.0
    idea_id: str | None = None
    metadata: dict = {}


@router.post(
    "/contributions/record",
    status_code=201,
    summary="Record any contribution (open, no API key needed)",
)
async def record_open_contribution(body: OpenContributionRequest) -> dict:
    """Record any contribution. No API key needed.

    Identify yourself by contributor_id OR by provider+provider_id.
    If using a provider identity that hasn't been seen before, a pending
    contributor is created automatically — no registration needed.
    """
    from app.services import contributor_identity_service

    contributor_id = body.contributor_id

    # Resolve via provider identity if contributor_id not given
    if not contributor_id and body.provider and body.provider_id:
        found = contributor_identity_service.find_contributor_by_identity(
            body.provider, body.provider_id,
        )
        if found:
            contributor_id = found
        else:
            # Auto-create a pending identity
            contributor_id = f"{body.provider}:{body.provider_id}"
            contributor_identity_service.link_identity(
                contributor_id=contributor_id,
                provider=body.provider,
                provider_id=body.provider_id,
                display_name=body.provider_id,
                verified=False,
            )

    if not contributor_id:
        raise HTTPException(
            status_code=422,
            detail="Provide contributor_id OR provider+provider_id",
        )

    try:
        return contribution_ledger_service.record_contribution(
            contributor_id=contributor_id,
            contribution_type=body.type,
            amount_cc=body.amount_cc,
            idea_id=body.idea_id,
            metadata={
                **body.metadata,
                **({"identity_provider": body.provider, "identity_id": body.provider_id}
                   if body.provider else {}),
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/contributions/ledger/{contributor_id}",
    summary="Get contributor CC balance and history",
)
async def get_contributor_ledger(contributor_id: str, limit: int = Query(50, ge=1, le=500)) -> dict:
    """Return contributor balance (total CC by type) and recent history."""
    balance = contribution_ledger_service.get_contributor_balance(contributor_id)
    history = contribution_ledger_service.get_contributor_history(contributor_id, limit=limit)
    return {
        "balance": balance,
        "history": history,
    }


@router.get(
    "/contributions/ledger/{contributor_id}/ideas",
    summary="List ideas a contributor has invested in",
)
async def get_contributor_idea_investments(contributor_id: str) -> dict:
    """Return ideas this contributor has invested CC into, grouped by idea."""
    history = contribution_ledger_service.get_contributor_history(contributor_id, limit=500)
    idea_records = [r for r in history if r.get("idea_id")]
    # Group by idea_id
    by_idea: dict[str, list[dict]] = {}
    for rec in idea_records:
        by_idea.setdefault(rec["idea_id"], []).append(rec)
    return {
        "contributor_id": contributor_id,
        "ideas": by_idea,
    }


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
        normalized_cost, provenance = estimate_commit_cost_with_provenance(
            files_changed=files_changed,
            lines_added=lines_added,
            submitted_cost=payload.cost_amount,
            metadata=payload.metadata,
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
                **provenance,
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
