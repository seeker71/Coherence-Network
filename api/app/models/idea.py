"""Idea portfolio models for federated prioritization."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.coherence_credit import CostVector, ValueVector


class ManifestationStatus(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    VALIDATED = "validated"


class IdeaStage(str, Enum):
    NONE = "none"
    SPECCED = "specced"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    COMPLETE = "complete"


IDEA_STAGE_ORDER: list[IdeaStage] = [
    IdeaStage.NONE,
    IdeaStage.SPECCED,
    IdeaStage.IMPLEMENTING,
    IdeaStage.TESTING,
    IdeaStage.REVIEWING,
    IdeaStage.COMPLETE,
]


class IdeaType(str, Enum):
    SUPER = "super"           # Strategic goal; never picked up for direct work
    CHILD = "child"           # Actionable sub-idea; can be picked up
    STANDALONE = "standalone"  # No parent; backward compatible default


class IdeaQuestion(BaseModel):
    question: str = Field(min_length=1)
    value_to_whole: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    answer: Optional[str] = None
    measured_delta: Optional[float] = None


class IdeaQuestionCreate(BaseModel):
    question: str = Field(min_length=1)
    value_to_whole: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)


class Idea(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0)
    actual_value: float = Field(default=0.0, ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    actual_cost: float = Field(default=0.0, ge=0.0)
    resistance_risk: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    manifestation_status: ManifestationStatus = ManifestationStatus.NONE
    interfaces: list[str] = Field(default_factory=list)
    open_questions: list[IdeaQuestion] = Field(default_factory=list)
    idea_type: IdeaType = IdeaType.STANDALONE
    parent_idea_id: Optional[str] = None
    child_idea_ids: list[str] = Field(default_factory=list)
    stage: IdeaStage = IdeaStage.NONE
    value_basis: Optional[dict[str, str]] = Field(default=None, description="Human-readable rationale for each numeric field")
    cost_vector: Optional[CostVector] = None
    value_vector: Optional[ValueVector] = None
    tags: list[str] = Field(default_factory=list, description="Normalized slug tags for filtering and discovery")


class IdeaWithScore(Idea):
    free_energy_score: float = Field(ge=0.0)
    value_gap: float = Field(ge=0.0)
    marginal_cc_score: float = Field(default=0.0, ge=0.0)
    selection_weight: float = Field(
        default=0.0,
        ge=0.0,
        description="Probability weight for stochastic selection (sums to 1.0 across portfolio).",
    )
    remaining_cost_cc: float = Field(default=0.0, ge=0.0, description="Remaining CC to invest")
    value_gap_cc: float = Field(default=0.0, ge=0.0, description="Uncaptured CC value")
    roi_cc: float = Field(default=0.0, ge=0.0, description="Expected CC return per CC invested")


class IdeaSelectionResult(BaseModel):
    """Result of a weighted stochastic idea pick."""
    selected: IdeaWithScore
    method: str = Field(description="Selection method used: free_energy | marginal_cc")
    temperature: float = Field(description="Temperature used (0=deterministic, higher=more random)")
    selection_weight: float = Field(description="Probability this idea had of being picked")
    runner_up: Optional[IdeaWithScore] = None
    pool_size: int = Field(description="Number of ideas in the selection pool")


class IdeaSummary(BaseModel):
    total_ideas: int = Field(ge=0)
    unvalidated_ideas: int = Field(ge=0)
    validated_ideas: int = Field(ge=0)
    total_potential_value: float = Field(ge=0.0)
    total_actual_value: float = Field(ge=0.0)
    total_value_gap: float = Field(ge=0.0)


class IdeaCountByStatus(BaseModel):
    none: int = Field(ge=0)
    partial: int = Field(ge=0)
    validated: int = Field(ge=0)


class IdeaCountResponse(BaseModel):
    total: int = Field(ge=0)
    by_status: IdeaCountByStatus


class PaginationInfo(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    returned: int = Field(ge=0)
    has_more: bool = False


class IdeaPortfolioResponse(BaseModel):
    ideas: list[IdeaWithScore]
    summary: IdeaSummary
    pagination: PaginationInfo | None = None


class IdeaShowcaseBudget(BaseModel):
    estimated_cost_cc: float = Field(ge=0.0)
    spent_cost_cc: float = Field(ge=0.0)
    remaining_cost_cc: float = Field(ge=0.0)


class IdeaShowcaseItem(BaseModel):
    idea_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    clear_ask: str = Field(min_length=1)
    budget: IdeaShowcaseBudget
    early_proof: str = Field(min_length=1)
    current_status: ManifestationStatus


class IdeaShowcaseResponse(BaseModel):
    ideas: list[IdeaShowcaseItem]


class IdeaUpdate(BaseModel):
    """PATCH body per spec 053: only these four optional fields."""
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    manifestation_status: Optional[ManifestationStatus] = None
    stage: Optional[IdeaStage] = None


class IdeaCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    interfaces: list[str] = Field(default_factory=list)
    open_questions: list[IdeaQuestionCreate] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, description="Optional tags to attach at creation time")
    # Optional fields for full-fidelity seeding
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    resistance_risk: Optional[float] = Field(default=None, ge=0.0)
    idea_type: Optional[IdeaType] = None
    parent_idea_id: Optional[str] = None
    child_idea_ids: Optional[list[str]] = None
    manifestation_status: Optional[ManifestationStatus] = None
    stage: Optional[IdeaStage] = None
    value_basis: Optional[dict[str, str]] = None


class IdeaQuestionAnswerUpdate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    measured_delta: Optional[float] = None


class IdeaStorageInfo(BaseModel):
    backend: str = Field(min_length=1)
    database_url: str = Field(min_length=1)
    idea_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    bootstrap_source: str = Field(min_length=1)


class GovernanceHealth(BaseModel):
    """Portfolio governance effectiveness snapshot (spec 126)."""
    governance_score: float = Field(ge=0.0, le=1.0)
    throughput_rate: float = Field(ge=0.0, le=1.0)
    value_gap_trend: float = Field(description="Negative = improving")
    question_answer_rate: float = Field(ge=0.0, le=1.0)
    stale_ideas: list[str] = Field(default_factory=list)
    total_ideas: int = Field(ge=0)
    validated_ideas: int = Field(ge=0)
    snapshot_at: str = Field(description="ISO 8601 UTC timestamp")
    window_days: int = Field(default=30, ge=1)


class IdeaTaskStatusCounts(BaseModel):
    """Status breakdown for tasks of a given type."""
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    needs_decision: int = 0


class IdeaTaskGroup(BaseModel):
    """Tasks of a single type linked to an idea."""
    task_type: str
    count: int
    status_counts: IdeaTaskStatusCounts
    tasks: list[dict]


class IdeaTasksResponse(BaseModel):
    """All tasks linked to an idea, grouped by type."""
    idea_id: str
    total: int
    groups: list[IdeaTaskGroup]


class StageSetRequest(BaseModel):
    """Body for POST /api/ideas/{idea_id}/stage."""
    stage: IdeaStage


class StageBucket(BaseModel):
    count: int = 0
    idea_ids: list[str] = Field(default_factory=list)


class ProgressDashboard(BaseModel):
    total_ideas: int = 0
    completion_pct: float = 0.0
    by_stage: dict[str, StageBucket] = Field(default_factory=dict)
    snapshot_at: str = Field(description="ISO 8601 UTC timestamp")


# ── Tag models (spec 129) ─────────────────────────────────────────────────────


class IdeaTagUpdateRequest(BaseModel):
    """Request body for PUT /api/ideas/{idea_id}/tags."""
    tags: list[str] = Field(description="Full replacement tag set; normalized at write time")


class IdeaTagUpdateResponse(BaseModel):
    """Response body for PUT /api/ideas/{idea_id}/tags."""
    id: str
    tags: list[str]


class IdeaTagCatalogEntry(BaseModel):
    """Single entry in the tag catalog."""
    tag: str
    idea_count: int = Field(ge=1)


class IdeaTagCatalogResponse(BaseModel):
    """Response body for GET /api/ideas/tags."""
    tags: list[IdeaTagCatalogEntry]
