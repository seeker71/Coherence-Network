"""Federation API routes for cross-instance data exchange."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middleware.auth import require_api_key
from app.models.federation import (
    FederatedInstance,
    FederatedPayload,
    FederationNodeHeartbeatRequest,
    FederationNodeRegisterRequest,
    FederationNodeRegisterResponse,
    FederationStrategyListResponse,
    FederationSyncResult,
    MeasurementListResponse,
    MeasurementPushRequest,
    MeasurementPushResponse,
    VALID_STRATEGY_TYPES,
)
from app.services import federation_service

router = APIRouter()


@router.post("/federation/instances", response_model=FederatedInstance, status_code=201)
async def register_instance(instance: FederatedInstance, _key: str = Depends(require_api_key)) -> FederatedInstance:
    """Register a remote Coherence instance."""
    return federation_service.register_instance(instance)


@router.get("/federation/instances", response_model=list[FederatedInstance])
async def list_instances() -> list[FederatedInstance]:
    """List all registered remote instances."""
    return federation_service.list_instances()


@router.get("/federation/instances/{instance_id}", response_model=FederatedInstance)
async def get_instance(instance_id: str) -> FederatedInstance:
    """Get a single registered instance by ID."""
    found = federation_service.get_instance(instance_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return found


@router.post("/federation/sync", response_model=FederationSyncResult)
async def receive_payload(payload: FederatedPayload, _key: str = Depends(require_api_key)) -> FederationSyncResult:
    """Receive a federated payload from a remote instance."""
    return federation_service.receive_payload(payload)


@router.get("/federation/sync/history")
async def sync_history(limit: int = Query(200, ge=1, le=1000)) -> list[dict]:
    """List past sync operations."""
    return federation_service.list_sync_history(limit=limit)


# ---------------------------------------------------------------------------
# Node registration / heartbeat (Spec 132)
# ---------------------------------------------------------------------------

@router.post("/federation/nodes", response_model=FederationNodeRegisterResponse)
async def register_node(body: FederationNodeRegisterRequest):
    """Register or update a federation node."""
    from fastapi.responses import JSONResponse
    resp, created = federation_service.register_or_update_node(body)
    status_code = 201 if created else 200
    return JSONResponse(content=resp.model_dump(mode="json"), status_code=status_code)


@router.post("/federation/nodes/{node_id}/heartbeat")
async def heartbeat_node(node_id: str, body: FederationNodeHeartbeatRequest):
    """Refresh liveness for a previously registered node."""
    result = federation_service.heartbeat_node(node_id, status=body.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


@router.get("/federation/nodes")
async def list_nodes():
    """List all registered federation nodes."""
    return federation_service.list_nodes()


# ---------------------------------------------------------------------------
# Aggregated node stats (Spec 133)
# ---------------------------------------------------------------------------

@router.get("/federation/nodes/stats")
async def get_aggregated_node_stats(window_days: int = Query(7, ge=1, le=365)):
    """Return aggregated provider stats across all federation nodes."""
    return federation_service.get_aggregated_node_stats(window_days=window_days)


# ---------------------------------------------------------------------------
# Measurement summaries (Spec 131)
# ---------------------------------------------------------------------------

@router.post(
    "/federation/nodes/{node_id}/measurements",
    response_model=MeasurementPushResponse,
    status_code=201,
)
async def post_measurement_summaries(node_id: str, body: MeasurementPushRequest):
    """Accept a batch of measurement summaries from a node."""
    for sm in body.summaries:
        if sm.node_id != node_id:
            raise HTTPException(
                status_code=422,
                detail=f"node_id mismatch: path='{node_id}', summary='{sm.node_id}'",
            )
        if sm.sample_count != sm.successes + sm.failures:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"sample_count mismatch: sample_count={sm.sample_count} "
                    f"!= successes({sm.successes}) + failures({sm.failures})"
                ),
            )
    summaries_dicts = [s.model_dump(mode="json") for s in body.summaries]
    stored = federation_service.store_measurement_summaries(node_id, summaries_dicts)
    return MeasurementPushResponse(stored=stored, node_id=node_id)


@router.get(
    "/federation/nodes/{node_id}/measurements",
    response_model=MeasurementListResponse,
)
async def get_measurement_summaries(
    node_id: str,
    decision_point: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return stored measurement summaries for a node."""
    rows, total = federation_service.list_measurement_summaries(
        node_id=node_id,
        decision_point=decision_point,
        limit=limit,
        offset=offset,
    )
    return MeasurementListResponse(
        node_id=node_id,
        summaries=rows,
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Strategy broadcasts (Spec 134)
# ---------------------------------------------------------------------------

@router.get(
    "/federation/strategies",
    response_model=FederationStrategyListResponse,
)
async def get_strategies(
    strategy_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return active (non-expired) federation strategy broadcasts."""
    if strategy_type is not None and strategy_type not in VALID_STRATEGY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                "invalid strategy_type; expected one of: "
                "provider_recommendation, prompt_variant_winner, provider_warning"
            ),
        )
    rows, total = federation_service.list_active_strategies(
        strategy_type=strategy_type,
        limit=limit,
        offset=offset,
    )
    return FederationStrategyListResponse(
        strategies=rows,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/federation/strategies/compute", status_code=200)
async def compute_strategies():
    """Trigger computation of new strategy broadcasts from current data."""
    new_strategies = federation_service.compute_and_store_strategies()
    return {"computed": len(new_strategies), "strategies": new_strategies}
