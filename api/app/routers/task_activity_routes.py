"""Task activity endpoints — live task visibility and SSE streaming."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.task_activity_service import (
    get_active_tasks,
    get_activity,
    get_task_stream,
    log_activity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ActivityEvent(BaseModel):
    node_id: str = ""
    node_name: str = ""
    provider: str = ""
    event_type: str
    data: dict = {}


@router.get("/tasks/activity")
async def recent_activity(
    limit: int = Query(50, ge=1, le=200),
    task_id: str | None = Query(None),
    node_id: str | None = Query(None),
) -> list[dict]:
    """Recent activity across all tasks."""
    return get_activity(limit=limit, task_id=task_id, node_id=node_id)


@router.get("/tasks/active")
async def active_tasks() -> list[dict]:
    """Currently executing tasks across all nodes."""
    return get_active_tasks()


@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str) -> list[dict]:
    """All events for one task."""
    return get_task_stream(task_id)


@router.post("/tasks/{task_id}/activity", status_code=201)
async def post_activity(task_id: str, body: ActivityEvent) -> dict:
    """Log an activity event (from runners)."""
    event = log_activity(
        task_id=task_id,
        event_type=body.event_type,
        data={
            "node_id": body.node_id,
            "node_name": body.node_name,
            "provider": body.provider,
            **body.data,
        },
    )
    return event


@router.get("/tasks/{task_id}/events")
async def task_events_sse(task_id: str):
    """Server-Sent Events stream for live task updates."""

    async def event_generator():
        last_seen = 0
        while True:
            events = get_task_stream(task_id)
            new_events = events[last_seen:]
            for event in new_events:
                yield f"data: {json.dumps(event)}\n\n"
            last_seen = len(events)

            # Check if task is done
            if any(
                e["event_type"] in ("completed", "failed", "timeout") for e in events
            ):
                yield f"data: {json.dumps({'event_type': 'end'})}\n\n"
                break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
