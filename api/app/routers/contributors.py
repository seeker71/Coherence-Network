"""Contributors router — backed by graph_nodes (type=contributor)."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query

from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service

router = APIRouter()


def _node_to_contributor(node: dict) -> Contributor:
    """Convert a graph node to a Contributor model."""
    legacy_id = node.get("legacy_id", "")
    try:
        cid = UUID(legacy_id) if legacy_id and "-" in legacy_id else uuid4()
    except (ValueError, AttributeError):
        cid = uuid4()
    email = node.get("email") or ""
    # Contributor model requires a valid email — use a placeholder if missing
    if not email or "@" not in email:
        email = f"{node.get('name', 'unknown')}@coherence.network"
    return Contributor(
        id=cid,
        name=node.get("name", ""),
        type=node.get("contributor_type") or "HUMAN",
        email=email,
        wallet_address=node.get("wallet_address") or None,
        hourly_rate=float(node["hourly_rate"]) if node.get("hourly_rate") else None,
    )


@router.post(
    "/contributors",
    response_model=Contributor,
    status_code=201,
    summary="Create contributor",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
def create_contributor(contributor: ContributorCreate) -> Contributor:
    """Register a new contributor (human or system) in the network."""
    contrib = Contributor(**contributor.model_dump())
    node_id = f"contributor:{contrib.name}"
    existing = graph_service.get_node(node_id)
    if existing:
        raise HTTPException(status_code=422, detail=f"Contributor '{contrib.name}' already exists")
    graph_service.create_node(
        id=node_id, type="contributor", name=contrib.name,
        description=f"{contrib.type or 'HUMAN'} contributor",
        phase="water",
        properties={
            "contributor_type": contrib.type,
            "email": contrib.email,
            "wallet_address": contrib.wallet_address,
            "hourly_rate": float(contrib.hourly_rate) if contrib.hourly_rate else None,
            "legacy_id": str(contrib.id),
        },
    )
    return contrib


@router.get(
    "/contributors/{contributor_id}",
    response_model=Contributor,
    summary="Get contributor by ID",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor(contributor_id: str) -> Contributor:
    """Retrieve a single contributor by name or UUID."""
    # Try by name first, then by UUID
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if not node:
        # Search by legacy UUID
        result = graph_service.list_nodes(type="contributor", limit=500)
        for n in result.get("items", []):
            if n.get("legacy_id") == str(contributor_id) or n.get("name") == contributor_id:
                node = n
                break
    if not node:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return _node_to_contributor(node)


@router.get(
    "/contributors",
    response_model=PaginatedResponse[Contributor],
    summary="List contributors",
)
def list_contributors(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> PaginatedResponse[Contributor]:
    """List contributors with pagination metadata."""
    result = graph_service.list_nodes(type="contributor", limit=limit, offset=offset)
    items = [_node_to_contributor(n) for n in result.get("items", [])]
    return PaginatedResponse(items=items, total=result.get("total", len(items)), limit=limit, offset=offset)
