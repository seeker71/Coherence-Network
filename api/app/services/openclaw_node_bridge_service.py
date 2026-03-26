"""OpenClaw node bridge: WebSocket delivery for federation messages (Spec 156 Phase 3).

Real-time push parallel to SSE (`/api/federation/nodes/{id}/stream`), using a versioned
JSON envelope. Backpressure: per-connection queues drop the oldest event when full.
Optional auth: set COHERENCE_BRIDGE_TOKEN; clients pass the same value as query `token`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Match SSE subscriber default; drop oldest on overflow (backpressure).
_BRIDGE_QUEUE_MAX = 100

_ws_subscribers: dict[str, list[asyncio.Queue]] = {}
_ws_lock = asyncio.Lock()

SCHEMA = "coherence.openclaw.bridge.v1"


def bridge_envelope(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Stable JSON envelope for OpenClaw / gateway consumers."""
    return {
        "v": 1,
        "schema": SCHEMA,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def notify_openclaw_bridge_subscribers(target_node_id: str | None, event: dict[str, Any]) -> None:
    """Push a federation message (or compatible event) to WebSocket subscribers."""
    wrapped = bridge_envelope("federation_message", event)
    targets: list[asyncio.Queue] = []
    if target_node_id:
        targets = _ws_subscribers.get(target_node_id, [])
    else:
        for queues in _ws_subscribers.values():
            targets.extend(queues)

    for q in targets:
        try:
            q.put_nowait(wrapped)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(wrapped)
            except asyncio.QueueFull:
                logger.warning("Openclaw bridge queue still full after drop; skipping event")


async def register_bridge_subscriber(node_id: str) -> asyncio.Queue:
    """Return a queue for this node_id."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=_BRIDGE_QUEUE_MAX)
    async with _ws_lock:
        if node_id not in _ws_subscribers:
            _ws_subscribers[node_id] = []
        _ws_subscribers[node_id].append(queue)
    return queue


async def unregister_bridge_subscriber(node_id: str, queue: asyncio.Queue) -> None:
    async with _ws_lock:
        if node_id in _ws_subscribers:
            try:
                _ws_subscribers[node_id].remove(queue)
            except ValueError:
                pass
            if not _ws_subscribers[node_id]:
                del _ws_subscribers[node_id]


def bridge_token_configured() -> bool:
    return bool(os.getenv("COHERENCE_BRIDGE_TOKEN", "").strip())


def bridge_token_ok(token: str | None) -> bool:
    expected = os.getenv("COHERENCE_BRIDGE_TOKEN", "").strip()
    if not expected:
        return True
    return (token or "").strip() == expected


def json_dumps(obj: dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"))
