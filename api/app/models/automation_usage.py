"""Models for provider automation usage, capacity, and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ProviderKind = Literal["internal", "github", "openai", "custom"]
ProviderStatus = Literal["ok", "degraded", "unavailable"]
UnitType = Literal["tokens", "requests", "minutes", "usd", "tasks", "hours"]
AlertSeverity = Literal["info", "warning", "critical"]


class UsageMetric(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    unit: UnitType
    used: float = Field(ge=0.0)
    remaining: float | None = Field(default=None, ge=0.0)
    limit: float | None = Field(default=None, ge=0.0)
    window: str | None = Field(default=None, max_length=120)


class ProviderUsageSnapshot(BaseModel):
    id: str = Field(min_length=1, max_length=140)
    provider: str = Field(min_length=1, max_length=120)
    kind: ProviderKind
    status: ProviderStatus
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: list[UsageMetric] = Field(default_factory=list)
    cost_usd: float | None = Field(default=None, ge=0.0)
    capacity_tasks_per_day: float | None = Field(default=None, ge=0.0)
    notes: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderUsageOverview(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    providers: list[ProviderUsageSnapshot] = Field(default_factory=list)
    unavailable_providers: list[str] = Field(default_factory=list)
    tracked_providers: int = Field(ge=0)


class UsageAlert(BaseModel):
    id: str = Field(min_length=1, max_length=180)
    provider: str = Field(min_length=1, max_length=120)
    metric_id: str = Field(min_length=1, max_length=120)
    severity: AlertSeverity
    message: str = Field(min_length=1, max_length=500)
    remaining_ratio: float | None = Field(default=None, ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageAlertReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    threshold_ratio: float = Field(ge=0.0, le=1.0)
    alerts: list[UsageAlert] = Field(default_factory=list)
