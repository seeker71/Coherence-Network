"""Marketplace models for the OpenClaw Idea Marketplace (spec 121)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class MarketplaceListing(BaseModel):
    """A published idea listing in the cross-instance marketplace."""

    listing_id: str = Field(description="Unique listing ID in format mkt_{uuid}")
    idea_id: str = Field(min_length=1)
    origin_instance_id: str = Field(min_length=1)
    author_id: str = Field(description="Format: {user}@{instance}")
    author_display_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0, default=0.0)
    confidence: float = Field(ge=0.3, le=1.0)
    tags: list[str] = Field(default_factory=list)
    content_hash: str = Field(description="SHA-256 hash of normalized name+description")
    visibility: str = Field(default="public", description="public or unlisted")
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fork_count: int = Field(default=0, ge=0)
    adoption_score: float = Field(default=0.0, ge=0.0)
    status: str = Field(default="active", description="active, archived, or flagged")


class MarketplaceFork(BaseModel):
    """A fork event linking a local idea to a marketplace listing."""

    fork_id: str = Field(description="Unique fork ID in format fork_{uuid}")
    local_idea_id: str = Field(min_length=1)
    forked_from_listing_id: str = Field(min_length=1)
    forked_from_idea_id: str = Field(min_length=1)
    forked_from_instance_id: str = Field(min_length=1)
    forked_by: str = Field(min_length=1)
    notes: str = Field(default="")
    forked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lineage_link_id: Optional[str] = Field(
        default=None,
        description="Value lineage link created for attribution",
    )


class AuthorReputation(BaseModel):
    """Computed reputation score for a marketplace author."""

    author_id: str = Field(min_length=1)
    reputation_score: float = Field(ge=0.0)
    total_publications: int = Field(ge=0)
    total_forks: int = Field(ge=0)
    total_adoption_cc: float = Field(ge=0.0)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublishRequest(BaseModel):
    """Request body for POST /api/marketplace/publish."""

    idea_id: str = Field(min_length=1, description="Existing local idea ID")
    tags: list[str] = Field(default_factory=list)
    author_display_name: str = Field(min_length=1)
    visibility: str = Field(default="public")


class ForkRequest(BaseModel):
    """Request body for POST /api/marketplace/fork/{listing_id}."""

    forker_id: str = Field(min_length=1)
    notes: str = Field(default="")


class BrowseResponse(BaseModel):
    """Paginated browse response."""

    listings: list[MarketplaceListing]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class QualityGateError(BaseModel):
    """A single field-level quality gate error."""

    field: str
    message: str


class PublishQualityGateResponse(BaseModel):
    """422 response body for quality gate failures."""

    detail: str = "Idea does not meet marketplace quality gate"
    errors: list[QualityGateError]


class DuplicateListingResponse(BaseModel):
    """409 response body for duplicate listing detection."""

    detail: str = "Duplicate listing exists"
    existing_listing_id: str


class MarketplaceManifest(BaseModel):
    """OpenClaw plugin manifest returned by GET /api/marketplace/manifest."""

    plugin_id: str = "coherence-network-marketplace"
    version: str = "1.0.0"
    name: str = "Coherence Network Idea Marketplace"
    capabilities: list[str] = Field(
        default_factory=lambda: ["publish", "browse", "fork", "reputation"]
    )
    required_permissions: list[str] = Field(
        default_factory=lambda: ["read:ideas", "write:ideas", "read:user_identity"]
    )
    endpoints: dict[str, str] = Field(
        default_factory=lambda: {
            "publish": "/api/marketplace/publish",
            "browse": "/api/marketplace/browse",
            "fork": "/api/marketplace/fork/{listing_id}",
            "reputation": "/api/marketplace/authors/{author_id}/reputation",
        }
    )
    webhooks: dict[str, str] = Field(
        default_factory=lambda: {
            "on_fork": "/api/marketplace/webhooks/fork",
            "on_adoption": "/api/marketplace/webhooks/adoption",
        }
    )
