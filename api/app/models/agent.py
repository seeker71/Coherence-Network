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
    target_state: Optional[str] = Field(default=None, min_length=1, max_length=600)
    success_evidence: Optional[List[str]] = None
    abort_evidence: Optional[List[str]] = None
    observation_window_sec: Optional[int] = Field(default=None, ge=1, le=604800)

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

    @field_validator("target_state", mode="before")
    @classmethod
    def target_state_strip(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("success_evidence", "abort_evidence", mode="before")
    @classmethod
    def normalize_evidence_list(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            cleaned = v.strip()
            return [cleaned] if cleaned else []
        if not isinstance(v, list):
            raise ValueError("evidence fields must be a list of strings")
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("evidence fields must contain strings only")
            cleaned = item.strip()
            if cleaned:
                out.append(cleaned)
        return out


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
    target_state: Optional[str] = Field(default=None, min_length=1, max_length=600)
    success_evidence: Optional[List[str]] = None
    abort_evidence: Optional[List[str]] = None
    observation_window_sec: Optional[int] = Field(default=None, ge=1, le=604800)

    @field_validator("progress_pct", mode="before")
    @classmethod
    def progress_pct_int_only(cls, v: object) -> Optional[int]:
        """Reject string or other non-int (spec 002: PATCH invalid progress_pct type → 422)."""
        if v is None:
            return None
        if not isinstance(v, int):
            raise ValueError("progress_pct must be an integer")
        return v

    @field_validator("target_state", mode="before")
    @classmethod
    def update_target_state_strip(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("success_evidence", "abort_evidence", mode="before")
    @classmethod
    def update_normalize_evidence_list(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            cleaned = v.strip()
            return [cleaned] if cleaned else []
        if not isinstance(v, list):
            raise ValueError("evidence fields must be a list of strings")
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("evidence fields must contain strings only")
            cleaned = item.strip()
            if cleaned:
                out.append(cleaned)
        return out


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
    target_state: Optional[str] = None
    success_evidence: Optional[List[str]] = None
    abort_evidence: Optional[List[str]] = None
    observation_window_sec: Optional[int] = None
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
    target_state: Optional[str] = None
    success_evidence: Optional[List[str]] = None
    abort_evidence: Optional[List[str]] = None
    observation_window_sec: Optional[int] = None
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


class AgentRunStateClaim(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1, max_length=200)
    worker_id: str = Field(..., min_length=1, max_length=200)
    lease_seconds: int = Field(default=120, ge=15, le=3600)
    attempt: int = Field(default=1, ge=1, le=100000)
    branch: Optional[str] = Field(default=None, max_length=300)
    repo_path: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None


class AgentRunStateUpdate(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1, max_length=200)
    worker_id: str = Field(..., min_length=1, max_length=200)
    patch: Dict[str, Any] = Field(default_factory=dict)
    lease_seconds: Optional[int] = Field(default=None, ge=15, le=3600)
    require_owner: bool = True


class AgentRunStateHeartbeat(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1, max_length=200)
    worker_id: str = Field(..., min_length=1, max_length=200)
    lease_seconds: int = Field(default=120, ge=15, le=3600)


class AgentRunStateSnapshot(BaseModel):
    claimed: bool
    task_id: str
    run_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: Optional[str] = None
    attempt: Optional[int] = None
    branch: Optional[str] = None
    repo_path: Optional[str] = None
    head_sha: Optional[str] = None
    checkpoint_sha: Optional[str] = None
    failure_class: Optional[str] = None
    next_action: Optional[str] = None
    lease_expires_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    updated_at: Optional[str] = None
    detail: Optional[str] = None


class AgentRunnerHeartbeat(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=200)
    status: str = Field(default="idle", min_length=1, max_length=50)
    lease_seconds: int = Field(default=90, ge=10, le=3600)
    host: Optional[str] = Field(default=None, max_length=200)
    pid: Optional[int] = Field(default=None, ge=1, le=2_147_483_647)
    version: Optional[str] = Field(default=None, max_length=200)
    active_task_id: Optional[str] = Field(default=None, max_length=200)
    active_run_id: Optional[str] = Field(default=None, max_length=200)
    last_error: Optional[str] = Field(default=None, max_length=2000)
    capabilities: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentRunnerSnapshot(BaseModel):
    runner_id: str
    status: str
    online: bool
    host: Optional[str] = None
    pid: Optional[int] = None
    version: Optional[str] = None
    active_task_id: Optional[str] = None
    active_run_id: Optional[str] = None
    last_error: Optional[str] = None
    lease_expires_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentRunnerList(BaseModel):
    runners: List[AgentRunnerSnapshot]
    total: int
