from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post(
    "/assets",
    response_model=Asset,
    status_code=201,
    summary="Create asset",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def create_asset(asset: AssetCreate, store: GraphStore = Depends(get_store)) -> Asset:
    """Register a new tracked asset (code, docs, endpoint, etc.)."""
    asset_obj = Asset(**asset.model_dump())
    return store.create_asset(asset_obj)


@router.get(
    "/assets/{asset_id}",
    response_model=Asset,
    summary="Get asset by ID",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset(asset_id: UUID, store: GraphStore = Depends(get_store)) -> Asset:
    """Retrieve a single asset by its unique identifier."""
    asset = store.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get(
    "/assets",
    response_model=PaginatedResponse[Asset],
    summary="List assets",
)
async def list_assets(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    store: GraphStore = Depends(get_store),
) -> PaginatedResponse[Asset]:
    """List all tracked assets with pagination metadata."""
    all_items = store.list_assets(limit=limit + offset + 1)
    total = len(all_items)
    page = all_items[offset : offset + limit]
    return PaginatedResponse(items=page, total=total, limit=limit, offset=offset)
