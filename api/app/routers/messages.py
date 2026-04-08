"""Contributor messaging endpoints (Phase 3).

Messages are graph nodes with edges connecting sender and recipient.
Write endpoints require API key authentication.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.middleware.auth import require_api_key
from app.models.message import InboxResponse, Message, MessageCreate
from app.services import message_service

router = APIRouter()


class MarkReadBody(BaseModel):
    contributor_id: str = Field(min_length=1)


@router.post("/messages", response_model=Message, status_code=201)
async def send_message(
    data: MessageCreate,
    _api_key: str = Depends(require_api_key),
) -> Message:
    """Send a direct or workspace message."""
    try:
        node = message_service.send_message(
            data.from_contributor_id,
            to_contributor_id=data.to_contributor_id,
            to_workspace_id=data.to_workspace_id,
            subject=data.subject,
            body=data.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Node.to_dict() merges properties into top-level dict
    return Message(
        id=node["id"],
        from_contributor_id=node.get("from_contributor_id", data.from_contributor_id),
        to_contributor_id=node.get("to_contributor_id"),
        to_workspace_id=node.get("to_workspace_id"),
        subject=node.get("subject"),
        body=node.get("body", data.body),
        read=node.get("read", False),
        created_at=node.get("created_at", ""),
    )


@router.get("/messages/inbox/{contributor_id}", response_model=InboxResponse)
async def get_inbox(
    contributor_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
) -> InboxResponse:
    """Get a contributor's inbox."""
    result = message_service.get_inbox(
        contributor_id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return InboxResponse(
        contributor_id=result["contributor_id"],
        messages=[Message(**m) for m in result["messages"]],
        total=result["total"],
        unread_count=result["unread_count"],
    )


@router.get("/messages/thread/{contributor_a}/{contributor_b}", response_model=list[Message])
async def get_thread(
    contributor_a: str,
    contributor_b: str,
    limit: int = Query(50, ge=1, le=200),
) -> list[Message]:
    """Get the message thread between two contributors."""
    messages = message_service.get_thread(
        contributor_a,
        contributor_b,
        limit=limit,
    )
    return [Message(**m) for m in messages]


@router.patch("/messages/{message_id}/read", response_model=Message)
async def mark_read(
    message_id: str,
    body: MarkReadBody,
    _api_key: str = Depends(require_api_key),
) -> Message:
    """Mark a message as read."""
    updated = message_service.mark_read(message_id, body.contributor_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Message not found")
    # Node.to_dict() merges properties into top-level dict
    return Message(
        id=updated["id"],
        from_contributor_id=updated.get("from_contributor_id", ""),
        to_contributor_id=updated.get("to_contributor_id"),
        to_workspace_id=updated.get("to_workspace_id"),
        subject=updated.get("subject"),
        body=updated.get("body", ""),
        read=updated.get("read", True),
        created_at=updated.get("created_at", ""),
    )


@router.get("/workspaces/{workspace_id}/messages", response_model=list[Message])
async def get_workspace_messages(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Message]:
    """Get messages sent to a workspace."""
    messages = message_service.get_workspace_messages(
        workspace_id,
        limit=limit,
        offset=offset,
    )
    return [Message(**m) for m in messages]
