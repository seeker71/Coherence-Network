"""Federation API routes for cross-instance data exchange."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.federation import (
    FederatedInstance,
    FederatedPayload,
    FleetCapabilitySummary,
    FederationNodeHeartbeatRequest,
    FederationNodeHeartbeatResponse,
    FederationNodeRegisterRequest,
    FederationNodeRegisterResponse,
    FederationStrategyEffectivenessReportRequest,
    FederationStrategyEffectivenessReportResponse,
    FederationStrategyListResponse,
    FederationSyncResult,
    MeasurementListResponse,
    MeasurementPushRequest,
    MeasurementPushResponse,
    VALID_STRATEGY_TYPES,
    FederatedAggregationRequest,
    FederatedAggregationResponse,
    FederatedAggregationListResponse,
)
from app.services import federation_service

router = APIRouter()


@router.post("/federation/instances", response_model=FederatedInstance, status_code=201)
async def register_instance(instance: FederatedInstance) -> FederatedInstance:
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
async def receive_payload(payload: FederatedPayload) -> FederationSyncResult:
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


@router.post("/federation/nodes/{node_id}/heartbeat", response_model=FederationNodeHeartbeatResponse)
async def heartbeat_node(
    node_id: str,
    body: FederationNodeHeartbeatRequest,
    refresh_capabilities: bool = Query(default=False),
):
    """Refresh liveness for a previously registered node."""
    capabilities_payload = None
    if body.capabilities is not None:
        capabilities_payload = (
            body.capabilities.model_dump(mode="json")
            if hasattr(body.capabilities, "model_dump")
            else body.capabilities
        )
    result = federation_service.heartbeat_node(
        node_id,
        status=body.status,
        capabilities=capabilities_payload,
        refresh_capabilities=refresh_capabilities,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


@router.get("/federation/nodes")
async def list_nodes():
    """List all registered federation nodes."""
    return federation_service.list_nodes()


@router.get("/federation/nodes/capabilities", response_model=FleetCapabilitySummary)
async def get_fleet_capabilities():
    """Return aggregated fleet capability coverage."""
    return federation_service.get_fleet_capability_summary()


# ---------------------------------------------------------------------------
# Aggregated node stats (Spec 133)
# ---------------------------------------------------------------------------

@router.get("/federation/nodes/stats")
async def get_aggregated_node_stats(window_days: int | None = Query(default=None, ge=1, le=365)):
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
    result = federation_service.store_measurement_summaries(node_id, summaries_dicts)
    return MeasurementPushResponse(
        stored=result["stored"],
        node_id=node_id,
        duplicates_skipped=result["duplicates_skipped"],
        duplicates_replaced=result["duplicates_replaced"],
    )


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


@router.post(
    "/federation/strategies/{strategy_id}/effectiveness",
    response_model=FederationStrategyEffectivenessReportResponse,
    status_code=201,
)
async def report_strategy_effectiveness(
    strategy_id: int,
    body: FederationStrategyEffectivenessReportRequest,
):
    """Record whether acting on a strategy improved outcome metrics."""
    try:
        report = federation_service.record_strategy_effectiveness(strategy_id=strategy_id, report=body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FederationStrategyEffectivenessReportResponse(**report)


# ---------------------------------------------------------------------------
# Federated Instance Aggregation (Spec 143)
# ---------------------------------------------------------------------------

@router.post(
    "/federation/instances/{node_id}/aggregate",
    response_model=FederatedAggregationResponse,
    status_code=202,
)
async def post_federated_aggregation(node_id: str, body: FederatedAggregationRequest):
    """Submit partner instance aggregation payload for trust-gated merge."""
    if body.envelope.node_id != node_id:
        raise HTTPException(status_code=422, detail="node_id mismatch between path and envelope")
    
    try:
        result = federation_service.ingest_federated_aggregation(node_id, body.model_dump(mode="json"))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
        
    if result.get("status") == "duplicate":
        from fastapi.responses import JSONResponse
        return JSONResponse(content=result, status_code=409)
        
    return result


@router.get("/federation/aggregates", response_model=FederatedAggregationListResponse)
async def get_federated_aggregates(strategy_type: str | None = Query(None)):
    """Return merged federated aggregation results."""
    aggregates = federation_service.list_federated_aggregates(strategy_type=strategy_type)
    return {"aggregates": aggregates}


# ---------------------------------------------------------------------------
# Node message bus — lightweight inter-node communication
# ---------------------------------------------------------------------------

_msg_log = logging.getLogger("coherence.node_messages")

# In-memory message store (survives within process lifetime;
# production should move to DB — but this unblocks inter-node comms now)
_MESSAGE_STORE: list[dict[str, Any]] = []
_MAX_MESSAGES = 500


class NodeMessage(BaseModel):
    from_node: str
    to_node: str | None = None  # None = broadcast to all nodes
    type: str = "text"  # text, command, status_request, status_response
    payload: dict[str, Any] = {}
    text: str = ""


@router.post("/federation/nodes/{node_id}/messages", status_code=201)
async def send_message(node_id: str, body: NodeMessage):
    """Send a message from this node. Set to_node=null to broadcast."""
    msg = {
        "id": f"msg_{uuid4().hex[:12]}",
        "from_node": node_id,
        "to_node": body.to_node,
        "type": body.type,
        "payload": body.payload,
        "text": body.text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read_by": [],
    }
    _MESSAGE_STORE.append(msg)
    # Trim old messages
    while len(_MESSAGE_STORE) > _MAX_MESSAGES:
        _MESSAGE_STORE.pop(0)
    _msg_log.info("MSG %s → %s: [%s] %s", node_id, body.to_node or "ALL", body.type, body.text[:100])
    return msg


@router.get("/federation/nodes/{node_id}/messages")
async def get_messages(
    node_id: str,
    since: str | None = Query(None, description="ISO timestamp — only messages after this time"),
    unread_only: bool = Query(True, description="Only messages not yet read by this node"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get messages for this node (direct + broadcasts). Marks them as read."""
    results = []
    for msg in reversed(_MESSAGE_STORE):
        # Include if addressed to this node or broadcast (to_node is None)
        if msg["to_node"] is not None and msg["to_node"] != node_id:
            continue
        # Skip own messages
        if msg["from_node"] == node_id:
            continue
        # Filter by since
        if since and msg["timestamp"] < since:
            continue
        # Filter unread
        if unread_only and node_id in msg.get("read_by", []):
            continue
        results.append(msg)
        if len(results) >= limit:
            break

    # Mark as read
    msg_ids = {m["id"] for m in results}
    for msg in _MESSAGE_STORE:
        if msg["id"] in msg_ids and node_id not in msg.get("read_by", []):
            msg["read_by"].append(node_id)

    return {"node_id": node_id, "messages": results, "count": len(results)}


@router.post("/federation/broadcast", status_code=201)
async def broadcast_message(body: NodeMessage):
    """Broadcast a message to all nodes."""
    body.to_node = None
    msg = {
        "id": f"msg_{uuid4().hex[:12]}",
        "from_node": body.from_node,
        "to_node": None,
        "type": body.type,
        "payload": body.payload,
        "text": body.text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read_by": [],
    }
    _MESSAGE_STORE.append(msg)
    while len(_MESSAGE_STORE) > _MAX_MESSAGES:
        _MESSAGE_STORE.pop(0)
    _msg_log.info("BROADCAST from %s: [%s] %s", body.from_node, body.type, body.text[:100])
    return msg
