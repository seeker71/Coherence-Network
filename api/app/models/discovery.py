"""Discovery feed models — Serendipity Discovery service.

Pydantic models for the personalized discovery feed that combines
resonance signals from ideas, peers, news, and ontology into a
unified "what resonates with who you are" experience.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoveryItem(BaseModel):
    kind: str = Field(
        ...,
        description="Type of discovery item: resonant_idea, resonant_peer, cross_domain, resonant_news, growth_edge",
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Resonance/relevance score")
    title: str
    summary: str
    entity_id: str = Field(..., description="ID of the underlying entity (idea, contributor, news, etc.)")
    entity_type: str = Field(..., description="Entity kind: idea, contributor, news, edge")
    reason: str = Field(..., description="Human-readable explanation of why this appeared")
    tags: list[str] = Field(default_factory=list)
    links: dict = Field(default_factory=dict, description="Web paths for navigation")


class DiscoveryFeed(BaseModel):
    contributor_id: str
    items: list[DiscoveryItem]
    total: int
    generated_at: str = Field(..., description="ISO 8601 UTC timestamp")
    profile_summary: dict = Field(
        default_factory=dict,
        description="Contributor's top axes and interests",
    )
