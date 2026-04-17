"""Assets router — backed by graph_nodes (type=asset)."""
from __future__ import annotations

from uuid import UUID, uuid4
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.asset import Asset, AssetCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service
from app.services.locale_projection import project, project_many, resolve_caller_lang

router = APIRouter()


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
