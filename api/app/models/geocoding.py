"""Models for forward geocoding and geographically filtered agent tasks."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class GeocodeSource(str, Enum):
    """Which provider produced the coordinates."""

    OPENCAGE = "opencage"
    NOMINATIM = "nominatim"
    FALLBACK = "fallback"


class GeocodeForwardResponse(BaseModel):
    """Response for GET /api/geocode/forward."""

    query: str
    found: bool
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    display_name: Optional[str] = None
    source: Optional[str] = None


class NearbyAgentTaskItem(BaseModel):
    """One agent task within the search radius."""

    task_id: str
    direction: str
    status: str
    task_type: Optional[str] = None
    distance_km: float = Field(..., ge=0.0)


class NearbyAgentTasksResponse(BaseModel):
    """Response for GET /api/geo/tasks/nearby."""

    tasks: list[NearbyAgentTaskItem] = []
    query_lat: float
    query_lon: float
    radius_km: float
    total: int
