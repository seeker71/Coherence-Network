"""Service for task control commands and SSE fan-out."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.models.task_control import (
    CommandIssueRequest,
    CommandIssueResponse,
    ControlAck,
    ControlCommand,
    ControlCommandStatus,
    PermissionResolution,
)

logger = logging.getLogger(__name__)

# task_id -> list of commands
_command_queues: Dict[str, List[ControlCommand]] = {}

# task_id -> asyncio.Condition for SSE fan-out
_queue_conditions: Dict[str, asyncio.Condition] = {}

# command_id -> ControlAck (idempotency for acks)
_acks: Dict[uuid.UUID, ControlAck] = {}


async def _get_condition(task_id: str) -> asyncio.Condition:
    if task_id not in _queue_conditions:
        _queue_conditions[task_id] = asyncio.Condition()
    return _queue_conditions[task_id]


async def issue_command(task_id: str, request: CommandIssueRequest) -> CommandIssueResponse:
    """Queue a new control command for a task."""
    condition = await _get_condition(task_id)

    # Check for duplicate client_command_id if provided
    if request.client_command_id:
        existing = next(
            (c for c in _command_queues.get(task_id, []) if getattr(c, "client_command_id", None) == request.client_command_id),
            None
        )
        if existing:
            return CommandIssueResponse(
                command_id=existing.command_id,
                task_id=task_id,
                queued_at=existing.issued_at,
                duplicate=True
            )

    command_id = uuid.uuid4()
    command = ControlCommand(
        command_id=command_id,
        task_id=task_id,
        command=request.command,
        payload=request.payload,
        state=ControlCommandStatus.QUEUED,
        client_command_id=request.client_command_id
    )

    if task_id not in _command_queues:
        _command_queues[task_id] = []
    _command_queues[task_id].append(command)

    async with condition:
        condition.notify_all()

    logger.info("Command %s issued for task %s", command_id, task_id)
    return CommandIssueResponse(
        command_id=command_id,
        task_id=task_id,
        queued_at=command.issued_at,
        duplicate=False
    )


async def acknowledge_command(task_id: str, ack: ControlAck) -> bool:
    """Acknowledge receipt or application of a command."""
    # Find command
    queue = _command_queues.get(task_id, [])
    command = next((c for c in queue if c.command_id == ack.command_id), None)

    if not command:
        logger.warning("Ack for unknown command %s in task %s", ack.command_id, task_id)
        return False

    # Update state
    if ack.status == "applied":
        command.state = ControlCommandStatus.ACKED
    elif ack.status == "rejected":
        command.state = ControlCommandStatus.FAILED

    _acks[ack.command_id] = ack
    logger.info("Command %s acknowledged with status %s", ack.command_id, ack.status)
    return True


async def resolve_permission(task_id: str, resolution: PermissionResolution) -> bool:
    """Resolve an 'ask' command with a decision."""
    # This is a specialized form of acknowledgement that might trigger task resume
    # For now, just record it as an ack with details
    ack = ControlAck(
        command_id=resolution.command_id,
        status="applied",
        detail=f"Decision: {resolution.decision}. Note: {resolution.note}"
    )
    return await acknowledge_command(task_id, ack)


async def get_commands(task_id: str, since_command_id: Optional[uuid.UUID] = None) -> List[ControlCommand]:
    """Get all commands for a task, optionally since a specific one."""
    queue = _command_queues.get(task_id, [])
    if not since_command_id:
        return queue

    # Find index of since_command_id
    idx = -1
    for i, cmd in enumerate(queue):
        if cmd.command_id == since_command_id:
            idx = i
            break

    return queue[idx + 1:] if idx != -1 else queue


async def wait_for_commands(task_id: str, timeout: float = 30.0) -> bool:
    """Wait for new commands on the queue."""
    condition = await _get_condition(task_id)
    async with condition:
        try:
            await asyncio.wait_for(condition.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
