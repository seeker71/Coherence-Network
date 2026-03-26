"""Contributions router — backed by graph_nodes + graph_edges."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor, ContributorType
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service
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


# ── Graph helpers ─────────────────────────────────────────────────


def _find_contributor_node(contributor_id: UUID) -> dict | None:
    """Find a contributor node by legacy UUID."""
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return node
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("legacy_id") == str(contributor_id) or n.get("name") == str(contributor_id):
            return n
    return None


def _find_asset_node(asset_id: UUID) -> dict | None:
    """Find an asset node by legacy UUID."""
    node = graph_service.get_node(f"asset:{asset_id}")
    if node:
        return node
    result = graph_service.list_nodes(type="asset", limit=500)
    for n in result.get("items", []):
        if n.get("legacy_id") == str(asset_id):
            return n
    return None


def _find_contributor_by_email(email: str) -> dict | None:
    """Find a contributor node by email."""
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("email") == email:
            return n
    return None


def _find_asset_by_name(name: str) -> dict | None:
    """Find an asset node by description/name."""
    result = graph_service.list_nodes(type="asset", limit=500)
    for n in result.get("items", []):
        desc = n.get("description", "")
        if name in desc or n.get("name") == name:
            return n
    return None


def _edge_to_contribution(edge: dict) -> Contribution:
    """Convert a graph edge to a Contribution model."""
    props = edge.get("properties", {})
    return Contribution(
        id=UUID(props["contribution_id"]) if props.get("contribution_id") else uuid4(),
        contributor_id=UUID(props["contributor_id"]) if props.get("contributor_id") else uuid4(),
        asset_id=UUID(props["asset_id"]) if props.get("asset_id") else uuid4(),
        cost_amount=Decimal(str(props.get("cost_amount", "0"))),
        coherence_score=float(props.get("coherence_score", 0.5)),
        metadata=props.get("metadata", {}),
    )


def _store_contribution(
    contributor_id: UUID,
    asset_id: UUID,
    contributor_node_id: str,
    asset_node_id: str,
    cost_amount: Decimal,
    coherence_score: float,
    metadata: dict,
) -> Contribution:
    """Store a contribution as a graph edge and return the Contribution model."""
    contrib_id = uuid4()
    graph_service.create_edge(
        from_id=contributor_node_id,
        to_id=asset_node_id,
        type="contribution",
        properties={
            "contribution_id": str(contrib_id),
            "contributor_id": str(contributor_id),
            "asset_id": str(asset_id),
            "cost_amount": str(cost_amount),
            "coherence_score": coherence_score,
            "metadata": metadata,
        },
        strength=coherence_score,
        created_by="contributions_router",
    )
    # Update total_cost on the asset node
    asset_node = graph_service.get_node(asset_node_id)
    if asset_node:
        current_cost = Decimal(str(asset_node.get("total_cost", "0")))
        graph_service.update_node(
            asset_node_id,
            properties={"total_cost": str(current_cost + cost_amount)},
        )
    return Contribution(
        id=contrib_id,
        contributor_id=contributor_id,
        asset_id=asset_id,
        cost_amount=cost_amount,
        coherence_score=coherence_score,
        metadata=metadata,
    )


# ── Cost provenance ──────────────────────────────────────────────


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


def calculate_coherence(contribution: ContributionCreate) -> float:
    """Calculate basic coherence score."""
    score = 0.5  # Baseline
    if contribution.metadata.get("has_tests"):
        score += 0.2
    if contribution.metadata.get("has_docs"):
        score += 0.2
    if contribution.metadata.get("complexity", "medium") == "low":
        score += 0.1
    return min(score, 1.0)


# ── Core endpoints ───────────────────────────────────────────────


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
async def create_contribution(contribution: ContributionCreate) -> Contribution:
    """Record a new contribution linking a contributor to an asset with cost and coherence scoring."""
    contributor_node = _find_contributor_node(contribution.contributor_id)
    if not contributor_node:
        raise HTTPException(status_code=404, detail="Contributor not found")

    asset_node = _find_asset_node(contribution.asset_id)
    if not asset_node:
        raise HTTPException(status_code=404, detail="Asset not found")

    coherence = calculate_coherence(contribution)
    provenance = _manual_cost_provenance(contribution.metadata, contribution.cost_amount)

    return _store_contribution(
        contributor_id=contribution.contributor_id,
        asset_id=contribution.asset_id,
        contributor_node_id=contributor_node["id"],
        asset_node_id=asset_node["id"],
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
async def get_contribution(contribution_id: UUID) -> Contribution:
    """Retrieve a single contribution record by its unique identifier."""
    from sqlalchemy import or_
    from app.models.graph import Edge
    from app.services.unified_db import session

    with session() as s:
        edges = s.query(Edge).filter(Edge.type == "contribution").all()
        for e in edges:
            props = e.properties or {}
            if props.get("contribution_id") == str(contribution_id):
                return _edge_to_contribution(e.to_dict())
    raise HTTPException(status_code=404, detail="Contribution not found")


@router.get("/contributions", response_model=PaginatedResponse[Contribution], summary="List contributions")
def list_contributions(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> PaginatedResponse[Contribution]:
    """List all contributions with pagination metadata."""
    from app.models.graph import Edge
    from app.services.unified_db import session

    with session() as s:
        q = s.query(Edge).filter(Edge.type == "contribution").order_by(Edge.created_at.desc())
        total = q.count()
        edges = q.offset(offset).limit(limit).all()
        items = [_edge_to_contribution(e.to_dict()) for e in edges]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/assets/{asset_id}/contributions",
    response_model=list[Contribution],
    summary="List contributions for an asset",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset_contributions(asset_id: UUID) -> list[Contribution]:
    """Get all contributions linked to a specific asset."""
    asset_node = _find_asset_node(asset_id)
    if not asset_node:
        raise HTTPException(status_code=404, detail="Asset not found")
    edges = graph_service.get_edges(asset_node["id"], direction="incoming", edge_type="contribution")
    return [_edge_to_contribution(e) for e in edges]


@router.get(
    "/contributors/{contributor_id}/contributions",
    response_model=list[Contribution],
    summary="List contributions by a contributor",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
async def get_contributor_contributions(contributor_id: UUID) -> list[Contribution]:
    """Get all contributions made by a specific contributor."""
    contributor_node = _find_contributor_node(contributor_id)
    if not contributor_node:
        raise HTTPException(status_code=404, detail="Contributor not found")
    edges = graph_service.get_edges(contributor_node["id"], direction="outgoing", edge_type="contribution")
    return [_edge_to_contribution(e) for e in edges]


# ── GitHub contributions ─────────────────────────────────────────


def calculate_coherence_from_github_metadata(metadata: dict) -> float:
    """Calculate coherence score from GitHub commit metadata."""
    score = 0.5
    files_changed = metadata.get("files_changed", 0)
    if files_changed > 0:
        score += 0.1
    lines_added = metadata.get("lines_added", 0)
    if lines_added > 0 and lines_added < 100:
        score += 0.2
    elif lines_added >= 100:
        score += 0.1
    return min(score, 1.0)


@router.post(
    "/contributions/github",
    response_model=Contribution,
    status_code=201,
    summary="Track GitHub contribution",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def track_github_contribution(payload: GitHubContribution) -> Contribution:
    """Track a contribution from a GitHub webhook. Auto-creates contributor and asset if they don't exist."""
    # Find or create contributor by email
    contributor_node = _find_contributor_by_email(payload.contributor_email)
    contributor_name = payload.contributor_email.split("@")[0]

    if not contributor_node:
        contrib = Contributor(type=ContributorType.HUMAN, name=contributor_name, email=payload.contributor_email)
        node_id = f"contributor:{contrib.name}"
        contributor_node = graph_service.create_node(
            id=node_id, type="contributor", name=contrib.name,
            description=f"HUMAN contributor",
            phase="water",
            properties={
                "contributor_type": "HUMAN",
                "email": payload.contributor_email,
                "legacy_id": str(contrib.id),
            },
        )
        contributor_legacy_id = contrib.id
    else:
        contributor_legacy_id = UUID(contributor_node.get("legacy_id", str(uuid4())))

    # Find or create asset for repository
    asset_node = _find_asset_by_name(payload.repository)

    if not asset_node:
        asset = Asset(type=AssetType.CODE, description=f"GitHub repository: {payload.repository}")
        node_id = f"asset:{asset.id}"
        asset_node = graph_service.create_node(
            id=node_id, type="asset", name=payload.repository[:80],
            description=f"GitHub repository: {payload.repository}",
            phase="ice",
            properties={
                "asset_type": "CODE",
                "total_cost": "0",
                "legacy_id": str(asset.id),
            },
        )
        asset_legacy_id = asset.id
    else:
        asset_legacy_id = UUID(asset_node.get("legacy_id", str(uuid4())))

    # Calculate coherence and cost
    coherence = calculate_coherence_from_github_metadata(payload.metadata)
    files_changed = payload.metadata.get("files_changed", 0)
    lines_added = payload.metadata.get("lines_added", 0)
    normalized_cost, provenance = estimate_commit_cost_with_provenance(
        files_changed=files_changed,
        lines_added=lines_added,
        submitted_cost=payload.cost_amount,
        metadata=payload.metadata,
    )

    return _store_contribution(
        contributor_id=contributor_legacy_id,
        asset_id=asset_legacy_id,
        contributor_node_id=contributor_node["id"],
        asset_node_id=asset_node["id"],
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
    by_idea: dict[str, list[dict]] = {}
    for rec in idea_records:
        by_idea.setdefault(rec["idea_id"], []).append(rec)
    return {
        "contributor_id": contributor_id,
        "ideas": by_idea,
    }
