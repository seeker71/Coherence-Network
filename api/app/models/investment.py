"""Investment models — positions, portfolio, time pledges, history events.

Universal shape: a Position holds idea_id, contributor_id, cc_staked,
time_pledged_cc_equivalent, current_value, and computed roi. The preview,
portfolio listing, and history endpoints are all projections of this same
underlying position state.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Projections (computed views over ledger + idea state)
# ---------------------------------------------------------------------------


class InvestPreviewProjections(BaseModel):
    """ROI projection range for an idea, surfaced before stake confirmation."""
    low_multiplier: float = Field(ge=0.0)
    high_multiplier: float = Field(ge=0.0)
    basis: str


class InvestPreview(BaseModel):
    """ROI projection returned by GET /api/ideas/{idea_id}/invest-preview."""
    idea_id: str
    idea_name: str
    stage: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    total_cc_staked: float = Field(ge=0.0)
    prior_investments_count: int = Field(ge=0)
    prior_roi_avg: float = Field(ge=0.0)
    projections: InvestPreviewProjections
    stage_unlock_pct: int = Field(ge=0, le=100)
    pipeline_velocity_days: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Positions and portfolio
# ---------------------------------------------------------------------------


class InvestmentPosition(BaseModel):
    """A single contributor's position in one idea."""
    idea_id: str
    idea_name: str
    invested_cc: float = Field(ge=0.0)
    current_value_cc: float = Field(ge=0.0)
    gain_loss_cc: float
    roi_pct: float
    stage: str
    unlock_pct: int = Field(ge=0, le=100)
    staked_at: Optional[str] = None


class PortfolioSummary(BaseModel):
    total_invested_cc: float = Field(ge=0.0)
    total_current_value_cc: float = Field(ge=0.0)
    total_gain_loss_cc: float
    total_positions: int = Field(ge=0)
    active_positions: int = Field(ge=0)


class Portfolio(BaseModel):
    """Returned by GET /api/contributors/{id}/investments."""
    contributor_id: str
    summary: PortfolioSummary
    positions: list[InvestmentPosition]


# ---------------------------------------------------------------------------
# History timeline
# ---------------------------------------------------------------------------


class InvestmentEvent(BaseModel):
    """One CC flow event for the history timeline."""
    event_id: str
    event_type: str  # stake | return | compute | pledge | fulfill
    idea_id: Optional[str] = None
    amount_cc: float
    recorded_at: str
    metadata: dict = Field(default_factory=dict)


class InvestmentHistory(BaseModel):
    contributor_id: str
    events: list[InvestmentEvent]


# ---------------------------------------------------------------------------
# Time pledge
# ---------------------------------------------------------------------------


class TimePledgeCreate(BaseModel):
    idea_id: str
    hours_pledged: float = Field(gt=0.0)
    pledge_type: str = "review"


class TimePledge(BaseModel):
    pledge_id: str
    contributor_id: str
    idea_id: str
    hours_pledged: float
    pledge_type: str
    cc_equivalent: float
    cc_per_hour_rate: float
    status: str  # pending | fulfilled | expired
    created_at: str
    expires_at: str
    fulfilled_at: Optional[str] = None
    contribution_id: Optional[str] = None
    evidence_url: Optional[str] = None


class TimePledgeList(BaseModel):
    contributor_id: str
    pledges: list[TimePledge]


class TimePledgeFulfill(BaseModel):
    contribution_id: str
    evidence_url: Optional[str] = None
