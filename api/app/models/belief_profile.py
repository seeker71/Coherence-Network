"""Pydantic models for Belief System (spec-169).

Per-contributor worldview axes, concept resonances, and idea-matching models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BeliefAxis(str, Enum):
    scientific = "scientific"    # empirical, evidence-driven
    spiritual = "spiritual"      # meaning-oriented, transcendent
    pragmatic = "pragmatic"      # utility-first, solution-oriented
    holistic = "holistic"        # systems thinking, interconnectedness
    synthetic = "synthetic"      # integrative, bridge-builder
    critical = "critical"        # power-aware, deconstructive
    imaginative = "imaginative"  # speculative, futures-oriented


class ConceptResonance(BaseModel):
    concept_id: str
    concept_name: str
    score: float = Field(ge=0.0, le=1.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BeliefProfile(BaseModel):
    contributor_id: str
    worldview_axes: dict[str, float] = Field(default_factory=dict)
    concept_resonances: list[ConceptResonance] = Field(default_factory=list)
    tag_affinities: dict[str, float] = Field(default_factory=dict)
    primary_worldview: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("worldview_axes")
    @classmethod
    def validate_axes(cls, v: dict) -> dict:
        valid_axes = {a.value for a in BeliefAxis}
        for key, val in v.items():
            if key not in valid_axes:
                raise ValueError(f"'{key}' is not a valid BeliefAxis. Valid axes: {', '.join(sorted(valid_axes))}")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Axis value for '{key}' must be between 0.0 and 1.0, got {val}")
        return v

    @field_validator("primary_worldview")
    @classmethod
    def validate_primary_worldview(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_axes = {a.value for a in BeliefAxis}
            if v not in valid_axes:
                raise ValueError(f"'{v}' is not a valid BeliefAxis")
        return v


class BeliefProfilePatch(BaseModel):
    """Partial update model — only provided fields are updated."""
    worldview_axes: Optional[dict[str, float]] = None
    concept_resonances: Optional[list[ConceptResonance]] = None
    tag_affinities: Optional[dict[str, float]] = None
    primary_worldview: Optional[str] = None

    @field_validator("worldview_axes")
    @classmethod
    def validate_axes(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        valid_axes = {a.value for a in BeliefAxis}
        for key, val in v.items():
            if key not in valid_axes:
                raise ValueError(f"'{key}' is not a valid BeliefAxis. Valid axes: {', '.join(sorted(valid_axes))}")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Axis value for '{key}' must be between 0.0 and 1.0, got {val}")
        return v

    @field_validator("primary_worldview")
    @classmethod
    def validate_primary_worldview(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_axes = {a.value for a in BeliefAxis}
            if v not in valid_axes:
                raise ValueError(f"'{v}' is not a valid BeliefAxis")
        return v


class ResonanceResult(BaseModel):
    contributor_id: str
    idea_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    concept_overlap: float = Field(ge=0.0, le=1.0)
    worldview_alignment: float = Field(ge=0.0, le=1.0)
    tag_match: float = Field(ge=0.0, le=1.0)
    explanation: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class BeliefROI(BaseModel):
    contributor_id: str
    period_days: int = Field(ge=1)
    recommendations_shown: int = Field(ge=0)
    recommendations_engaged: int = Field(ge=0)
    engagement_rate: float = Field(ge=0.0)
    belief_completeness: float = Field(ge=0.0, le=1.0)
    baseline_engagement_rate: Optional[float] = None
    lift: Optional[float] = None
    note: Optional[str] = None
