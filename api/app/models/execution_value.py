"""Models for execution value and income proof surfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionValueSource(BaseModel):
    name: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionProofSummary(BaseModel):
    tasks_total: int = Field(ge=0)
    terminal_tasks: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    running: int = Field(ge=0)
    pending: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    p50_seconds: int = Field(ge=0)
    p95_seconds: int = Field(ge=0)
    runtime_backfill_count: int = Field(ge=0)


class IdeaValueSlice(BaseModel):
    idea_id: str
    measured_value_usd: float = Field(ge=0.0)
    measured_cost_usd: float = Field(ge=0.0)
    net_value_usd: float
    roi_ratio: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    grounding_sources: dict[str, Any] = Field(default_factory=dict)


class GroundedValueProofSummary(BaseModel):
    ideas_count: int = Field(ge=0)
    ideas_with_value: int = Field(ge=0)
    measured_value_usd: float = Field(ge=0.0)
    measured_cost_usd: float = Field(ge=0.0)
    net_value_usd: float
    roi_ratio: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    top_ideas: list[IdeaValueSlice] = Field(default_factory=list)


class IncomeProofSummary(BaseModel):
    paid_read_count: int = Field(ge=0)
    paid_asset_count: int = Field(ge=0)
    paid_read_cc: float = Field(ge=0.0)
    settled_cc: float = Field(ge=0.0)
    estimated_paid_read_usd: float | None = None
    cc_per_usd: float | None = None
    spendable_fiat_usd: float = Field(ge=0.0)
    income_proven: bool
    spendable_income_proven: bool
    proof_level: str
    offramp_status: str
    notes: list[str] = Field(default_factory=list)


class NutritionProofSummary(BaseModel):
    daily_nutrition_usd: float | None = None
    covered_days_by_spendable_fiat: float | None = None
    covered_days_by_estimated_cc: float | None = None
    can_cover_nutrition: bool | None = None


class ExecutionValueAnswer(BaseModel):
    can_generate_value_with_execution: bool
    can_prove_income: bool
    can_cover_nutrition: bool | None
    status: str
    healthiest_next_execution: str


class ExecutionValueProofResponse(BaseModel):
    generated_at: datetime
    window_days: int = Field(ge=1, le=90)
    answer: ExecutionValueAnswer
    execution: ExecutionProofSummary
    value: GroundedValueProofSummary
    income: IncomeProofSummary
    nutrition: NutritionProofSummary
    sources: list[ExecutionValueSource] = Field(default_factory=list)
