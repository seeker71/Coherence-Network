from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.distribution import Distribution, DistributionCreate
from app.models.error import ErrorDetail
from app.services.distribution_engine import DistributionEngine
from app.services.distribution_settlement_service import DistributionSettlementService

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
    settlement_service = DistributionSettlementService(store)

    computed = await engine.distribute(asset_id=distribution.asset_id, value_amount=distribution.value_amount)
    settled = await settlement_service.settle(computed)
    return store.create_distribution(settled)


@router.get(
    "/distributions/{distribution_id}",
    response_model=Distribution,
    responses={404: {"model": ErrorDetail}},
)
async def get_distribution(distribution_id: UUID, store: GraphStore = Depends(get_store)) -> Distribution:
    distribution = store.get_distribution(distribution_id)
    if not distribution:
        raise HTTPException(status_code=404, detail="Distribution not found")
    return distribution


@router.get("/distributions", response_model=list[Distribution])
async def list_distributions(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Distribution]:
    return store.list_distributions(limit=limit)
