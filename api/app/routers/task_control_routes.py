"""Task control routes — real-time steering and feedback."""

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.task_control import (
    CommandIssueRequest,
    CommandIssueResponse,
    ControlAck,
    PermissionResolution,
)
from app.services import task_control_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tasks/{task_id}/control-stream")
async def task_control_sse(task_id: str, last_event_id: Optional[uuid.UUID] = Query(None)):
    """SSE stream for control commands addressed to the runner."""

    async def event_generator():
        last_seen_id = last_event_id
        while True:
            # Get pending commands
            commands = await task_control_service.get_commands(task_id, since_command_id=last_seen_id)
            for cmd in commands:
                payload = {
                    "type": "control_command",
                    "command": cmd.command,
                    "command_id": str(cmd.command_id),
                    "issued_at": cmd.issued_at.isoformat(),
                    "issuer": cmd.issuer,
                    "payload": cmd.payload,
                }
                yield f"id: {cmd.command_id}\ndata: {json.dumps(payload)}\n\n"
                last_seen_id = cmd.command_id

            # Wait for new commands
            await asyncio.sleep(1.0)
            
            # Send heartbeat ping
            yield ": ping\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tasks/{task_id}/control/issue", status_code=201)
async def issue_command(task_id: str, body: CommandIssueRequest) -> CommandIssueResponse:
    """Issue a control command (from operator/UI)."""
    return await task_control_service.issue_command(task_id, body)


@router.post("/tasks/{task_id}/control/ack", status_code=201)
async def acknowledge_command(task_id: str, body: ControlAck) -> dict:
    """Acknowledge a control command (from runner)."""
    success = await task_control_service.acknowledge_command(task_id, body)
    if not success:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"ok": True}


@router.post("/tasks/{task_id}/control/permission")
async def resolve_permission(task_id: str, body: PermissionResolution) -> dict:
    """Resolve an 'ask' command decision (from operator/UI)."""
    success = await task_control_service.resolve_permission(task_id, body)
    if not success:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"ok": True}
