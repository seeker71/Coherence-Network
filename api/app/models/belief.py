"""Belief profile models — contributor worldview, axes, and concept preferences."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BeliefProfileResponse(BaseModel):
    contributor_id: str = Field(min_length=1)
    worldview: str = Field(min_length=1)
    axis_weights: dict[str, float] = Field(default_factory=dict)
    concept_weights: dict[str, float] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class BeliefProfileUpdate(BaseModel):
    worldview: Optional[str] = None
    axis_weights: Optional[dict[str, float]] = None
    concept_weights: Optional[dict[str, float]] = None


class BeliefResonanceResponse(BaseModel):
    contributor_id: str
    idea_id: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    concept_overlap: float = Field(ge=0.0, le=1.0)
    axis_alignment: float = Field(ge=0.0, le=1.0)
    worldview_alignment: float = Field(ge=0.0, le=1.0)
    matching_concepts: list[str] = Field(default_factory=list)
    idea_worldview_signal: str = Field(default="pragmatic")
