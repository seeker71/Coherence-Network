"""Contributors router — backed by graph_nodes (type=contributor)."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middleware.auth import require_api_key
from app.models.belief import BeliefProfileResponse, BeliefProfileUpdate, BeliefResonanceResponse
from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import belief_service, graph_service

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
    from app.services.contributor_hygiene import is_test_contributor_email
    contrib = Contributor(**contributor.model_dump())
    if is_test_contributor_email(contrib.email):
        raise HTTPException(status_code=422, detail="Test email domains are not allowed for persistent contributors")
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


def _belief_payload(contributor_id: str, data: dict) -> BeliefProfileResponse:
    return BeliefProfileResponse(
        contributor_id=contributor_id,
        worldview=data["worldview"],
        axis_weights=data["axis_weights"],
        concept_weights=data["concept_weights"],
        updated_at=data.get("updated_at"),
    )


@router.get(
    "/contributors/{contributor_id}/beliefs/resonance",
    response_model=BeliefResonanceResponse,
    summary="Resonance between contributor beliefs and an idea",
)
def get_belief_resonance(
    contributor_id: str,
    idea_id: str = Query(..., min_length=1, description="Idea id to compare"),
) -> BeliefResonanceResponse:
    payload = belief_service.compute_resonance(contributor_id, idea_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Contributor or idea not found",
        )
    return BeliefResonanceResponse(**payload)


@router.get(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfileResponse,
    summary="Get contributor belief profile",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_beliefs(contributor_id: str) -> BeliefProfileResponse:
    data = belief_service.get_belief_profile_dict(contributor_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return _belief_payload(contributor_id, data)


@router.patch(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfileResponse,
    summary="Update contributor belief profile",
    responses={401: {"model": ErrorDetail}, 404: {"model": ErrorDetail}},
)
def patch_contributor_beliefs(
    contributor_id: str,
    body: BeliefProfileUpdate,
    _key: str = Depends(require_api_key),
) -> BeliefProfileResponse:
    dump = body.model_dump(exclude_unset=True, exclude_none=True)
    if not dump:
        data = belief_service.get_belief_profile_dict(contributor_id)
    else:
        data = belief_service.save_belief_profile(contributor_id, dump)
    if data is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return _belief_payload(contributor_id, data)
