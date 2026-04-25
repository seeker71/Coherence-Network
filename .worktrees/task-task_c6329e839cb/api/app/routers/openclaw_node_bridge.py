"""WebSocket bridge for OpenClaw ↔ federation node messages (real-time, alongside SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services import openclaw_node_bridge_service as bridge

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/federation/openclaw/nodes/{node_id}/bridge")
async def openclaw_node_bridge(
    websocket: WebSocket,
    node_id: str,
    token: str | None = Query(None, description="Must match federation.bridge_token when bridge auth is configured"),
) -> None:
    """Bidirectional-capable WebSocket; server primarily pushes federation_message events.

    Reconnect: clients should reconnect with exponential backoff on disconnect.
    Client JSON ping: ``{"type":"ping"}`` → server ``{"type":"pong","schema":...}``.
    """
    if not bridge.bridge_token_ok(token):
        await websocket.close(code=1008, reason="bridge token required or invalid")
        return

    await websocket.accept()
    queue = await bridge.register_bridge_subscriber(node_id)
    try:
        hello = bridge.bridge_envelope(
            "connected",
            {"node_id": node_id, "schema": bridge.SCHEMA},
        )
        await websocket.send_text(bridge.json_dumps(hello))

        async def pump_out() -> None:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    await websocket.send_text(bridge.json_dumps(event))
                except asyncio.TimeoutError:
                    hb = bridge.bridge_envelope("heartbeat", {"node_id": node_id})
                    await websocket.send_text(bridge.json_dumps(hb))
                except (WebSocketDisconnect, OSError) as exc:
                    logger.debug("bridge pump send end: %s", exc)
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
                    await websocket.send_text(
                        bridge.json_dumps({"type": "pong", "schema": bridge.SCHEMA}),
                    )
        except WebSocketDisconnect:
            pass
        finally:
            pump.cancel()
            try:
                await pump
            except asyncio.CancelledError:
                pass
    finally:
        await bridge.unregister_bridge_subscriber(node_id, queue)
