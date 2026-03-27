"""Pydantic models for the cross-service event stream (WebSocket pub/sub)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventStreamPublish(BaseModel):
    """Publish payload for POST /api/events/publish."""

    event_type: str = Field(..., min_length=1, max_length=128)
    entity: str = Field(default="generic", max_length=128)
    entity_id: str | None = Field(default=None, max_length=256)
    data: dict[str, Any] = Field(default_factory=dict)


class EventStreamPublishResponse(BaseModel):
    """201 response: stable envelope plus server-assigned correlation id."""

    v: int = 1
    schema: str
    id: str
    event_type: str
    entity: str
    entity_id: str | None
    timestamp: str
    data: dict[str, Any]
