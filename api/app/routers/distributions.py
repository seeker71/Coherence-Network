"""Distributions router — backed by graph_nodes + graph_edges."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.distribution import Distribution, DistributionCreate
from app.models.error import ErrorDetail
from app.services import graph_service
from app.services.distribution_engine import DistributionEngine

router = APIRouter()


@router.post(
    "/distributions",
    response_model=Distribution,
    status_code=201,
    responses={404: {"model": ErrorDetail}},
    summary="Trigger value distribution for an asset",
)
async def create_distribution(distribution: DistributionCreate) -> Distribution:
    """Trigger value distribution for an asset."""
    asset_node = graph_service.get_node(f"asset:{distribution.asset_id}")
    if not asset_node:
        # Search by legacy ID
        result = graph_service.list_nodes(type="asset", limit=500)
        asset_node = next(
            (n for n in result.get("items", []) if n.get("legacy_id") == str(distribution.asset_id)),
            None,
        )
    if not asset_node:
        raise HTTPException(status_code=404, detail="Asset not found")

    engine = DistributionEngine()
    return await engine.distribute(
        asset_id=distribution.asset_id,
        asset_node_id=asset_node["id"],
        value_amount=distribution.value_amount,
    )
