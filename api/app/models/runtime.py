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
    paid_tool_event_count: int = Field(ge=0, default=0)
    paid_tool_failure_count: int = Field(ge=0, default=0)
    paid_tool_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    paid_tool_runtime_cost: float = Field(ge=0.0, default=0.0)
    paid_tool_average_runtime_ms: float = Field(ge=0.0, default=0.0)
    by_source: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)


class EndpointAttentionRow(BaseModel):
    endpoint: str = Field(min_length=1)
    methods: list[str] = Field(default_factory=list)
    idea_id: str = Field(min_length=1)
    origin_idea_id: str = Field(min_length=1)
    event_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    runtime_cost_estimate: float = Field(ge=0.0)
    cost_per_event: float = Field(ge=0.0)
    paid_tool_event_count: int = Field(ge=0)
    paid_tool_failure_count: int = Field(ge=0)
    paid_tool_ratio: float = Field(ge=0.0, le=1.0)
    friction_event_count: int = Field(ge=0)
    friction_event_density: float = Field(ge=0.0, le=1.0)
    potential_value: float = Field(ge=0.0)
    actual_value: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    actual_cost: float = Field(ge=0.0)
    value_gap: float = Field(ge=0.0)
    attention_score: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_attention: bool = False
    reasons: list[str] = Field(default_factory=list)


class EndpointAttentionReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_seconds: int = Field(ge=60)
    attention_threshold: float = Field(ge=0.0, le=1_000.0)
    min_event_count: int = Field(ge=1)
    total_endpoints: int = Field(ge=0)
    attention_count: int = Field(ge=0)
    endpoints: list[EndpointAttentionRow] = Field(default_factory=list)
