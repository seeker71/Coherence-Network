"""Portfolio Pydantic models — contributor personal view (spec 174)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Identity ────────────────────────────────────────────────────────


class LinkedIdentity(BaseModel):
    type: str  # github | telegram | wallet
    handle: str
    verified: bool


class ContributorSummary(BaseModel):
    id: str
    display_name: str
    identities: list[LinkedIdentity] = Field(default_factory=list)


# ── Portfolio aggregate ─────────────────────────────────────────────


class PortfolioSummary(BaseModel):
    contributor: ContributorSummary
    cc_balance: Optional[float] = None
    cc_network_pct: Optional[float] = None
    idea_contribution_count: int = 0
    stake_count: int = 0
    task_completion_count: int = 0
    recent_activity: Optional[datetime] = None


# ── CC balance / history ────────────────────────────────────────────


class CCBalance(BaseModel):
    contributor_id: str
    balance: float
    network_total: float
    network_pct: float
    last_updated: datetime


class CCHistoryBucket(BaseModel):
    period_start: datetime
    period_end: datetime
    cc_earned: float
    running_total: float
    network_pct_at_period_end: Optional[float] = None


class CCHistory(BaseModel):
    contributor_id: str
    window: str
    bucket: str
    series: list[CCHistoryBucket] = Field(default_factory=list)


# ── Network stats ────────────────────────────────────────────────────


class NetworkStats(BaseModel):
    total_supply: float
    total_contributors: int
    last_computed_at: datetime


# ── Health signal ────────────────────────────────────────────────────


class HealthSignal(BaseModel):
    activity_signal: str = "unknown"  # active | slow | dormant | unknown
    value_delta_pct: Optional[float] = None
    evidence_count: int = 0


# ── Idea contributions ──────────────────────────────────────────────


class IdeaContributionSummary(BaseModel):
    idea_id: str
    idea_title: str
    idea_status: str = "unknown"
    contribution_types: list[str] = Field(default_factory=list)
    cc_attributed: float = 0.0
    contribution_count: int = 0
    last_contributed_at: Optional[datetime] = None
    health: HealthSignal = Field(default_factory=HealthSignal)


class IdeaContributionsList(BaseModel):
    contributor_id: str
    total: int
    items: list[IdeaContributionSummary] = Field(default_factory=list)


class ContributionDetail(BaseModel):
    id: str
    type: str
    date: Optional[datetime] = None
    asset_id: Optional[str] = None
    cc_attributed: float = 0.0
    coherence_score: float = 0.0
    lineage_chain_id: Optional[str] = None


class LineageLinkBrief(BaseModel):
    """Subset of value-lineage link for portfolio audit drill-down."""

    id: str
    idea_id: str
    spec_id: str
    estimated_cost: float = 0.0


class ContributionLineageView(BaseModel):
    """Single contribution with optional linkage into the value-lineage ledger."""

    contributor_id: str
    contribution_id: str
    idea_id: str
    contribution_type: str = "unknown"
    cc_attributed: float = 0.0
    lineage_chain_id: Optional[str] = None
    value_lineage_link: Optional[LineageLinkBrief] = None
    lineage_resolution_note: Optional[str] = None


class ValueLineageSummary(BaseModel):
    lineage_id: Optional[str] = None
    total_value: float = 0.0
    roi_ratio: Optional[float] = None
    stage_events: int = 0


class IdeaContributionDrilldown(BaseModel):
    contributor_id: str
    idea_id: str
    idea_title: str
    contributions: list[ContributionDetail] = Field(default_factory=list)
    value_lineage_summary: ValueLineageSummary = Field(default_factory=ValueLineageSummary)


# ── Stakes ──────────────────────────────────────────────────────────


class StakeSummary(BaseModel):
    stake_id: str
    idea_id: str
    idea_title: str
    cc_staked: float
    cc_valuation: Optional[float] = None
    roi_pct: Optional[float] = None
    staked_at: Optional[datetime] = None
    last_valued_at: Optional[datetime] = None
    health: HealthSignal = Field(default_factory=HealthSignal)


class StakesList(BaseModel):
    contributor_id: str
    total: int
    items: list[StakeSummary] = Field(default_factory=list)


# ── Tasks ────────────────────────────────────────────────────────────


class TaskSummary(BaseModel):
    task_id: str
    description: str
    idea_id: Optional[str] = None
    idea_title: Optional[str] = None
    provider: Optional[str] = None
    outcome: Optional[str] = None  # passed | failed | partial
    cc_earned: float = 0.0
    completed_at: Optional[datetime] = None


class TasksList(BaseModel):
    contributor_id: str
    total: int
    items: list[TaskSummary] = Field(default_factory=list)
