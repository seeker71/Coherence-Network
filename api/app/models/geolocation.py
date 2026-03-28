"""Geolocation models — city-level privacy-first contributor location sharing."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationVisibility(str, Enum):
    PUBLIC = "public"
    CONTRIBUTORS_ONLY = "contributors_only"
    PRIVATE = "private"


class ContributorLocationSet(BaseModel):
    """Request body to set/update a contributor's location."""
    city: str = Field(..., min_length=1, max_length=100, description="City name (e.g. 'São Paulo')")
    region: Optional[str] = Field(None, max_length=100, description="State or region (optional)")
    country: str = Field(..., min_length=2, max_length=100, description="Country name or ISO code")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Approximate city-center latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Approximate city-center longitude")
    visibility: LocationVisibility = Field(
        LocationVisibility.CONTRIBUTORS_ONLY,
        description="Who can see this location",
    )

    @field_validator("city", "country", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ContributorLocation(BaseModel):
    """Stored location for a contributor."""
    contributor_id: str
    city: str
    region: Optional[str] = None
    country: str
    latitude: float
    longitude: float
    visibility: LocationVisibility = LocationVisibility.CONTRIBUTORS_ONLY
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class NearbyContributor(BaseModel):
    """A contributor returned in a nearby search."""
    contributor_id: str
    name: str
    city: str
    country: str
    distance_km: float = Field(..., description="Approximate distance in km from query point")
    coherence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class NearbyIdea(BaseModel):
    """An idea associated with a nearby contributor."""
    idea_id: str
    title: str
    contributor_id: str
    contributor_name: str
    city: str
    country: str
    distance_km: float


class NearbyResult(BaseModel):
    """Combined response for /api/nearby."""
    contributors: list[NearbyContributor] = []
    ideas: list[NearbyIdea] = []
    query_lat: float
    query_lon: float
    radius_km: float
    total_contributors: int
    total_ideas: int


class LocalNewsResonance(BaseModel):
    """News item with local resonance score."""
    article_id: str
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    resonance_score: float = Field(..., ge=0.0, le=1.0)
    local_keywords: list[str] = []
    location_match: str = Field(..., description="Location that matched (city or country)")


class LocalNewsResonanceResponse(BaseModel):
    """Response for /api/news/resonance/local."""
    location: str
    items: list[LocalNewsResonance] = []
    total: int
