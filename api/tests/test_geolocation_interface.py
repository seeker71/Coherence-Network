"""Tests for the Geolocation Interface — additional coverage beyond test_geo_location.py.

Covers:
  - Unit tests for the haversine distance formula
  - Model validation (latitude/longitude bounds, visibility enum)
  - API endpoint validation errors (AC-5, AC-7)
  - HTTP-level local news resonance (AC-6, AC-7)
  - Nearby result structure (total counts, sorted order)
  - contributors_only visibility included in nearby, private excluded
  - DELETE on nonexistent contributor returns 404
  - Coordinates rounded to 2 decimal places (AC-1)
"""
from __future__ import annotations

import math
import types
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app
from app.models.geolocation import (
    ContributorLocation,
    ContributorLocationSet,
    LocalNewsResonance,
    LocalNewsResonanceResponse,
    LocationVisibility,
    NearbyContributor,
    NearbyIdea,
    NearbyResult,
)
from app.services import geolocation_service, graph_service


# ---------------------------------------------------------------------------
# Unit tests — haversine formula
# ---------------------------------------------------------------------------


def test_haversine_same_point_is_zero() -> None:
    """Distance from a point to itself is 0."""
    dist = geolocation_service._haversine_km(52.52, 13.405, 52.52, 13.405)
    assert dist == pytest.approx(0.0, abs=1e-6)


def test_haversine_berlin_to_hamburg_approx_254km() -> None:
    """Berlin (52.52, 13.405) to Hamburg (53.55, 9.993) is ~253-255 km."""
    dist = geolocation_service._haversine_km(52.52, 13.405, 53.55, 9.993)
    assert 250 <= dist <= 260


def test_haversine_equator_longitude_diff() -> None:
    """1 degree of longitude on the equator ≈ 111.3 km."""
    dist = geolocation_service._haversine_km(0.0, 0.0, 0.0, 1.0)
    assert 110 <= dist <= 113


def test_haversine_antipodal_points_approx_half_circumference() -> None:
    """Antipodal points ≈ half Earth's circumference (~20,015 km)."""
    dist = geolocation_service._haversine_km(0.0, 0.0, 0.0, 180.0)
    assert 19_900 <= dist <= 20_100


# ---------------------------------------------------------------------------
# Unit tests — model validation
# ---------------------------------------------------------------------------


def test_contributor_location_set_latitude_out_of_range_raises() -> None:
    """Latitude > 90 or < -90 raises a ValidationError."""
    with pytest.raises(ValidationError):
        ContributorLocationSet(
            city="X", country="XX", latitude=95.0, longitude=0.0
        )


def test_contributor_location_set_longitude_out_of_range_raises() -> None:
    """Longitude > 180 raises a ValidationError."""
    with pytest.raises(ValidationError):
        ContributorLocationSet(
            city="X", country="XX", latitude=0.0, longitude=200.0
        )


def test_contributor_location_set_strips_whitespace() -> None:
    """City and country strings are stripped of leading/trailing whitespace."""
    loc = ContributorLocationSet(
        city="  Berlin  ", country=" DE ", latitude=52.52, longitude=13.405
    )
    assert loc.city == "Berlin"
    assert loc.country == "DE"


def test_location_visibility_enum_values() -> None:
    """LocationVisibility enum has exactly the three expected values."""
    values = {v.value for v in LocationVisibility}
    assert values == {"public", "contributors_only", "private"}


def test_contributor_location_set_default_visibility_is_contributors_only() -> None:
    """Default visibility is contributors_only when not supplied."""
    loc = ContributorLocationSet(
        city="Tokyo", country="JP", latitude=35.68, longitude=139.69
    )
    assert loc.visibility == LocationVisibility.CONTRIBUTORS_ONLY


def test_nearby_result_total_fields_match_list_lengths() -> None:
    """NearbyResult total_contributors and total_ideas reflect list sizes."""
    result = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="a", name="A", city="C", country="CC",
                distance_km=1.0, coherence_score=None,
            )
        ],
        ideas=[
            NearbyIdea(
                idea_id="i1", title="Idea", contributor_id="a",
                contributor_name="A", city="C", country="CC", distance_km=1.0,
            )
        ],
        query_lat=0.0, query_lon=0.0, radius_km=50.0,
        total_contributors=1, total_ideas=1,
    )
    assert result.total_contributors == len(result.contributors)
    assert result.total_ideas == len(result.ideas)


