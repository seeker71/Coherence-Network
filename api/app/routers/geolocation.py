"""Geolocation router — contributor location, nearby search, local news resonance."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.geolocation import (
    ContributorLocation,
    ContributorLocationSet,
    LocalNewsResonanceResponse,
    NearbyResult,
)
from app.models.error import ErrorDetail
from app.services import geolocation_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Contributor location endpoints
# ---------------------------------------------------------------------------


@router.patch(
    "/contributors/{contributor_id}/location",
    response_model=ContributorLocation,
    summary="Set contributor location (city-level)",
    responses={
        404: {"model": ErrorDetail, "description": "Contributor not found"},
        422: {"model": ErrorDetail, "description": "Validation error"},
    },
)
def set_location(contributor_id: str, payload: ContributorLocationSet) -> ContributorLocation:
    """Optionally share your city-level location.

    Coordinates are rounded to two decimal places (~1 km precision) so exact
    addresses are never stored. Visibility defaults to ``contributors_only``.
    """
    payload.latitude = round(payload.latitude, 2)
    payload.longitude = round(payload.longitude, 2)
    try:
        return geolocation_service.set_contributor_location(contributor_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/contributors/{contributor_id}/location",
    response_model=ContributorLocation,
    summary="Get contributor location",
    responses={
        404: {"model": ErrorDetail, "description": "Location not set or contributor not found"},
    },
)
def get_location(contributor_id: str) -> ContributorLocation:
    """Return the stored location for a contributor."""
    loc = geolocation_service.get_contributor_location(contributor_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="No location set for this contributor")
    return loc


@router.delete(
    "/contributors/{contributor_id}/location",
    status_code=204,
    summary="Remove contributor location",
    responses={
        404: {"model": ErrorDetail, "description": "Contributor not found"},
    },
)
def delete_location(contributor_id: str) -> None:
    """Opt out of location sharing — removes all stored location data."""
    removed = geolocation_service.delete_contributor_location(contributor_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")


# ---------------------------------------------------------------------------
# Nearby search
# ---------------------------------------------------------------------------


@router.get(
    "/nearby",
    response_model=NearbyResult,
    summary="Find nearby contributors and ideas",
)
def nearby(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Query latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Query longitude"),
    radius_km: float = Query(100.0, gt=0, le=20000, description="Search radius in km"),
    limit: int = Query(50, ge=1, le=200, description="Max results per category"),
) -> NearbyResult:
    """Return contributors and ideas within *radius_km* of the given coordinates.

    Only contributors with ``visibility`` set to ``public`` or
    ``contributors_only`` are returned. Exact coordinates are never exposed —
    only city name and approximate distance.
    """
    return geolocation_service.find_nearby(lat=lat, lon=lon, radius_km=radius_km, limit=limit)


# ---------------------------------------------------------------------------
# Local news resonance
# ---------------------------------------------------------------------------


@router.get(
    "/news/resonance/local",
    response_model=LocalNewsResonanceResponse,
    summary="News resonance for a location",
)
def local_news_resonance(
    location: str = Query(..., min_length=2, max_length=200, description="City or region name"),
    limit: int = Query(20, ge=1, le=100),
) -> LocalNewsResonanceResponse:
    """Return recent news items that match the given location.

    Resonance score (0–1) indicates how strongly the article text mentions
    the location keywords.
    """
    return geolocation_service.local_news_resonance(location=location, limit=limit)
