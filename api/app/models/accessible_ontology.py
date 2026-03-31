"""Models for accessible ontology — non-technical contributor workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PlainLanguageContribution(BaseModel):
    """A plain-language concept submission from a non-technical contributor."""

    plain_text: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The concept described in plain language",
        examples=["Water flows downhill because of gravity and seeks balance"],
    )
    contributor_id: str = Field(
        default="anonymous",
        description="Contributor identifier (username, email, or 'anonymous')",
    )
    domains: list[str] = Field(
        default_factory=list,
        description="Domains the contributor knows (e.g. ['music', 'ecology', 'cooking'])",
        max_length=20,
    )
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional short title; inferred from plain_text if omitted",
    )
    view_preference: str = Field(
        default="garden",
        description="How contributor prefers to see ontology: 'garden', 'cards', 'graph'",
        pattern="^(garden|cards|graph)$",
    )


class OntologyConceptPatch(BaseModel):
    """Patch an accessible ontology concept."""

    title: str | None = None
    plain_text: str | None = None
    domains: list[str] | None = None
    status: str | None = Field(
        default=None,
        pattern="^(pending|placed|orphan)$",
        description="Placement status: pending=not yet placed, placed=in graph, orphan=no fit found",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class InferredRelationship(BaseModel):
    """A relationship inferred by the system between two ontology concepts."""

    concept_id: str
    concept_name: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class AccessibleConceptResponse(BaseModel):
    """Full response for an accessible ontology concept."""

    id: str
    title: str
    plain_text: str
    contributor_id: str
    domains: list[str]
    status: str  # pending | placed | orphan
    inferred_relationships: list[InferredRelationship]
    garden_position: dict[str, Any]  # x, y, cluster
    core_concept_match: str | None  # ID of best-matching core concept
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class GardenView(BaseModel):
    """Garden-view aggregation of accessible ontology concepts."""

    clusters: list[dict[str, Any]]
    concepts: list[dict[str, Any]]
    total: int
    contributor_count: int
    domain_count: int
    placement_rate: float = Field(ge=0.0, le=1.0, description="Fraction of concepts placed in graph")


class OntologyContributionStats(BaseModel):
    """Statistics proving the feature is working."""

    total_contributions: int
    placed_count: int
    pending_count: int
    orphan_count: int
    placement_rate: float
    top_domains: list[dict[str, Any]]
    recent_contributors: list[str]
    inferred_edges_count: int
