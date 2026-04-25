"""Belief system models — per-contributor worldview, interests, and concept preferences.

Implements: spec-169 (belief-system-interface)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BeliefAxis(str, Enum):
    scientific = "scientific"
    spiritual = "spiritual"
    pragmatic = "pragmatic"
    holistic = "holistic"
    relational = "relational"
    systemic = "systemic"


class ConceptResonance(BaseModel):
    concept_id: str = Field(..., min_length=1, description="ID of a concept node")
    weight: float = Field(..., ge=0.0, le=1.0, description="Resonance weight [0.0, 1.0]")


class BeliefProfile(BaseModel):
    contributor_id: str
    worldview_axes: Dict[str, float] = Field(default_factory=dict)
    concept_resonances: List[ConceptResonance] = Field(default_factory=list)
    interest_tags: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("worldview_axes")
    @classmethod
    def validate_worldview_axes(cls, v: Dict[str, float]) -> Dict[str, float]:
        valid_axes = {a.value for a in BeliefAxis}
        for axis, weight in v.items():
            if axis not in valid_axes:
                raise ValueError(f"worldview axis '{axis}' is not a valid BeliefAxis")
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"worldview axis '{axis}' weight {weight} must be between 0.0 and 1.0")
        return v


class BeliefPatch(BaseModel):
    """PATCH body — all fields optional. replace=False means additive."""

    model_config = {"extra": "forbid"}

    worldview_axes: Optional[Dict[str, float]] = None
    concept_resonances: Optional[List[ConceptResonance]] = None
    interest_tags: Optional[List[str]] = None
    replace: bool = Field(False, description="If true, replace lists instead of appending")

    @field_validator("worldview_axes")
    @classmethod
    def validate_worldview_axes(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v is None:
            return v
        valid_axes = {a.value for a in BeliefAxis}
        for axis, weight in v.items():
            if axis not in valid_axes:
                raise ValueError(f"worldview axis '{axis}' is not a valid BeliefAxis")
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"worldview axis '{axis}' weight {weight} must be between 0.0 and 1.0")
        return v


class ResonanceBreakdown(BaseModel):
    concept_overlap: float = Field(ge=0.0, le=1.0)
    worldview_alignment: float = Field(ge=0.0, le=1.0)
    tag_match: float = Field(ge=0.0, le=1.0)


class ResonanceResult(BaseModel):
    contributor_id: str
    idea_id: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    breakdown: ResonanceBreakdown
    matched_concepts: List[str] = Field(default_factory=list)
    matched_axes: List[str] = Field(default_factory=list)


class WorldviewAxisStat(BaseModel):
    axis: str
    avg_weight: float


class BeliefROI(BaseModel):
    contributors_with_profiles: int
    contributors_total: int
    profile_adoption_rate: float
    top_worldview_axes: List[WorldviewAxisStat]
    avg_resonance_match_rate: float
    concept_resonances_total: int
    spec_ref: str = "spec-169"
