"""Models for provider automation usage, capacity, and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ProviderKind = Literal["internal", "github", "openai", "custom"]
ProviderStatus = Literal["ok", "degraded", "unavailable"]
UnitType = Literal["tokens", "requests", "minutes", "usd", "tasks", "hours", "gb"]
AlertSeverity = Literal["info", "warning", "critical"]
DataSource = Literal["provider_api", "provider_cli", "runtime_events", "configuration_only", "unknown"]


class UsageMetric(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    unit: UnitType
    used: float = Field(ge=0.0)
    remaining: float | None = Field(default=None, ge=0.0)
    limit: float | None = Field(default=None, ge=0.0)
    window: str | None = Field(default=None, max_length=120)
    validation_state: str | None = Field(default=None, max_length=40)
    validation_detail: str | None = Field(default=None, max_length=400)
    evidence_source: str | None = Field(default=None, max_length=200)


class ProviderUsageSnapshot(BaseModel):
    id: str = Field(min_length=1, max_length=140)
    provider: str = Field(min_length=1, max_length=120)
    kind: ProviderKind
    status: ProviderStatus
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: list[UsageMetric] = Field(default_factory=list)
    cost_usd: float | None = Field(default=None, ge=0.0)
    capacity_tasks_per_day: float | None = Field(default=None, ge=0.0)
    actual_current_usage: float | None = Field(default=None, ge=0.0)
    actual_current_usage_unit: UnitType | None = None
    usage_per_time: str | None = Field(default=None, max_length=160)
    usage_remaining: float | None = Field(default=None, ge=0.0)
    usage_remaining_unit: UnitType | None = None
    official_records: list[str] = Field(default_factory=list)
    data_source: DataSource = "unknown"
    notes: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderUsageOverview(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    providers: list[ProviderUsageSnapshot] = Field(default_factory=list)
    unavailable_providers: list[str] = Field(default_factory=list)
    tracked_providers: int = Field(ge=0)
    limit_coverage: dict[str, Any] = Field(default_factory=dict)


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


class SubscriptionPlanEstimate(BaseModel):
    provider: str = Field(min_length=1, max_length=120)
    detected: bool = False
    current_tier: str = Field(min_length=1, max_length=120)
    next_tier: str = Field(min_length=1, max_length=120)
    current_monthly_cost_usd: float = Field(ge=0.0)
    next_monthly_cost_usd: float = Field(ge=0.0)
    monthly_upgrade_delta_usd: float = Field(ge=0.0)
    estimated_benefit_score: float = Field(ge=0.0)
    estimated_roi: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    expected_benefits: list[str] = Field(default_factory=list)


class SubscriptionUpgradeEstimatorReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    plans: list[SubscriptionPlanEstimate] = Field(default_factory=list)
    detected_subscriptions: int = Field(ge=0)
    estimated_current_monthly_cost_usd: float = Field(ge=0.0)
    estimated_next_monthly_cost_usd: float = Field(ge=0.0)
    estimated_monthly_upgrade_delta_usd: float = Field(ge=0.0)


class ProviderReadinessRow(BaseModel):
    provider: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=120)
    status: ProviderStatus
    required: bool = False
    configured: bool = False
    severity: AlertSeverity
    missing_env: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProviderReadinessReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    required_providers: list[str] = Field(default_factory=list)
    all_required_ready: bool = False
    blocking_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    providers: list[ProviderReadinessRow] = Field(default_factory=list)
    limit_telemetry: dict[str, Any] = Field(default_factory=dict)


class ProviderValidationRow(BaseModel):
    provider: str = Field(min_length=1, max_length=120)
    configured: bool = False
    readiness_status: ProviderStatus = "unavailable"
    usage_events: int = Field(ge=0)
    successful_events: int = Field(ge=0)
    validated_execution: bool = False
    last_event_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)


class ProviderValidationReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    required_providers: list[str] = Field(default_factory=list)
    runtime_window_seconds: int = Field(ge=60, le=2592000)
    min_execution_events: int = Field(ge=1, le=50)
    all_required_validated: bool = False
    blocking_issues: list[str] = Field(default_factory=list)
    providers: list[ProviderValidationRow] = Field(default_factory=list)
