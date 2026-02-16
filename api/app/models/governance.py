"""Governance and review models for change requests and voting."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    HUMAN = "human"
    MACHINE = "machine"


class VoteDecision(str, Enum):
    YES = "yes"
    NO = "no"


class ChangeRequestType(str, Enum):
    IDEA_CREATE = "idea_create"
    IDEA_UPDATE = "idea_update"
    IDEA_ADD_QUESTION = "idea_add_question"
    IDEA_ANSWER_QUESTION = "idea_answer_question"
    SPEC_CREATE = "spec_create"
    SPEC_UPDATE = "spec_update"


class ChangeRequestStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class ChangeRequestVote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    change_request_id: str
    voter_id: str = Field(min_length=1)
    voter_type: ActorType
    decision: VoteDecision
    rationale: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChangeRequestCreate(BaseModel):
    request_type: ChangeRequestType
    title: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    proposer_id: str = Field(min_length=1)
    proposer_type: ActorType = ActorType.HUMAN
    required_approvals: Optional[int] = Field(default=None, ge=1, le=10)
    auto_apply_on_approval: bool = True


class ChangeRequestVoteCreate(BaseModel):
    voter_id: str = Field(min_length=1)
    voter_type: ActorType = ActorType.HUMAN
    decision: VoteDecision
    rationale: Optional[str] = None


class ChangeRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_type: ChangeRequestType
    title: str
    payload: dict[str, Any]
    proposer_id: str
    proposer_type: ActorType
    required_approvals: int = Field(ge=1)
    auto_apply_on_approval: bool = True
    status: ChangeRequestStatus = ChangeRequestStatus.OPEN
    approvals: int = Field(default=0, ge=0)
    rejections: int = Field(default=0, ge=0)
    applied_result: Optional[dict[str, Any]] = None
    votes: list[ChangeRequestVote] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
