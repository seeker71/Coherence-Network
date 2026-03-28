"""Response models for graph self-balance / fractal equilibrium (Spec 170)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SplitSignal(BaseModel):
    """A container node has too many hierarchical children — consider splitting."""

    node_id: str
    name: str
    node_type: str
    child_count: int
    reason: str = Field(
        description="Why this node triggered a split signal",
    )
    suggested_action: str = Field(
        description="Human-readable remediation hint",
    )


class MergeSuggestion(BaseModel):
    """Orphan nodes cluster together — consider merging or re-parenting."""

    node_ids: list[str]
    names: list[str]
    component_size: int
    reason: str
    suggested_action: str


class IdeaEnergyRow(BaseModel):
    idea_id: str
    name: str
    energy: float
    energy_share: float


class NeglectedBranch(BaseModel):
    idea_id: str
    name: str
    energy: float
    value_gap: float
    roi_cc: float
    reason: str


class EntropyReport(BaseModel):
    """Energy concentration across ideas — anti-collapse diversity signal."""

    total_ideas: int
    total_energy: float
    top3_energy_share: float
    concentration_alert: bool
    top_ideas: list[IdeaEnergyRow]
    neglected_branches: list[NeglectedBranch]
    shannon_entropy_normalized: float = Field(
        ge=0.0,
        le=1.0,
        description="1 = evenly spread, 0 = single idea dominates",
    )


class BalanceParameters(BaseModel):
    max_children: int
    concentration_threshold: float
    weak_degree_max: int = Field(
        default=2,
        description="Used internally for orphan edge analysis",
    )


class GraphBalanceReport(BaseModel):
    """Full equilibrium snapshot for GET /api/graph/balance."""

    split_signals: list[SplitSignal]
    merge_suggestions: list[MergeSuggestion]
    entropy: EntropyReport
    parameters: BalanceParameters
