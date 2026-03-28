"""Belief profile models — contributor worldview, axes, and concept preferences."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

DEFAULT_AXIS_KEYS = ("rigor", "empathy", "speed", "creativity", "collaboration", "systems")

Worldview = Literal[
    "scientific",
    "spiritual",
    "pragmatic",
    "holistic",
    "artistic",
    "systems",
]


class BeliefProfile(BaseModel):
    """Full belief profile returned by GET."""

    contributor_id: str = Field(min_length=1, description="Contributor UUID or name key")
    worldview: Worldview = "pragmatic"
    axes: dict[str, float] = Field(
        default_factory=dict,
        description="Axis label → weight 0..1 for radar visualization",
    )
    concepts: dict[str, float] = Field(
        default_factory=dict,
        description="Concept tag → preference weight 0..1",
    )

    @field_validator("axes", "concepts", mode="before")
    @classmethod
    def _coerce_floats(cls, v: object) -> dict[str, float]:
        if not isinstance(v, dict):
            return {}
        out: dict[str, float] = {}
        for k, val in v.items():
            if not isinstance(k, str) or not k.strip():
                continue
            try:
                fv = float(val)
            except (TypeError, ValueError):
                continue
            out[k.strip()] = max(0.0, min(1.0, fv))
        return out


class BeliefProfileUpdate(BaseModel):
    """Partial update for PATCH — omitted fields unchanged."""

    worldview: Worldview | None = None
    axes: dict[str, float] | None = None
    concepts: dict[str, float] | None = None

    @field_validator("axes", "concepts", mode="before")
    @classmethod
    def _optional_coerce(cls, v: object) -> dict[str, float] | None:
        if v is None:
            return None
        if not isinstance(v, dict):
            return {}
        out: dict[str, float] = {}
        for k, val in v.items():
            if not isinstance(k, str) or not k.strip():
                continue
            try:
                fv = float(val)
            except (TypeError, ValueError):
                continue
            out[k.strip()] = max(0.0, min(1.0, fv))
        return out


class BeliefResonanceScores(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    concept_overlap: float = Field(ge=0.0, le=1.0)
    worldview_fit: float = Field(ge=0.0, le=1.0)
    axis_alignment: float = Field(ge=0.0, le=1.0)


class BeliefResonanceResponse(BaseModel):
    contributor_id: str
    idea_id: str
    idea_name: str
    scores: BeliefResonanceScores
    matched_concepts: list[str] = Field(default_factory=list)
    notes: str = ""
