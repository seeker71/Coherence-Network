"""Contributors router — backed by graph_nodes (type=contributor)."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service, contributor_service

router = APIRouter()


class GraduateIn(BaseModel):
    """Soft-identity graduation request.

    A visitor who wants to invite/react/voice can graduate to a real
    contributor node without a signup form — just a display name + a
    per-device fingerprint. No email, no password, no public key. The
    same frequency as the voice-posting auto-graduation in
    concept_voice_service.
    """
    author_name: str
    device_fingerprint: str | None = None
    invited_by: str | None = None


class GraduateOut(BaseModel):
    contributor_id: str
    created: bool
    invited_by: str | None = None


@router.post(
    "/contributors/graduate",
    response_model=GraduateOut,
    summary="Soft-identity graduation — mint a contributor node from name + fingerprint",
)
def graduate_contributor(body: GraduateIn) -> GraduateOut:
    """Create (or return) a contributor node keyed by name + fingerprint.

    Idempotent: calling twice with the same name+fingerprint returns
    the existing node. When ``invited_by`` is supplied and the
    contributor is new, we record the invite-chain link on the
    contributor's graph properties so the lineage is preserved in the
    database, not just the inviter's localStorage.
    """
    name = (body.author_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="author_name is required")
    fp = (body.device_fingerprint or uuid4().hex[:8]).strip()[:24]
    safe_name = "".join(c for c in name.lower() if c.isalnum() or c in "-_") or "friend"
    safe_fp = "".join(c for c in fp.lower() if c.isalnum() or c in "-_") or uuid4().hex[:8]
    candidate_id = f"{safe_name}-{safe_fp}"[:64]

    existing = graph_service.get_node(f"contributor:{candidate_id}")
    if existing:
        return GraduateOut(
            contributor_id=candidate_id,
            created=False,
            invited_by=(existing.get("invited_by") if isinstance(existing, dict) else None) or None,
        )

    # Create, and record invited_by attribution on the properties so the
    # chain is queryable server-side.
    invited_by = (body.invited_by or "").strip() or None
    node_id = f"contributor:{candidate_id}"
    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=candidate_id,
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"{candidate_id}@coherence.network",
            "author_display_name": name,
            "invited_by": invited_by,
        },
    )
    return GraduateOut(
        contributor_id=candidate_id,
        created=True,
        invited_by=invited_by,
    )


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
    # Coerce unknown contributor_type values to SYSTEM so a stray label in
    # the graph never blows up the endpoint for every caller.
    raw_type = str(node.get("contributor_type") or "HUMAN").strip().upper()
    try:
        from app.models.contributor import ContributorType
        contrib_type = ContributorType(raw_type)
    except ValueError:
        contrib_type = ContributorType.SYSTEM
    # ``claimed`` defaults to True for living contributors — only
    # placeholder identities minted by the inspired-by resolver carry
    # ``claimed: False``. The directory uses this to render the waiting
    # distinctly from the walked-in.
    claimed = bool(node.get("claimed", True))
    return Contributor(
        id=cid,
        name=node.get("name", ""),
        type=contrib_type,
        email=email,
        wallet_address=node.get("wallet_address") or None,
        hourly_rate=float(node["hourly_rate"]) if node.get("hourly_rate") else None,
        locale=node.get("locale") or None,
        claimed=claimed,
        canonical_url=node.get("canonical_url") or None,
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
    "/contributors/{contributor_id}/spend",
    summary="Get contributor spend metrics (daily/monthly)",
    tags=["contributors"],
)
def get_contributor_spend(contributor_id: str) -> dict:
    """Return CC spent in the last 24h and last 30 days for budgeting."""
    from app.services import contribution_ledger_service
    return contribution_ledger_service.get_spend_metrics(contributor_id)


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
