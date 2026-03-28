"""Pydantic models for graph health (fractal-self-balance / spec-172)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GravityWell(BaseModel):
    concept_id: str
    child_count: int = Field(ge=0)
    severity: Literal["warning", "critical"]


class OrphanCluster(BaseModel):
    cluster_id: str
    concept_ids: list[str]
    size: int = Field(ge=1)
    severity: Literal["warning", "critical"]


class SurfaceCandidate(BaseModel):
    concept_id: str
    reason: str
    score: float = Field(ge=0.0, le=1.0)


class GraphSignal(BaseModel):
    id: str
    type: Literal["split_signal", "merge_signal", "surface_signal", "convergence_ok"]
    concept_id: str | None = None
    cluster_id: str | None = None
    severity: Literal["info", "warning", "critical"]
    created_at: datetime
    resolved: bool = False


class GraphHealthSnapshot(BaseModel):
    balance_score: float = Field(ge=0.0, le=1.0)
    entropy_score: float = Field(ge=0.0, le=1.0)
    concentration_ratio: float = Field(ge=0.0, le=1.0)
    gravity_wells: list[GravityWell]
    orphan_clusters: list[OrphanCluster]
    surface_candidates: list[SurfaceCandidate]
    signals: list[GraphSignal]
    computed_at: datetime


class ConvergenceGuardBody(BaseModel):
    reason: str
    set_by: str


class ConvergenceGuardResponse(BaseModel):
    concept_id: str
    convergence_guard: bool
    reason: str = ""
    set_by: str = ""


class GraphHealthROI(BaseModel):
    balance_score_delta: float
    split_signals_actioned: int = Field(ge=0)
    merge_signals_actioned: int = Field(ge=0)
    surface_signals_actioned: int = Field(ge=0)
    spec_ref: str = "spec-172"
