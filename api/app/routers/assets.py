from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post("/assets", response_model=Asset, status_code=201)
async def create_asset(asset: AssetCreate, store: GraphStore = Depends(get_store)) -> Asset:
    """Create a new asset."""
    asset_obj = Asset(**asset.model_dump())
    return store.create_asset(asset_obj)


@router.get(
    "/assets/{asset_id}",
    response_model=Asset,
    responses={404: {"model": ErrorDetail}},
)
async def get_asset(asset_id: UUID, store: GraphStore = Depends(get_store)) -> Asset:
    """Get asset by ID."""
    asset = store.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/assets", response_model=list[Asset])
async def list_assets(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Asset]:
    """List all assets."""
    return store.list_assets(limit=limit)
