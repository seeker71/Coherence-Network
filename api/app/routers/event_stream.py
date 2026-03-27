"""WebSocket pub/sub and HTTP publish for the cross-service event stream."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.models.event_stream import EventStreamPublish, EventStreamPublishResponse
from app.services import event_stream_service as es

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_event_types(raw: str | None) -> frozenset[str] | None:
    if not raw or not str(raw).strip():
        return None
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return None
    return frozenset(parts)


@router.websocket("/events/stream")
async def event_stream_socket(
    websocket: WebSocket,
    event_types: str | None = Query(None, description="Comma-separated event_type filter"),
    entity: str | None = Query(None, max_length=128),
    entity_id: str | None = Query(None, max_length=256),
    token: str | None = Query(None, description="Must match COHERENCE_EVENT_STREAM_TOKEN when set"),
) -> None:
    if not es.stream_token_ok(token):
        await websocket.close(code=1008, reason="event stream token required or invalid")
        return

    await websocket.accept()
    ft = _parse_event_types(event_types)
    ent = entity.strip() if entity else None
    eid = entity_id.strip() if entity_id else None
    queue = await es.register_subscriber(event_types=ft, entity=ent, entity_id=eid)

    hello = es.envelope(
        "connected",
        "event_stream",
        None,
        {"schema": es.SCHEMA, "filters": {"event_types": list(ft) if ft else None, "entity": ent, "entity_id": eid}},
    )
    await websocket.send_text(es.json_dumps(hello))

    async def pump_out() -> None:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(es.json_dumps(event))
            except asyncio.TimeoutError:
                hb = es.envelope("heartbeat", "event_stream", None, {})
                await websocket.send_text(es.json_dumps(hb))
            except (WebSocketDisconnect, OSError) as exc:
                logger.debug("event_stream pump end: %s", exc)
                break

    pump = asyncio.create_task(pump_out())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                body: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if body.get("type") == "ping":
                await websocket.send_text(es.json_dumps({"type": "pong", "schema": es.SCHEMA}))
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        try:
            await pump
        except asyncio.CancelledError:
            pass
        await es.unregister_subscriber(queue)


@router.post("/events/publish", response_model=EventStreamPublishResponse, status_code=201)
async def publish_event(
    payload: EventStreamPublish,
    x_event_stream_token: str | None = Header(None, alias="X-Event-Stream-Token"),
) -> EventStreamPublishResponse:
    if not es.publish_token_ok(x_event_stream_token):
        raise HTTPException(status_code=401, detail="event stream publish token required or invalid")

    msg = es.publish(
        payload.event_type,
        payload.entity,
        payload.entity_id,
        payload.data,
    )
    return EventStreamPublishResponse(
        v=msg["v"],
        schema=msg["schema"],
        id=msg["id"],
        event_type=msg["event_type"],
        entity=msg["entity"],
        entity_id=msg["entity_id"],
        timestamp=msg["timestamp"],
        data=msg["data"],
    )
