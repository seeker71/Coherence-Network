"""Creator resonance report models.

The report accepts explicit platform snapshots instead of scraping or
guessing. Authorized exports, API reads, or manually entered creator
dashboard numbers all land in the same shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SnapshotKind = Literal["baseline", "current", "milestone"]


class CreatorMetricSnapshot(BaseModel):
    followers: float = Field(default=0.0, ge=0.0)
    new_followers: float = Field(default=0.0, ge=0.0)
    reach: float = Field(default=0.0, ge=0.0)
    impressions: float = Field(default=0.0, ge=0.0)
    views: float = Field(default=0.0, ge=0.0)
    likes: float = Field(default=0.0, ge=0.0)
    saves: float = Field(default=0.0, ge=0.0)
    shares: float = Field(default=0.0, ge=0.0)
    comments: float = Field(default=0.0, ge=0.0)
    profile_visits: float = Field(default=0.0, ge=0.0)
    link_clicks: float = Field(default=0.0, ge=0.0)
    streams: float = Field(default=0.0, ge=0.0)
    listeners: float = Field(default=0.0, ge=0.0)
    playlist_adds: float = Field(default=0.0, ge=0.0)
    pre_saves: float = Field(default=0.0, ge=0.0)
    merch_clicks: float = Field(default=0.0, ge=0.0)
    ticket_clicks: float = Field(default=0.0, ge=0.0)
    subscriptions: float = Field(default=0.0, ge=0.0)
    revenue_usd: float = Field(default=0.0, ge=0.0)


class CreatorPlatformSnapshot(BaseModel):
    platform: str = Field(min_length=1, max_length=48)
    kind: SnapshotKind = "current"
    metrics: CreatorMetricSnapshot = Field(default_factory=CreatorMetricSnapshot)
    captured_at: datetime | None = None
    source_label: str | None = Field(default=None, max_length=160)
    evidence_url: str | None = Field(default=None, max_length=500)


class CreatorCampaignCost(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    amount_usd: float = Field(ge=0.0)
    category: str = Field(default="production", max_length=60)


class CreatorArtifact(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    artifact_type: str = Field(default="post", max_length=60)
    platform: str | None = Field(default=None, max_length=48)
    url: str | None = Field(default=None, max_length=500)
    role: str = Field(default="campaign_asset", max_length=80)


class CreatorResonanceReportRequest(BaseModel):
    artist_name: str = Field(min_length=1, max_length=160)
    campaign_title: str = Field(min_length=1, max_length=200)
    window_start: datetime | None = None
    window_end: datetime | None = None
    snapshots: list[CreatorPlatformSnapshot] = Field(min_length=1)
    costs: list[CreatorCampaignCost] = Field(default_factory=list)
    artifacts: list[CreatorArtifact] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list, max_length=12)


class CreatorPlatformSummary(BaseModel):
    platform: str
    baseline: dict[str, float] = Field(default_factory=dict)
    current: dict[str, float] = Field(default_factory=dict)
    delta: dict[str, float] = Field(default_factory=dict)
    strongest_metric: str | None = None
    evidence_count: int = Field(ge=0)


class CreatorDimensionScore(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    baseline_total: float = Field(ge=0.0)
    current_total: float = Field(ge=0.0)
    lift: float
    weight: float = Field(ge=0.0, le=1.0)
    metrics: list[str] = Field(default_factory=list)


class CreatorReportRecommendation(BaseModel):
    priority: str
    reason: str
    action: str
    expected_signal: str


class CreatorReportAnswer(BaseModel):
    can_generate_attention_value: bool
    can_validate_generation: bool
    can_show_income: bool
    status: str
    healthiest_next_execution: str


class CreatorResonanceReport(BaseModel):
    report_id: str
    generated_at: datetime
    artist_name: str
    campaign_title: str
    answer: CreatorReportAnswer
    proof_quality: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    attention_total: float = Field(ge=0.0)
    engagement_total: float = Field(ge=0.0)
    conversion_total: float = Field(ge=0.0)
    relationship_total: float = Field(ge=0.0)
    income_usd: float = Field(ge=0.0)
    cost_usd: float = Field(ge=0.0)
    net_income_usd: float
    engagement_rate: float = Field(ge=0.0)
    conversion_rate: float = Field(ge=0.0)
    platform_summaries: list[CreatorPlatformSummary] = Field(default_factory=list)
    dimensions: list[CreatorDimensionScore] = Field(default_factory=list)
    recommendations: list[CreatorReportRecommendation] = Field(default_factory=list)
    validation_plan: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    truth_boundary: str
