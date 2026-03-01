from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor, ContributorType
from app.models.error import ErrorDetail
from app.services.contribution_cost_service import (
    ACTUAL_VERIFICATION_KEYS,
    ESTIMATOR_VERSION,
    estimate_commit_cost_with_provenance,
)
from app.services.contributor_hygiene import is_internal_contributor_email, normalize_contributor_email

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


def _contributor_type_for_email(email: str) -> ContributorType:
    return ContributorType.SYSTEM if is_internal_contributor_email(email) else ContributorType.HUMAN


def _canonical_system_contributor(store: GraphStore) -> Contributor | None:
    systems = [
        row
        for row in store.list_contributors(limit=1000)
        if str(getattr(row.type, "value", row.type)).upper() == "SYSTEM"
    ]
    if not systems:
        return None
    systems.sort(key=lambda row: (str(row.created_at), str(row.id)))
    return systems[0]


def _resolve_registered_contributor(store: GraphStore, normalized_email: str) -> Contributor:
    existing = None
    if hasattr(store, "find_contributor_by_email"):
        existing = store.find_contributor_by_email(normalized_email)
    if existing is not None:
        return existing

    if is_internal_contributor_email(normalized_email):
        system = _canonical_system_contributor(store)
        if system is not None:
            return system
        raise HTTPException(
            status_code=409,
            detail="System contributor is not configured. Register one SYSTEM contributor first.",
        )
    raise HTTPException(
        status_code=409,
        detail="Contributor not registered. Register via /api/contributors with real name and real email first.",
    )


@router.post("/contributions", response_model=Contribution, status_code=201)
async def create_contribution(contribution: ContributionCreate, store: GraphStore = Depends(get_store)) -> Contribution:
    """Record a new contribution."""
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
    responses={404: {"model": ErrorDetail}},
)
async def get_contribution(contribution_id: UUID, store: GraphStore = Depends(get_store)) -> Contribution:
    """Get contribution by ID."""
    contrib = store.get_contribution(contribution_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


@router.get("/contributions", response_model=list[Contribution])
def list_contributions(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Contribution]:
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


@router.post("/contributions/github", response_model=Contribution, status_code=201)
async def track_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> Contribution:
    """Track contribution from GitHub webhook.

    Requires contributor to be explicitly registered.
    """
    # Resolve contributor by normalized email (or map internal emails to canonical SYSTEM).
    raw_email = str(payload.contributor_email).strip()
    normalized_email = normalize_contributor_email(raw_email)
    contributor = _resolve_registered_contributor(store, normalized_email)

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
        metadata=_github_contribution_metadata(
            payload=payload,
            normalized_email=normalized_email,
            raw_email=raw_email,
            normalized_cost=normalized_cost,
            contributor=contributor,
            provenance=provenance,
        ),
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


def _github_contribution_metadata(
    payload: GitHubContribution,
    normalized_email: str,
    raw_email: str,
    normalized_cost: Decimal,
    contributor: Contributor,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        **payload.metadata,
        "commit_hash": payload.commit_hash,
        "repository": payload.repository,
        "contributor_email": normalized_email,
        "contributor_email_raw": raw_email,
        "raw_cost_amount": str(payload.cost_amount),
        "normalized_cost_amount": str(normalized_cost),
        "cost_estimator_version": ESTIMATOR_VERSION,
        "contributor_type": str(getattr(contributor.type, "value", contributor.type)),
        **provenance,
    }


def _debug_github_dry_run_payload(
    payload: GitHubContribution,
    normalized_email: str,
    raw_email: str,
    contributor: Contributor | None,
    contributor_type: ContributorType,
    asset: Asset | None,
    coherence: float,
    normalized_cost: Decimal,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "success": True,
        "dry_run": True,
        "contributor_lookup": {
            "normalized_email": normalized_email,
            "raw_email": raw_email,
            "found_existing": contributor is not None,
            "type_if_created": contributor_type.value,
            "registration_required": contributor is None and contributor_type == ContributorType.HUMAN,
            "will_map_to_canonical_system": contributor is None and contributor_type == ContributorType.SYSTEM,
        },
        "asset_lookup": {
            "repository": payload.repository,
            "found_existing": asset is not None,
        },
        "estimation": {
            "coherence_score": coherence,
            "normalized_cost_amount": str(normalized_cost),
            "raw_cost_amount": str(payload.cost_amount),
            "provenance": provenance,
        },
    }


@router.post("/contributions/github/debug", response_model=dict, status_code=200)
async def debug_github_contribution(
    payload: GitHubContribution,
    persist: bool = Query(False, description="When true, persist contributor/asset/contribution records."),
    store: GraphStore = Depends(get_store),
) -> dict:
    """Debug version that returns detailed error info instead of raising."""
    import traceback
    try:
        raw_email = str(payload.contributor_email).strip()
        normalized_email = normalize_contributor_email(raw_email)
        # Find or create contributor by email
        contributor = None
        if hasattr(store, "find_contributor_by_email"):
            contributor = store.find_contributor_by_email(normalized_email)
        contributor_type = _contributor_type_for_email(normalized_email)

        # Find or create asset
        asset = None
        if hasattr(store, "find_asset_by_name"):
            asset = store.find_asset_by_name(payload.repository)

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

        if not persist:
            return _debug_github_dry_run_payload(
                payload=payload,
                normalized_email=normalized_email,
                raw_email=raw_email,
                contributor=contributor,
                contributor_type=contributor_type,
                asset=asset,
                coherence=coherence,
                normalized_cost=normalized_cost,
                provenance=provenance,
            )

        if not contributor:
            contributor = _resolve_registered_contributor(store, normalized_email)

        if not asset:
            asset = Asset(
                type=AssetType.CODE,
                description=f"GitHub repository: {payload.repository}"
            )
            asset = store.create_asset(asset)

        # Create contribution
        contrib = store.create_contribution(
            contributor_id=contributor.id,
            asset_id=asset.id,
            cost_amount=normalized_cost,
            coherence_score=coherence,
            metadata=_github_contribution_metadata(
                payload=payload,
                normalized_email=normalized_email,
                raw_email=raw_email,
                normalized_cost=normalized_cost,
                contributor=contributor,
                provenance=provenance,
            ),
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
