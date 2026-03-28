"""Belief profile models — per-contributor worldview, concepts, and value axes."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Curated worldviews (extensible strings; UI offers these defaults)
WORLDVIEW_CHOICES = (
    "scientific",
    "spiritual",
    "pragmatic",
    "holistic",
    "integrative",
    "speculative",
)

# Default radar axes (0–1): how strongly the contributor weights each lens
DEFAULT_AXIS_KEYS = (
    "empirical",
    "systemic",
    "humanistic",
    "technical",
    "intuitive",
    "pragmatic",
)


def default_axis_values() -> dict[str, float]:
    return {k: 0.5 for k in DEFAULT_AXIS_KEYS}


class BeliefProfile(BaseModel):
    """Full belief profile returned by GET."""

    contributor_id: str = Field(min_length=1)
    worldview: str = Field(default="pragmatic", description="Primary lens for interpreting ideas")
    concept_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Concept tag → resonance weight 0–1",
    )
    axis_values: dict[str, float] = Field(
        default_factory=default_axis_values,
        description="Radar axes: empirical, systemic, humanistic, … each 0–1",
    )

    @field_validator("concept_weights")
    @classmethod
    def _clamp_concepts(cls, v: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, val in v.items():
            k = key.strip().lower().replace(" ", "-")
            if not k:
                continue
            out[k] = max(0.0, min(1.0, float(val)))
        return out

    @field_validator("axis_values")
    @classmethod
    def _clamp_axes(cls, v: dict[str, float]) -> dict[str, float]:
        base = default_axis_values()
        for key, val in v.items():
            k = key.strip().lower().replace(" ", "-")
            if not k:
                continue
            base[k] = max(0.0, min(1.0, float(val)))
        return base


class BeliefProfileUpdate(BaseModel):
    """Partial update for PATCH."""

    worldview: Optional[str] = None
    concept_weights: Optional[dict[str, float]] = None
    axis_values: Optional[dict[str, float]] = None


class BeliefResonanceBreakdown(BaseModel):
    concept_alignment: float = Field(ge=0.0, le=1.0)
    worldview_alignment: float = Field(ge=0.0, le=1.0)
    axis_alignment: float = Field(ge=0.0, le=1.0)


class BeliefResonanceResponse(BaseModel):
    contributor_id: str
    idea_id: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    breakdown: BeliefResonanceBreakdown
    matched_concepts: list[str] = Field(default_factory=list)
