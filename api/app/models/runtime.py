"""Runtime telemetry models for endpoint-level tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


RuntimeSource = Literal["api", "web", "web_api", "worker"]


class RuntimeEventCreate(BaseModel):
    source: RuntimeSource
    endpoint: str = Field(min_length=1)
    raw_endpoint: Optional[str] = None
    method: str = Field(default="GET", min_length=1)
    status_code: int = Field(default=200, ge=100, le=599)
    runtime_ms: float = Field(gt=0.0)
    idea_id: Optional[str] = None
    metadata: dict[str, str | float | int | bool] = Field(default_factory=dict)


class RuntimeEvent(RuntimeEventCreate):
    id: str = Field(min_length=1)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime_cost_estimate: float = Field(ge=0.0)
    origin_idea_id: Optional[str] = None


class IdeaRuntimeSummary(BaseModel):
    idea_id: str
    event_count: int = Field(ge=0)
    total_runtime_ms: float = Field(ge=0.0)
    average_runtime_ms: float = Field(ge=0.0)
    runtime_cost_estimate: float = Field(ge=0.0)
    by_source: dict[str, int] = Field(default_factory=dict)


class EndpointRuntimeSummary(BaseModel):
    endpoint: str = Field(min_length=1)
    methods: list[str] = Field(default_factory=list)
    idea_id: str = Field(min_length=1)
    origin_idea_id: str = Field(min_length=1)
    event_count: int = Field(ge=0)
    total_runtime_ms: float = Field(ge=0.0)
    average_runtime_ms: float = Field(ge=0.0)
    runtime_cost_estimate: float = Field(ge=0.0)
    by_source: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
