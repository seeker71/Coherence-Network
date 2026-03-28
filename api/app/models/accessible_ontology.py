"""Models for accessible ontology — non-technical contributor workflow."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class PlainLanguageContribution(BaseModel):
    """A plain-language concept submission from a non-technical contributor."""

    plain_text: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The concept described in plain language",
    )
    contributor_id: str = Field(
        default="anonymous",
        description="Contributor identifier",
    )
    domains: list[str] = Field(
        default_factory=list,
        description="Domains the contributor knows",
    )
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional short title; inferred if omitted",
    )
    view_preference: str = Field(
        default="garden",
        description="garden | cards | graph",
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
    )


class InferredRelationship(BaseModel):
    concept_id: str
    concept_name: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class OntologyContributionStats(BaseModel):
    total_contributions: int
    placed_count: int
    pending_count: int
    orphan_count: int
    placement_rate: float
    top_domains: list[dict[str, Any]]
    recent_contributors: list[str]
    inferred_edges_count: int
