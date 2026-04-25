"""Pydantic models for CC Economics and Value Coherence (spec cc-economics-and-value-coherence).

Covers: supply reporting, exchange rate with spread, staking positions,
stake/unstake requests, and user staking summaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class CCSupply(BaseModel):
    """Current CC supply metrics with coherence score."""

    total_minted: float = Field(ge=0, description="Total CC ever minted")
    total_burned: float = Field(ge=0, description="Total CC ever burned")
    outstanding: float = Field(ge=0, description="CC currently outstanding (minted - burned)")
    treasury_value_usd: float = Field(ge=0, description="Treasury backing in USD")
    exchange_rate: float = Field(gt=0, description="Current CC per USD rate")
    coherence_score: float = Field(ge=0, description="treasury_value / (total_cc * exchange_rate)")
    coherence_status: str = Field(
        description="healthy (>=1.05), warning (1.0-1.05), paused (<1.0)"
    )
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CCExchangeRate(BaseModel):
    """Exchange rate response with spread and cache metadata."""

    cc_per_usd: float = Field(gt=0, description="Mid-market CC per USD")
    spread_pct: float = Field(ge=0, description="Spread percentage applied")
    buy_rate: float = Field(gt=0, description="Rate when buying CC (user gets fewer CC)")
    sell_rate: float = Field(gt=0, description="Rate when selling CC (user gets more CC)")
    oracle_source: str = Field(default="coingecko", description="Price oracle source")
    cached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_ttl_seconds: int = Field(default=300, gt=0, description="Cache TTL in seconds")
    is_stale: bool = Field(default=False, description="True if cache exceeded TTL")


class StakePosition(BaseModel):
    """A single staking position."""

    stake_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    idea_id: str = Field(min_length=1)
    amount_cc: float = Field(gt=0, description="Original staked amount")
    attribution_cc: float = Field(ge=0, description="Current attribution value")
    staked_at: datetime
    status: str = Field(description="active, cooling_down, or withdrawn")
    cooldown_hours: Optional[int] = Field(default=None)
    available_at: Optional[datetime] = Field(default=None)


class StakeRequest(BaseModel):
    """Request to stake CC into an idea."""

    user_id: str = Field(min_length=1)
    idea_id: str = Field(min_length=1)
    amount_cc: float = Field(gt=0)


class UnstakeRequest(BaseModel):
    """Request to unstake a position."""

    stake_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class UnstakeResponse(BaseModel):
    """Response after initiating unstake."""

    stake_id: str
    amount_cc: float
    attribution_cc: float
    cooldown_hours: int
    available_at: datetime
    status: str


class UserStakingSummary(BaseModel):
    """All staking positions for a user."""

    user_id: str
    positions: list[StakePosition] = Field(default_factory=list)
    total_staked_cc: float = Field(ge=0)
    total_attribution_cc: float = Field(ge=0)
