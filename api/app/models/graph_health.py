"""Pydantic models for Graph Health Monitoring (spec-172)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

SPEC_REF = "spec-172"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class GravityWell(BaseModel):
    concept_id: str
    child_count: int
    severity: str  # "warning" | "critical"


class OrphanCluster(BaseModel):
    cluster_id: str
    size: int
    members: list[str]


class SurfaceCandidate(BaseModel):
    concept_id: str
    potential_score: float = Field(ge=0.0, le=1.0)
    interaction_pct: float


class GraphSignal(BaseModel):
    id: str
    type: str  # split_signal | merge_signal | surface_signal | convergence_ok | health_report
    concept_id: Optional[str] = None
    cluster_id: Optional[str] = None
    severity: str  # info | warning | critical
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Snapshot model
# ---------------------------------------------------------------------------

class GraphHealthSnapshot(BaseModel):
    id: str
    computed_at: datetime
    balance_score: float = Field(ge=0.0, le=1.0)
    entropy_score: float = Field(ge=0.0, le=1.0)
    concentration_ratio: float = Field(ge=0.0, le=1.0)
    concept_count: int
    edge_count: int
    gravity_wells: list[GravityWell] = Field(default_factory=list)
    orphan_clusters: list[OrphanCluster] = Field(default_factory=list)
    surface_candidates: list[SurfaceCandidate] = Field(default_factory=list)
    signals: list[GraphSignal] = Field(default_factory=list)
    spec_ref: str = SPEC_REF


class GraphHealthHistoryResponse(BaseModel):
    items: list[GraphHealthSnapshot]
    total: int
    spec_ref: str = SPEC_REF


# ---------------------------------------------------------------------------
# Signal models
# ---------------------------------------------------------------------------

class SignalListResponse(BaseModel):
    signals: list[GraphSignal]
    total: int
    spec_ref: str = SPEC_REF


class SignalResolveRequest(BaseModel):
    resolution: str
    resolved_by: str


# ---------------------------------------------------------------------------
# Convergence guard models
# ---------------------------------------------------------------------------

class ConvergenceGuardRequest(BaseModel):
    reason: str
    set_by: str


class ConvergenceGuardResponse(BaseModel):
    concept_id: str
    convergence_guard: bool
    reason: Optional[str] = None
    set_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ROI model
# ---------------------------------------------------------------------------

class GraphHealthROI(BaseModel):
    period_days: int = 30
    balance_score_delta: float
    entropy_score_delta: float
    split_signals_actioned: int
    merge_signals_actioned: int
    surface_signals_actioned: int
    false_positive_rate: float
    convergence_guards_active: int
    note: Optional[str] = None
    spec_ref: str = SPEC_REF
