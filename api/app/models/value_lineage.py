"""Models for idea->spec->implementation->usage->payout lineage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

LineageStage = Literal["idea", "research", "spec", "spec_upgrade", "implementation", "review"]


class LineageContributors(BaseModel):
    idea: Optional[str] = None
    research: Optional[str] = None
    spec: Optional[str] = None
    spec_upgrade: Optional[str] = None
    implementation: Optional[str] = None
    review: Optional[str] = None


class LineageInvestment(BaseModel):
    stage: LineageStage
    contributor: str = Field(min_length=1)
    energy_units: float = Field(gt=0.0)
    coherence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    awareness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    friction_score: float = Field(default=0.5, ge=0.0, le=1.0)


class LineageLinkCreate(BaseModel):
    idea_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    implementation_refs: list[str] = Field(default_factory=list)
    contributors: LineageContributors
    investments: list[LineageInvestment] = Field(default_factory=list)
    estimated_cost: float = Field(ge=0.0)


class LineageLink(LineageLinkCreate):
    id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageEventCreate(BaseModel):
    source: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float = Field(ge=0.0)


class UsageEvent(UsageEventCreate):
    id: str = Field(min_length=1)
    lineage_id: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LineageValuation(BaseModel):
    lineage_id: str
    idea_id: str
    spec_id: str
    measured_value_total: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    roi_ratio: float = Field(ge=0.0)
    event_count: int = Field(ge=0)


class PayoutPreviewRequest(BaseModel):
    payout_pool: float = Field(gt=0.0)


class PayoutRow(BaseModel):
    role: str
    contributor: str
    amount: float = Field(ge=0.0)
    energy_units: float = Field(gt=0.0)
    effective_weight: float = Field(ge=0.0)


class PayoutPreview(BaseModel):
    lineage_id: str
    schema_version: str = Field(default="energy-balanced-v1")
    payout_pool: float = Field(gt=0.0)
    measured_value_total: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    roi_ratio: float = Field(ge=0.0)
    weights: dict[str, float]
    objective_weights: dict[str, float]
    signals: dict[str, float]
    payouts: list[PayoutRow]


class MinimumE2EFlowResponse(BaseModel):
    lineage_id: str
    usage_event_id: str
    valuation: LineageValuation
    payout_preview: PayoutPreview
    checks: list[str]


class LineageLinksResponse(BaseModel):
    links: list[LineageLink]
