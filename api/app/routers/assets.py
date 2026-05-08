"""Assets router — backed by graph_nodes (type=asset)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from decimal import Decimal

# Stable namespace for deriving asset UUIDs from slug-shaped graph
# node ids. Resolver-minted and KB-seeded asset nodes carry slug ids
# like `asset:emc2-music-festival-2026-...`. Without a deterministic
# mapping, every list call would uuid4() a fresh id per node and
# every link from list -> detail would 404 on the next request.
# uuid5(ASSET_NS, node_id) gives the same node the same UUID forever;
# the detail endpoint re-derives it from each node id and walks until
# it matches.
ASSET_NS = uuid5(NAMESPACE_URL, "coherencycoin.com/asset")


def _stable_asset_id(node: dict) -> UUID:
    """Resolve a node to its stable asset UUID.

    Order of trust:
      1. The portion of `node["id"]` after the `asset:` prefix, if it
         parses as a UUID — covers nodes whose graph id is already
         `asset:<uuid>`.
      2. uuid5 derived from the full node id — deterministic, so the
         same slug always returns the same UUID.
    """
    raw = str(node.get("id", "")).removeprefix("asset:")
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return uuid5(ASSET_NS, str(node.get("id", "")))

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.asset import (
    Asset,
    AssetCreate,
    AssetRegistration,
    AssetRegistrationCreate,
    ConceptTag,
)
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service
from app.services.locale_projection import project, project_many, resolve_caller_lang

router = APIRouter()


def _node_to_registration(node: dict) -> AssetRegistration:
    """Convert a graph node carrying MIME-aware asset properties to
    an AssetRegistration model."""
    props = node
    concept_tags_raw = props.get("concept_tags", []) or []
    concept_tags = [
        ConceptTag(concept_id=t.get("concept_id"), weight=float(t.get("weight", 0)))
        for t in concept_tags_raw
    ]
    creation_cost = Decimal(str(props.get("creation_cost_cc", "0")))
    created_at_raw = props.get("created_at")
    if isinstance(created_at_raw, str):
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.now(timezone.utc)
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        created_at = datetime.now(timezone.utc)

    return AssetRegistration(
        id=node["id"],
        type=props.get("mime_type") or props.get("asset_type", ""),
        name=props.get("name", ""),
        description=props.get("description", ""),
        content_hash=props.get("content_hash", ""),
        arweave_tx=props.get("arweave_tx"),
        ipfs_cid=props.get("ipfs_cid"),
        concept_tags=concept_tags,
        creator_id=props.get("creator_id", ""),
        creation_cost_cc=creation_cost,
        metadata=props.get("metadata", {}) or {},
        created_at=created_at,
    )


def _node_to_asset(node: dict) -> Asset:
    """Convert a graph node to an Asset model.

    ``image_url`` lands on remote-resolved nodes (inspired-by minted
    content with og:image), ``file_path`` lands on locally-generated
    KB visuals served from /visuals/...; either one is enough to give
    the listing card a real thumbnail.

    Rich fields (name, canonical_url, creator_id, asin, slug, era,
    mime_type, content_hash, ipfs_cid, arweave_tx, etc.) are passed
    through unchanged when present on the node, so detail surfaces
    can render a title, an external source link, and the structured-
    data context that makes the surface trustworthy without a second
    round-trip to /api/graph/nodes."""
    image_url = node.get("image_url") or None
    file_path = node.get("file_path") or None

    def _str(key: str) -> str | None:
        value = node.get(key)
        return value if isinstance(value, str) and value else None

    def _int(key: str) -> int | None:
        value = node.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    return Asset(
        id=_stable_asset_id(node),
        type=node.get("asset_type", "CODE"),
        description=node.get("description", node.get("name", "")),
        total_cost=Decimal(str(node.get("total_cost", "0"))),
        image_url=image_url if isinstance(image_url, str) else None,
        file_path=file_path if isinstance(file_path, str) else None,
        node_id=_str("id"),
        name=_str("name"),
        canonical_url=_str("canonical_url"),
        slug=_str("slug"),
        creator_id=_str("creator_id"),
        creation_kind=_str("creation_kind"),
        asset_type=_str("asset_type"),
        mime_type=_str("mime_type"),
        content_hash=_str("content_hash"),
        ipfs_cid=_str("ipfs_cid"),
        arweave_tx=_str("arweave_tx"),
        asin=_str("asin"),
        isbn=_str("isbn"),
        runtime_length_min=_int("runtime_length_min"),
        era=_str("era"),
        company=_str("company"),
        title=_str("title"),
        location=_str("location"),
        substrate=_str("substrate"),
        when=_str("when"),
        language=_str("language"),
    )


@router.post(
    "/assets",
    response_model=Asset,
    status_code=201,
    summary="Create asset",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def create_asset(asset: AssetCreate) -> Asset:
    """Register a new tracked asset (code, docs, endpoint, etc.)."""
    asset_obj = Asset(**asset.model_dump())
    node_id = f"asset:{asset_obj.id}"
    graph_service.create_node(
        id=node_id, type="asset", name=(asset_obj.description or "")[:80],
        description=asset_obj.description or "",
        phase="ice",
        properties={
            "asset_type": asset_obj.type,
            "total_cost": str(asset_obj.total_cost),
        },
    )
    return asset_obj


@router.post(
    "/assets/register",
    response_model=AssetRegistration,
    status_code=201,
    summary="Register a MIME-typed asset with content provenance",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def register_asset(body: AssetRegistrationCreate) -> AssetRegistration:
    """Register an asset with full MIME type, content hash, storage
    references, concept tags, and format-specific metadata.

    Extends the legacy POST /api/assets — the legacy endpoint still
    accepts CODE/MODEL/CONTENT/DATA taxonomy for pipeline contributions.
    This endpoint supports arbitrary MIME types so a renderer can pair
    with the asset by type. See specs/asset-renderer-plugin.md R1.
    """
    registration_id = f"asset:{uuid4()}"
    now = datetime.now(timezone.utc)
    concept_tags_serializable = [
        {"concept_id": t.concept_id, "weight": t.weight}
        for t in body.concept_tags
    ]
    graph_service.create_node(
        id=registration_id,
        type="asset",
        name=body.name,
        description=body.description,
        phase="ice",
        properties={
            "mime_type": body.type,
            "name": body.name,
            "content_hash": body.content_hash,
            "arweave_tx": body.arweave_tx,
            "ipfs_cid": body.ipfs_cid,
            "concept_tags": concept_tags_serializable,
            "creator_id": body.creator_id,
            "creation_cost_cc": str(body.creation_cost_cc),
            "metadata": body.metadata,
            "created_at": now.isoformat(),
        },
    )
    return AssetRegistration(
        id=registration_id,
        type=body.type,
        name=body.name,
        description=body.description,
        content_hash=body.content_hash,
        arweave_tx=body.arweave_tx,
        ipfs_cid=body.ipfs_cid,
        concept_tags=body.concept_tags,
        creator_id=body.creator_id,
        creation_cost_cc=body.creation_cost_cc,
        metadata=body.metadata,
        created_at=now,
    )


@router.get(
    "/assets/{asset_id}/registration",
    response_model=AssetRegistration,
    summary="Get MIME-aware asset registration",
    responses={404: {"model": ErrorDetail, "description": "Asset registration not found"}},
)
async def get_asset_registration(asset_id: str) -> AssetRegistration:
    """Retrieve full registration (MIME type, concept tags, provenance, metadata)
    for an asset registered via POST /api/assets/register.
    """
    node_id = asset_id if asset_id.startswith("asset:") else f"asset:{asset_id}"
    node = graph_service.get_node(node_id)
    if not node or not node.get("mime_type"):
        raise HTTPException(status_code=404, detail="Asset registration not found")
    return _node_to_registration(node)


@router.get(
    "/assets/{asset_id}",
    response_model=Asset,
    summary="Get asset by ID",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset(
    asset_id: UUID,
    request: Request,
    lang: str | None = Query(None, description="Target language. Description renders in this locale when a view exists."),
) -> Asset:
    """Retrieve a single asset by its unique identifier.

    The lookup mirrors `_stable_asset_id`:
      1. Direct hit on `asset:<uuid>` — for nodes whose graph id is
         already `asset:<uuid>`.
      2. Walk all asset nodes and match the deterministic
         `_stable_asset_id(node)` — covers slug-shaped nodes minted
         by the resolver / KB seed.
    """
    node = graph_service.get_node(f"asset:{asset_id}")
    if not node:
        result = graph_service.list_nodes(type="asset", limit=1000)
        for n in result.get("items", []):
            if _stable_asset_id(n) == asset_id:
                node = n
                break
    if not node:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset = _node_to_asset(node)
    target_lang = resolve_caller_lang(request, lang)
    project(asset, "asset", str(asset.id), target_lang, title_field="description", body_field="description")
    return asset


@router.get(
    "/assets",
    response_model=PaginatedResponse[Asset],
    summary="List assets",
)
async def list_assets(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    lang: str | None = Query(None, description="Target language for descriptions."),
) -> PaginatedResponse[Asset]:
    """List all tracked assets with pagination metadata."""
    result = graph_service.list_nodes(type="asset", limit=limit, offset=offset)
    items = [_node_to_asset(n) for n in result.get("items", [])]
    target_lang = resolve_caller_lang(request, lang)
    if target_lang and target_lang != "en":
        for item in items:
            project(item, "asset", str(item.id), target_lang, title_field="description", body_field="description")
    return PaginatedResponse(items=items, total=result.get("total", len(items)), limit=limit, offset=offset)
