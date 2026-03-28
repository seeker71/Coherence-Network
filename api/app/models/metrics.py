"""Pydantic models for pipeline metrics API. Spec 026 Phase 1."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskMetricRecord(BaseModel):
    """Single task metric record posted by agent_runner. Spec 026."""

    task_id: str = Field(..., min_length=1, max_length=1000)
    task_type: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=200)
    executor: str = Field(default="", max_length=100)
    duration_seconds: float = Field(..., ge=0, le=86400)
    status: str = Field(..., pattern="^(completed|failed|timed_out)$")
    prompt_variant: Optional[str] = Field(default=None, max_length=200)
    skill_version: Optional[str] = Field(default=None, max_length=200)

    model_config = {"extra": "forbid"}


class ExecutionTimeStats(BaseModel):
    """P50/P95 execution time across tasks in the rolling window."""

    p50_seconds: float = Field(default=0, ge=0)
    p95_seconds: float = Field(default=0, ge=0)


class SuccessRateStats(BaseModel):
    """Completed vs failed counts and derived rate."""

    completed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    rate: float = Field(default=0.0, ge=0.0, le=1.0)


class MetricsResponse(BaseModel):
    """Response shape for GET /api/agent/metrics. Spec 026."""

    execution_time: ExecutionTimeStats = Field(default_factory=ExecutionTimeStats)
    success_rate: SuccessRateStats = Field(default_factory=SuccessRateStats)
    by_task_type: dict[str, Any] = Field(default_factory=dict)
    by_model: dict[str, Any] = Field(default_factory=dict)
    window_days: Optional[int] = Field(default=None, ge=1, le=90)
