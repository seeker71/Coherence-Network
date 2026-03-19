"""Coherence Credit (CC) — internal unit of account for the Coherence Network.

1 CC = cost of processing 1K tokens on the reference model.
All resource costs and values are denominated in CC with resource-type breakdowns.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class CostVector(BaseModel):
    """Breakdown of a CC cost amount by resource type."""
    total_cc: float = Field(ge=0.0, description="Total cost in Coherence Credits")
    compute_cc: float = Field(default=0.0, ge=0.0, description="LLM token processing cost")
    infrastructure_cc: float = Field(default=0.0, ge=0.0, description="Server/runtime cost")
    human_attention_cc: float = Field(default=0.0, ge=0.0, description="Human review/decision time")
    opportunity_cc: float = Field(default=0.0, ge=0.0, description="Delay/blocking cost")
    external_cc: float = Field(default=0.0, ge=0.0, description="Hard currency outflow")


class ValueVector(BaseModel):
    """Breakdown of a CC value amount by source type."""
    total_cc: float = Field(ge=0.0, description="Total value in Coherence Credits")
    adoption_cc: float = Field(default=0.0, ge=0.0, description="Value from usage/adoption")
    lineage_cc: float = Field(default=0.0, ge=0.0, description="Measured value from lineage pipeline")
    friction_avoided_cc: float = Field(default=0.0, ge=0.0, description="Value from unblocking work")
    revenue_cc: float = Field(default=0.0, ge=0.0, description="External revenue converted to CC")


class ProviderRate(BaseModel):
    """Cost rates for a specific compute provider in CC terms."""
    provider_id: str = Field(min_length=1)
    display_name: str = Field(default="")
    cc_per_1k_input: float = Field(ge=0.0, description="CC cost per 1K input tokens")
    cc_per_1k_output: float = Field(ge=0.0, description="CC cost per 1K output tokens")
    cc_per_second: float = Field(default=0.0, ge=0.0, description="CC cost per second of runtime")
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Quality from prompt A/B data")


class ExchangeRate(BaseModel):
    """Epoch-locked exchange rate between CC and external currencies."""
    epoch: str = Field(min_length=1, description="Rate epoch identifier, e.g. '2026-Q1'")
    cc_per_usd: float = Field(gt=0.0, description="How many CC per 1 USD")
    reference_model: str = Field(default="claude-sonnet-4-20250514", description="Model anchoring the CC definition")
    reference_rate_usd: float = Field(gt=0.0, description="USD cost per 1K tokens on reference model")
    human_hour_cc: float = Field(default=500.0, gt=0.0, description="CC value of 1 hour human attention")
    locked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = Field(default="")


class ExchangeRateConfig(BaseModel):
    """Full exchange rate configuration loaded from data/exchange_rates.json."""
    current_epoch: str = Field(min_length=1)
    rates: list[ExchangeRate] = Field(default_factory=list)
    providers: list[ProviderRate] = Field(default_factory=list)
