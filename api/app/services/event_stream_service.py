"""In-process pub/sub for real-time events (WebSocket + HTTP publish).

Cross-service usage: MCP, CLI, and web connect to the same exchange via
``/api/events/stream`` (subscribe) and ``/api/events/publish`` (emit).

Backpressure: per-subscriber queues drop oldest on overflow (same pattern as
OpenClaw bridge).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

SCHEMA = "coherence.event_stream.v1"
_QUEUE_MAX = 200

_subscribers: list["Subscriber"] = []
_lock = asyncio.Lock()


@dataclass
class Subscriber:
    queue: asyncio.Queue
    event_types: frozenset[str] | None
    entity: str | None
    entity_id: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def envelope(
    event_type: str,
    entity: str,
    entity_id: str | None,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "v": 1,
        "schema": SCHEMA,
        "id": event_id or f"es_{uuid4().hex[:16]}",
        "event_type": event_type,
        "entity": entity,
        "entity_id": entity_id,
        "timestamp": _now_iso(),
        "data": data,
    }


def _matches(sub: Subscriber, event_type: str, entity: str, entity_id: str | None) -> bool:
    if sub.event_types is not None and len(sub.event_types) > 0:
        if event_type not in sub.event_types:
            return False
    if sub.entity is not None and sub.entity != entity:
        return False
    if sub.entity_id is not None:
        if entity_id is None or sub.entity_id != entity_id:
            return False
    return True


def _put(queue: asyncio.Queue, item: dict[str, Any]) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        try:
            _ = queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("event_stream queue still full after drop; skipping event")


def publish(
    event_type: str,
    entity: str,
    entity_id: str | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Fan out to all matching WebSocket subscribers (sync, thread-safe for API handlers)."""
    msg = envelope(event_type, entity, entity_id, data)
    for sub in list(_subscribers):
        if _matches(sub, event_type, entity, entity_id):
            _put(sub.queue, msg)
    return msg


async def register_subscriber(
    *,
    event_types: frozenset[str] | None,
    entity: str | None,
    entity_id: str | None,
) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
    sub = Subscriber(queue=q, event_types=event_types, entity=entity, entity_id=entity_id)
    async with _lock:
        _subscribers.append(sub)
    return q


async def unregister_subscriber(queue: asyncio.Queue) -> None:
    async with _lock:
        _subscribers[:] = [s for s in _subscribers if s.queue is not queue]


def subscriber_count() -> int:
    return len(_subscribers)


def json_dumps(obj: dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"))


def stream_token_configured() -> bool:
    return bool(os.getenv("COHERENCE_EVENT_STREAM_TOKEN", "").strip())


def stream_token_ok(token: str | None) -> bool:
    expected = os.getenv("COHERENCE_EVENT_STREAM_TOKEN", "").strip()
    if not expected:
        return True
    return (token or "").strip() == expected


def publish_token_configured() -> bool:
    return bool(os.getenv("COHERENCE_EVENT_STREAM_PUBLISH_TOKEN", "").strip())


def publish_token_ok(token: str | None) -> bool:
    expected = os.getenv("COHERENCE_EVENT_STREAM_PUBLISH_TOKEN", "").strip()
    if not expected:
        return True
    return (token or "").strip() == expected