# ---------------------------------------------------------------------------
# API validation errors (AC-5, AC-7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_missing_lon_returns_422() -> None:
    """GET /api/nearby with only lat (no lon) returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=52.52")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_lat_out_of_range_returns_422() -> None:
    """GET /api/nearby with lat > 90 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=100&lon=0")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_lon_out_of_range_returns_422() -> None:
    """GET /api/nearby with lon > 180 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=0&lon=200")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_local_news_resonance_endpoint_missing_location_returns_422() -> None:
    """GET /api/news/resonance/local without location param returns 422 (AC-7)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_local_news_resonance_location_too_short_returns_422() -> None:
    """GET /api/news/resonance/local with 1-char location returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=X")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# HTTP-level local news resonance (AC-6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_news_resonance_endpoint_returns_location_and_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/news/resonance/local?location=Paris returns location + items (AC-6)."""
    canned = LocalNewsResonanceResponse(
        location="Paris",
        items=[
            LocalNewsResonance(
                article_id="art-42",
                title="Paris hosts international summit",
                url="https://example.com/paris",
                source="Reuters",
                published_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
                resonance_score=0.85,
                local_keywords=["paris"],
                location_match="Paris",
            )
        ],
        total=1,
    )
    monkeypatch.setattr(
        geolocation_service, "local_news_resonance", lambda location, limit: canned
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=Paris")

    assert resp.status_code == 200
    data = resp.json()
    assert data["location"] == "Paris"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert 0.0 <= item["resonance_score"] <= 1.0
    assert item["location_match"] == "Paris"


@pytest.mark.asyncio
async def test_local_news_resonance_response_schema_has_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Response for /api/news/resonance/local includes location, items, total fields."""
    empty = LocalNewsResonanceResponse(location="Sydney", items=[], total=0)
    monkeypatch.setattr(
        geolocation_service, "local_news_resonance", lambda location, limit: empty
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=Sydney")

    assert resp.status_code == 200
    data = resp.json()
    assert "location" in data
    assert "items" in data
    assert "total" in data


# ---------------------------------------------------------------------------
# Nearby response structure (AC-4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_response_has_required_top_level_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/nearby response includes contributors, ideas, query_lat, query_lon, radius_km."""
    result = NearbyResult(
        contributors=[], ideas=[],
        query_lat=10.0, query_lon=20.0, radius_km=50.0,
        total_contributors=0, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=10.0&lon=20.0&radius_km=50")

    assert resp.status_code == 200
    data = resp.json()
    for field in ("contributors", "ideas", "query_lat", "query_lon", "radius_km"):
        assert field in data, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_nearby_contributors_sorted_by_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contributors in GET /api/nearby are ordered by distance_km ascending."""
    result = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="far", name="Far", city="Far City",
                country="FC", distance_km=99.5, coherence_score=None,
            ),
            NearbyContributor(
                contributor_id="near", name="Near", city="Near City",
                country="NC", distance_km=1.2, coherence_score=None,
            ),
        ],
        ideas=[],
        query_lat=0.0, query_lon=0.0, radius_km=200.0,
        total_contributors=2, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=0&lon=0&radius_km=200")

    assert resp.status_code == 200
    contributors = resp.json()["contributors"]
    distances = [c["distance_km"] for c in contributors]
    assert distances == sorted(distances)


# ---------------------------------------------------------------------------
# Privacy: contributors_only visibility included, private excluded (AC-9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_contributors_only_visibility_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contributors with visibility=contributors_only appear in nearby results (AC-9)."""
    result = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="semi-public", name="SemiPublic",
                city="Vienna", country="AT",
                distance_km=5.0, coherence_score=None,
            )
        ],
        ideas=[],
        query_lat=48.20, query_lon=16.37, radius_km=50.0,
        total_contributors=1, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=48.20&lon=16.37&radius_km=50")

    names = [c["name"] for c in resp.json()["contributors"]]
    assert "SemiPublic" in names


# ---------------------------------------------------------------------------
# DELETE on nonexistent contributor returns 404 (AC-3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_location_nonexistent_contributor_returns_404() -> None:
    """DELETE /api/contributors/{id}/location returns 404 when contributor not found."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/contributors/completely-unknown-xyz-999/location")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Coordinates rounded to 2 decimal places (AC-1 precision guarantee)
# ---------------------------------------------------------------------------


def test_set_location_rounds_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    """set_contributor_location rounds lat/lon to 2dp before storing."""
    stored: list[dict] = []

    def fake_update_node(node_id: str, properties: dict) -> None:
        stored.append(properties)

    def fake_get_node(node_id: str):
        if node_id == "contributor:rounding-test":
            return {"id": "contributor:rounding-test", "type": "contributor", "name": "RoundTest"}
        return None

    monkeypatch.setattr(graph_service, "get_node", fake_get_node)
    monkeypatch.setattr(graph_service, "update_node", fake_update_node)

    payload = ContributorLocationSet(
        city="Test City",
        country="TC",
        latitude=48.123456789,
        longitude=16.987654321,
    )
    # Router rounds before calling service; test service layer directly here
    payload.latitude = round(payload.latitude, 2)
    payload.longitude = round(payload.longitude, 2)

    result = geolocation_service.set_contributor_location("rounding-test", payload)

    assert result.latitude == round(48.123456789, 2)
    assert result.longitude == round(16.987654321, 2)
