"""Pydantic models for contributor messaging (Phase 3)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    from_contributor_id: str = Field(min_length=1)
    to_contributor_id: Optional[str] = None
    to_workspace_id: Optional[str] = None
    subject: Optional[str] = None
    body: str = Field(min_length=1)


class Message(BaseModel):
    id: str
    from_contributor_id: str
    to_contributor_id: Optional[str] = None
    to_workspace_id: Optional[str] = None
    subject: Optional[str] = None
    body: str
    read: bool = False
    created_at: datetime


class InboxResponse(BaseModel):
    contributor_id: str
    messages: list[Message]
    total: int
    unread_count: int
