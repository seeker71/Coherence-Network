"""Agent orchestration models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    SPEC = "spec"
    TEST = "test"
    IMPL = "impl"
    REVIEW = "review"
    HEAL = "heal"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_DECISION = "needs_decision"


class AgentTaskCreate(BaseModel):
    """Request body for creating a task."""

    direction: str = Field(..., min_length=1)
    task_type: TaskType
    context: Optional[Dict[str, Any]] = None


class AgentTaskUpdate(BaseModel):
    """Request body for updating task status. Supports progress and decision fields (spec 003)."""

    status: Optional[TaskStatus] = None
    output: Optional[str] = None
    progress_pct: Optional[int] = None  # 0-100
    current_step: Optional[str] = None
    decision_prompt: Optional[str] = None
    decision: Optional[str] = None  # user reply; when present and status is needs_decision, set status→running


class AgentTask(BaseModel):
    """Agent task as returned by the API."""

    id: str
    direction: str
    task_type: TaskType
    status: TaskStatus
    model: str
    command: str
    output: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    progress_pct: Optional[int] = None
    current_step: Optional[str] = None
    decision_prompt: Optional[str] = None
    decision: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AgentTaskListItem(BaseModel):
    """Task in list response (no command/output)."""

    id: str
    direction: str
    task_type: TaskType
    status: TaskStatus
    model: str
    progress_pct: Optional[int] = None
    current_step: Optional[str] = None
    decision_prompt: Optional[str] = None
    decision: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AgentTaskList(BaseModel):
    """List of tasks with total."""

    tasks: List[AgentTaskListItem]
    total: int


class RouteResponse(BaseModel):
    """Response from route-only endpoint."""

    task_type: str
    model: str
    command_template: str
    tier: str
