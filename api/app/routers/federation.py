"""Federation API routes for cross-instance data exchange."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.middleware.traceability import traces_to

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
from app.services import openclaw_node_bridge_service

router = APIRouter()


@router.post("/federation/instances", response_model=FederatedInstance, status_code=201, summary="Register a remote Coherence instance")
async def register_instance(instance: FederatedInstance) -> FederatedInstance:
    """Register a remote Coherence instance."""
    return federation_service.register_instance(instance)


@router.get("/federation/instances", response_model=list[FederatedInstance], summary="List all registered remote instances")
async def list_instances() -> list[FederatedInstance]:
    """List all registered remote instances."""
    return federation_service.list_instances()


@router.get("/federation/instances/{instance_id}", response_model=FederatedInstance, summary="Get a single registered instance by ID")
async def get_instance(instance_id: str) -> FederatedInstance:
    """Get a single registered instance by ID."""
    found = federation_service.get_instance(instance_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return found


@router.post("/federation/sync", response_model=FederationSyncResult, summary="Receive a federated payload from a remote instance")
async def receive_payload(payload: FederatedPayload) -> FederationSyncResult:
    """Receive a federated payload from a remote instance."""
    return federation_service.receive_payload(payload)


@router.get("/federation/sync/history", summary="List past sync operations")
async def sync_history(limit: int = Query(200, ge=1, le=1000)) -> list[dict]:
    """List past sync operations."""
    return federation_service.list_sync_history(limit=limit)


# ---------------------------------------------------------------------------
# Node registration / heartbeat (Spec 132)
# ---------------------------------------------------------------------------

@router.post("/federation/nodes", response_model=FederationNodeRegisterResponse, summary="Register or update a federation node")
@traces_to(spec="132", idea="federation-node-identity", description="Register a federation node")
async def register_node(body: FederationNodeRegisterRequest):
    """Register or update a federation node."""
    from fastapi.responses import JSONResponse
    resp, created = federation_service.register_or_update_node(body)
    status_code = 201 if created else 200
    return JSONResponse(content=resp.model_dump(mode="json"), status_code=status_code)


@router.post("/federation/nodes/{node_id}/heartbeat", response_model=FederationNodeHeartbeatResponse, summary="Refresh liveness for a previously registered node")
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
        git_sha=body.git_sha,
        system_metrics=body.system_metrics,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


@router.get("/federation/nodes", summary="List all registered federation nodes")
async def list_nodes():
    """List all registered federation nodes."""
    return federation_service.list_nodes()


@router.delete("/federation/nodes/{node_id}", status_code=204, summary="Remove a stale or duplicate federation node")
async def delete_node(node_id: str):
    """Remove a stale or duplicate federation node."""
    ok = federation_service.delete_node(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return None


@router.get("/federation/nodes/capabilities", response_model=FleetCapabilitySummary, summary="Return aggregated fleet capability coverage")
async def get_fleet_capabilities():
    """Return aggregated fleet capability coverage."""
    return federation_service.get_fleet_capability_summary()


# ---------------------------------------------------------------------------
# Aggregated node stats (Spec 133)
# ---------------------------------------------------------------------------

@router.get("/federation/nodes/stats", summary="Return aggregated provider stats across all federation nodes")
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
    summary="Accept a batch of measurement summaries from a node",
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
    summary="Return stored measurement summaries for a node",
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
    summary="Return active (non-expired) federation strategy broadcasts",
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


@router.post("/federation/strategies/compute", status_code=200, summary="Trigger computation of new strategy broadcasts from current data")
async def compute_strategies():
    """Trigger computation of new strategy broadcasts from current data."""
    new_strategies = federation_service.compute_and_store_strategies()
    return {"computed": len(new_strategies), "strategies": new_strategies}


@router.post(
    "/federation/strategies/{strategy_id}/effectiveness",
    response_model=FederationStrategyEffectivenessReportResponse,
    status_code=201,
    summary="Record whether acting on a strategy improved outcome metrics",
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
    summary="Submit partner instance aggregation payload for trust-gated merge",
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


@router.get("/federation/aggregates", response_model=FederatedAggregationListResponse, summary="Return merged federated aggregation results")
async def get_federated_aggregates(strategy_type: str | None = Query(None)):
    """Return merged federated aggregation results."""
    aggregates = federation_service.list_federated_aggregates(strategy_type=strategy_type)
    return {"aggregates": aggregates}


# ---------------------------------------------------------------------------
# Node message bus — lightweight inter-node communication
# ---------------------------------------------------------------------------

_msg_log = logging.getLogger("coherence.node_messages")

_MAX_MESSAGES = 500


class NodeMessage(BaseModel):
    from_node: str
    to_node: str | None = None  # None = broadcast to all nodes
    type: str = "text"  # text, command, status_request, status_response
    payload: dict[str, Any] = {}
    text: str = ""


def _store_message(msg_dict: dict[str, Any]) -> dict[str, Any]:
    """Persist a message to PostgreSQL. Falls back to fire-and-forget on DB error."""
    try:
        from app.services.federation_service import NodeMessageRecord
        from app.services import unified_db as _udb

        with _udb.session() as session:
            record = NodeMessageRecord(
                id=msg_dict["id"],
                from_node=msg_dict["from_node"],
                to_node=msg_dict.get("to_node"),
                type=msg_dict.get("type", "text"),
                text=msg_dict.get("text", ""),
                payload_json=json.dumps(msg_dict.get("payload", {})),
                timestamp=msg_dict["timestamp"],
                read_by_json="[]",
            )
            session.add(record)
            session.commit()
    except Exception as e:
        _msg_log.warning("Failed to persist message %s: %s", msg_dict.get("id"), e)
    return msg_dict


def _message_record_to_dict(rec) -> dict[str, Any]:
    read_by = json.loads(rec.read_by_json) if rec.read_by_json else []
    return {
        "id": rec.id,
        "from_node": rec.from_node,
        "to_node": rec.to_node,
        "type": rec.type,
        "text": rec.text,
        "payload": json.loads(rec.payload_json) if rec.payload_json else {},
        "timestamp": rec.timestamp,
        "read_by": read_by,
    }


def _query_messages(
    node_id: str,
    since: str | None = None,
    unread_only: bool = True,
    limit: int = 50,
    include_self: bool = False,
) -> list[dict[str, Any]]:
    """Query messages from PostgreSQL for a specific node."""
    try:
        from app.services.federation_service import NodeMessageRecord
        from app.services import unified_db as _udb
        from sqlalchemy import or_

        with _udb.session() as session:
            q = session.query(NodeMessageRecord).filter(
                or_(
                    NodeMessageRecord.to_node == node_id,
                    NodeMessageRecord.to_node.is_(None),  # broadcasts
                )
            )
            if not include_self:
                q = q.filter(NodeMessageRecord.from_node != node_id)
            if since:
                q = q.filter(NodeMessageRecord.timestamp > since)
            q = q.order_by(NodeMessageRecord.timestamp.desc()).limit(limit)

            results = []
            for rec in q.all():
                row = _message_record_to_dict(rec)
                if unread_only and node_id in row["read_by"]:
                    continue
                results.append(row)
            return results
    except Exception as e:
        _msg_log.warning("Failed to query messages for %s: %s", node_id, e)
        return []


def _get_message(message_id: str) -> dict[str, Any] | None:
    try:
        from app.services.federation_service import NodeMessageRecord
        from app.services import unified_db as _udb

        with _udb.session() as session:
            rec = session.query(NodeMessageRecord).filter(NodeMessageRecord.id == message_id).first()
            return _message_record_to_dict(rec) if rec else None
    except Exception as e:
        _msg_log.warning("Failed to get message %s: %s", message_id, e)
        return None


def _mark_messages_read(node_id: str, msg_ids: set[str]) -> None:
    """Mark messages as read by this node in PostgreSQL."""
    if not msg_ids:
        return
    try:
        from app.services.federation_service import NodeMessageRecord
        from app.services import unified_db as _udb

        with _udb.session() as session:
            for rec in session.query(NodeMessageRecord).filter(NodeMessageRecord.id.in_(msg_ids)):
                read_by = json.loads(rec.read_by_json) if rec.read_by_json else []
                if node_id not in read_by:
                    read_by.append(node_id)
                    rec.read_by_json = json.dumps(read_by)
            session.commit()
    except Exception as e:
        _msg_log.warning("Failed to mark messages read for %s: %s", node_id, e)


@router.post("/federation/nodes/{node_id}/messages", status_code=201, summary="Send a message from this node. Set to_node=null to broadcast")
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
    _store_message(msg)
    _msg_log.info("MSG %s → %s: [%s] %s", node_id, body.to_node or "ALL", body.type, body.text[:100])
    # Push to SSE subscribers
    _notify_sse_subscribers(body.to_node, msg)
    openclaw_node_bridge_service.notify_openclaw_bridge_subscribers(body.to_node, msg)
    return msg


@router.get("/federation/nodes/{node_id}/messages", summary="Get messages for this node (direct + broadcasts). Marks them as read")
async def get_messages(
    node_id: str,
    since: str | None = Query(None, description="ISO timestamp — only messages after this time"),
    unread_only: bool = Query(True, description="Only messages not yet read by this node"),
    limit: int = Query(50, ge=1, le=200),
    include_self: bool = Query(False, description="Include messages sent by this node"),
):
    """Get messages for this node (direct + broadcasts). Marks them as read."""
    results = _query_messages(
        node_id,
        since=since,
        unread_only=unread_only,
        limit=limit,
        include_self=include_self,
    )

    # Mark as read
    msg_ids = {m["id"] for m in results}
    _mark_messages_read(node_id, msg_ids)

    return {"node_id": node_id, "messages": results, "count": len(results)}


@router.get("/federation/messages/{message_id}", summary="Read a federation node message by id")
async def get_message_by_id(message_id: str):
    """Read a federation node message by id."""
    msg = _get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.post("/federation/broadcast", status_code=201, summary="Broadcast a message to all nodes")
async def broadcast_message(body: NodeMessage):
    """Broadcast a message to all nodes."""
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
    _store_message(msg)
    _msg_log.info("BROADCAST from %s: [%s] %s", body.from_node, body.type, body.text[:100])
    # Notify SSE subscribers
    _notify_sse_subscribers(None, msg)
    openclaw_node_bridge_service.notify_openclaw_bridge_subscribers(None, msg)
    return msg


# ── SSE: real-time push notifications for connected nodes ────────────

import asyncio
import queue
import threading
from fastapi.responses import StreamingResponse

# In-memory subscriber queues: node_id → list[queue.Queue]
_sse_subscribers: dict[str, list[queue.Queue]] = {}
_sse_lock = threading.Lock()


def _notify_sse_subscribers(target_node_id: str | None, event: dict) -> None:
    """Push an event to SSE subscribers. None = broadcast to all."""
    targets = []
    if target_node_id:
        targets = _sse_subscribers.get(target_node_id, [])
    else:
        # Broadcast to all subscribers
        for queues in _sse_subscribers.values():
            targets.extend(queues)

    for q in targets:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass  # Drop if subscriber is too slow


@router.get("/federation/nodes/{node_id}/stream", summary="SSE stream for a node. Pushes: messages, deploys, task events, status changes")
async def node_event_stream(node_id: str):
    """SSE stream for a node. Pushes: messages, deploys, task events, status changes.

    Connect with:
      curl -N https://api.coherencycoin.com/api/federation/nodes/{node_id}/stream

    Events are JSON objects with 'event_type' and 'data' fields.
    The stream stays open until the client disconnects.
    """
    subscriber_queue: queue.Queue = queue.Queue(maxsize=100)

    with _sse_lock:
        if node_id not in _sse_subscribers:
            _sse_subscribers[node_id] = []
        _sse_subscribers[node_id].append(subscriber_queue)

    def event_generator():
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'event_type': 'connected', 'node_id': node_id})}\n\n"

            deadline = time.time() + 2.0
            delivered_ids: set[str] = set()
            delivered_any = False
            while time.time() < deadline:
                try:
                    event = subscriber_queue.get(timeout=0.1)
                    event_id = str(event.get("id") or "")
                    if event_id:
                        delivered_ids.add(event_id)
                    delivered_any = True
                    yield f"data: {json.dumps(event)}\n\n"
                    while True:
                        event = subscriber_queue.get_nowait()
                        event_id = str(event.get("id") or "")
                        if event_id:
                            delivered_ids.add(event_id)
                        yield f"data: {json.dumps(event)}\n\n"
                    break
                except queue.Empty:
                    unread = _query_messages(node_id, unread_only=True, limit=50)
                    fresh = [msg for msg in unread if str(msg.get("id") or "") not in delivered_ids]
                    if fresh:
                        msg_ids = {str(msg.get("id") or "") for msg in fresh if str(msg.get("id") or "")}
                        if msg_ids:
                            _mark_messages_read(node_id, msg_ids)
                        delivered_any = True
                        for msg in fresh:
                            event_id = str(msg.get("id") or "")
                            if event_id:
                                delivered_ids.add(event_id)
                            yield f"data: {json.dumps(msg)}\n\n"
                        break
            if not delivered_any:
                yield ": keepalive\n\n"
        finally:
            # Clean up subscriber
            with _sse_lock:
                if node_id in _sse_subscribers:
                    try:
                        _sse_subscribers[node_id].remove(subscriber_queue)
                    except ValueError:
                        pass
                    if not _sse_subscribers[node_id]:
                        del _sse_subscribers[node_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Diagnostic pub/sub channel ──────────────────────────────────────

# Separate from message SSE — diagnostic events are high-frequency and
# only delivered to subscribers who explicitly opt in.
_diag_subscribers: dict[str, list[asyncio.Queue]] = {}  # node_id → queues
_diag_lock = asyncio.Lock()


@router.post("/federation/nodes/{node_id}/diag", status_code=201, summary="Publish a diagnostic event from a node. High-frequency, ephemeral")
async def publish_diagnostic(node_id: str, body: dict = {}):
    """Publish a diagnostic event from a node. High-frequency, ephemeral.

    Events are NOT persisted — only delivered to active subscribers.
    """
    event = {
        "node_id": node_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **body,
    }

    # Push to subscribers of this specific node
    for q in _diag_subscribers.get(node_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

    # Also push to wildcard subscribers (listening to all nodes)
    for q in _diag_subscribers.get("*", []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

    return {"ok": True}


@router.get("/federation/nodes/{node_id}/diag/stream", summary="SSE stream for diagnostic events from a node. Use node_id='*' for all nodes")
async def subscribe_diagnostics(node_id: str):
    """SSE stream for diagnostic events from a node. Use node_id='*' for all nodes.

    Connect: curl -N https://api.coherencycoin.com/api/federation/nodes/*/diag/stream
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    async with _diag_lock:
        if node_id not in _diag_subscribers:
            _diag_subscribers[node_id] = []
        _diag_subscribers[node_id].append(queue)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'event_type': 'subscribed', 'node_id': node_id})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with _diag_lock:
                if node_id in _diag_subscribers:
                    try:
                        _diag_subscribers[node_id].remove(queue)
                    except ValueError:
                        pass
                    if not _diag_subscribers[node_id]:
                        del _diag_subscribers[node_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
