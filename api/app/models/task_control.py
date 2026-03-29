"""Pydantic models for task control channel."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ControlCommandType(str, Enum):
    CHECKPOINT = "checkpoint"
    STEER = "steer"
    ABORT = "abort"
    ASK = "ask"
    REPORT = "report"


class ControlCommandStatus(str, Enum):
    QUEUED = "queued"
    DELIVERED = "delivered"
    ACKED = "acked"
    FAILED = "failed"


class ControlCommand(BaseModel):
    command_id: UUID = Field(default_factory=UUID)
    task_id: str
    command: ControlCommandType
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    issuer: str = "operator"
    payload: Dict[str, Any] = Field(default_factory=dict)
    state: ControlCommandStatus = ControlCommandStatus.QUEUED
    client_command_id: Optional[UUID] = None


class ControlAckStatus(str, Enum):
    RECEIVED = "received"
    APPLIED = "applied"
    REJECTED = "rejected"


class ControlAck(BaseModel):
    command_id: UUID
    status: ControlAckStatus
    detail: Optional[str] = None
    reason_code: Optional[str] = None


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PermissionResolution(BaseModel):
    command_id: UUID
    decision: PermissionDecision
    note: Optional[str] = None


class CommandIssueRequest(BaseModel):
    command: ControlCommandType
    payload: Dict[str, Any] = Field(default_factory=dict)
    client_command_id: Optional[UUID] = None


class CommandIssueResponse(BaseModel):
    command_id: UUID
    task_id: str
    queued_at: datetime
    duplicate: bool = False
