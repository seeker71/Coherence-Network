"""Activity event models for workspace activity feeds."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ActivityEventType(str, Enum):
    idea_created = "idea_created"
    idea_updated = "idea_updated"
    spec_created = "spec_created"
    task_completed = "task_completed"
    contribution_recorded = "contribution_recorded"
    member_joined = "member_joined"
    member_invited = "member_invited"
    governance_vote = "governance_vote"
    project_created = "project_created"
    message_sent = "message_sent"


class ActivityEvent(BaseModel):
    id: str
    event_type: str
    workspace_id: str
    actor_contributor_id: Optional[str] = None
    subject_type: Optional[str] = None  # idea, spec, task, contributor...
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    summary: str
    created_at: datetime


class ActivityFeedResponse(BaseModel):
    workspace_id: str
    events: list[ActivityEvent]
    total: int
    has_more: bool


class ActivitySummaryResponse(BaseModel):
    workspace_id: str
    event_counts: dict[str, int]
    period_days: int
