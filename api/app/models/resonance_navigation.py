"""Pydantic models for resonance-based discovery (spec 166)."""

from __future__ import annotations

from pydantic import BaseModel, Field


AXIS_KEYS = (
    "curiosity",
    "serendipity",
    "depth",
    "coherence_affinity",
    "recency",
)


class ResonanceAxes(BaseModel):
    """Desired discovery state; each axis is in [0.0, 1.0]."""

    curiosity: float = Field(default=0.5, ge=0.0, le=1.0)
    serendipity: float = Field(default=0.5, ge=0.0, le=1.0)
    depth: float = Field(default=0.5, ge=0.0, le=1.0)
    coherence_affinity: float = Field(default=0.5, ge=0.0, le=1.0)
    recency: float = Field(default=0.5, ge=0.0, le=1.0)


class ResonanceDiscoveryRequest(BaseModel):
    """POST /api/discovery/resonance body."""

    axes: ResonanceAxes = Field(default_factory=ResonanceAxes)
    axis_weights: dict[str, float] | None = Field(
        default=None,
        description="Optional per-axis weights (default 1.0). Keys subset of resonance axes.",
    )
    contributor_id: str | None = Field(
        default=None,
        description="When set, serendipity uses distance from this contributor's recent idea keywords.",
    )
    limit: int = Field(default=20, ge=1, le=100)
    include_internal: bool = Field(default=False)
    include_graph: bool = Field(default=True, description="Include related graph nodes and edges for top hits.")


class ResonanceIdeaHit(BaseModel):
    idea: dict
    resonance_score: float = Field(ge=0.0, le=1.0)
    axis_profile: dict[str, float]


class ResonanceDiscoveryResponse(BaseModel):
    requested_axes: dict[str, float]
    ideas: list[ResonanceIdeaHit]
    nodes: list[dict] = Field(default_factory=list)
    connections: list[dict] = Field(default_factory=list)
