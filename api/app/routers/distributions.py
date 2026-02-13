from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.distribution import Distribution, DistributionCreate
from app.models.error import ErrorDetail
from app.services.distribution_engine import DistributionEngine

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post(
    "/distributions",
    response_model=Distribution,
    status_code=201,
    responses={404: {"model": ErrorDetail}},
)
async def create_distribution(distribution: DistributionCreate, store: GraphStore = Depends(get_store)) -> Distribution:
    """Trigger value distribution for an asset."""
    if not store.get_asset(distribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")

    engine = DistributionEngine(store)
    return await engine.distribute(asset_id=distribution.asset_id, value_amount=distribution.value_amount)
