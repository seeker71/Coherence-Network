"""Agent orchestration models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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
    """Request body for creating a task. direction: strip leading/trailing whitespace before length check (spec 010)."""

    direction: str = Field(..., min_length=1, max_length=5000)
    task_type: TaskType
    context: Optional[Dict[str, Any]] = None

    @field_validator("task_type", mode="before")
    @classmethod
    def task_type_must_be_enum(cls, v: object) -> TaskType:
        """Reject invalid task_type so POST returns 422 with detail array (spec 037, 009)."""
        if isinstance(v, TaskType):
            return v
        if isinstance(v, str) and v in (e.value for e in TaskType):
            return TaskType(v)
        raise ValueError(
            f"task_type must be one of {[e.value for e in TaskType]}; got {v!r}"
        )

    @field_validator("direction", mode="before")
    @classmethod
    def direction_strip(cls, v: object) -> object:
        """Strip leading/trailing whitespace before length validation; whitespace-only becomes empty → 422 (spec 010)."""
        if isinstance(v, str):
            return v.strip()
        return v


class AgentTaskUpsertActive(BaseModel):
    """Request body for upserting an externally running task session."""

    session_key: str = Field(..., min_length=1, max_length=200)
    direction: str = Field(..., min_length=1, max_length=5000)
    task_type: TaskType = TaskType.IMPL
    worker_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    context: Optional[Dict[str, Any]] = None

    @field_validator("session_key", mode="before")
    @classmethod
    def session_key_strip(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("direction", mode="before")
    @classmethod
    def direction_strip(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class AgentTaskUpdate(BaseModel):
    """Request body for updating task status. Supports progress and decision fields (spec 003)."""

    status: Optional[TaskStatus] = None
    output: Optional[str] = None
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    current_step: Optional[str] = None
    decision_prompt: Optional[str] = None
    decision: Optional[str] = None  # user reply; when present and status is needs_decision, set status→running
    context: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @field_validator("progress_pct", mode="before")
    @classmethod
    def progress_pct_int_only(cls, v: object) -> Optional[int]:
        """Reject string or other non-int (spec 002: PATCH invalid progress_pct type → 422)."""
        if v is None:
            return None
        if not isinstance(v, int):
            raise ValueError("progress_pct must be an integer")
        return v


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
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
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
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
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
    executor: Optional[str] = None  # "claude", "cursor", or "openclaw"
    provider: Optional[str] = None
    billing_provider: Optional[str] = None
    is_paid_provider: Optional[bool] = None
