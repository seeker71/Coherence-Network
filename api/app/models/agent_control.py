"""Pydantic models for the agent SSE control channel (steer, checkpoint, abort, ask, report)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ControlCommandType(str, Enum):
    CHECKPOINT = "checkpoint"
    STEER = "steer"
    ABORT = "abort"
    ASK = "ask"
    REPORT = "report"
    PING = "ping"
    ERROR = "error"


class ControlAckStatus(str, Enum):
    RECEIVED = "received"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


CONTROL_SCHEMA_VERSION = 1


class ControlCommandEnqueue(BaseModel):
    """POST /control/commands body (envelope without command_id — server assigns)."""

    type: ControlCommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    issuer: str = Field(default="api", min_length=1, max_length=500)

    @field_validator("type", mode="before")
    @classmethod
    def coerce_type(cls, v: object) -> ControlCommandType:
        if isinstance(v, ControlCommandType):
            return v
        if isinstance(v, str):
            try:
                return ControlCommandType(v)
            except ValueError as err:
                raise ValueError(f"invalid control command type: {v!r}") from err
        raise ValueError("type must be a string or ControlCommandType")


class ControlCommandQueuedResponse(BaseModel):
    command_id: str
    task_id: str
    queued_at: datetime


class ControlAckRequest(BaseModel):
    command_id: str = Field(..., min_length=1, max_length=80)
    status: ControlAckStatus
    message: Optional[str] = Field(default=None, max_length=4000)
    result: Optional[dict[str, Any]] = None


class ControlAckResponse(BaseModel):
    command_id: str
    task_id: str
    status: ControlAckStatus
    message: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    acked_at: datetime


def new_command_id() -> str:
    return f"cmd_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
