"""Assets router — backed by graph_nodes (type=asset)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from decimal import Decimal

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
    """Convert a graph node to an Asset model."""
    legacy_id = node.get("legacy_id", node["id"].replace("asset:", ""))
    try:
        asset_id = UUID(legacy_id)
    except (ValueError, AttributeError):
        asset_id = uuid4()
    return Asset(
        id=asset_id,
        type=node.get("asset_type", "CODE"),
        description=node.get("description", node.get("name", "")),
        total_cost=Decimal(str(node.get("total_cost", "0"))),
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
            "legacy_id": str(asset_obj.id),
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
    """Retrieve a single asset by its unique identifier."""
    node = graph_service.get_node(f"asset:{asset_id}")
    if not node:
        # Search by legacy ID
        result = graph_service.list_nodes(type="asset", limit=500)
        for n in result.get("items", []):
            if n.get("legacy_id") == str(asset_id):
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
