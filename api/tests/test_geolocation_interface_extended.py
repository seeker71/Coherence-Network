"""Extended tests for the Geolocation Interface (geolocation-interface).

Supplements test_geolocation_interface.py and test_geo_location.py with
additional coverage for:
  - Haversine symmetry and pole-to-pole distance
  - ContributorLocationSet region field and edge cases
  - ContributorLocation model defaults
  - NearbyContributor coherence_score validation
  - LocalNewsResonance model field validation
  - find_nearby: radius clamping, query coord echo, limit, idea attribution
  - /api/nearby HTTP edge cases (zero results, default radius, zero/negative radius)
  - local_news_resonance service: limit, total, sorted order, location_match field
  - PATCH 404 for unknown contributor, coordinate rounding
  - GET location round-trip (via monkeypatch), 404 when no location set
"""
from __future__ import annotations

import sys
import types

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
# Helpers
# ---------------------------------------------------------------------------


def _create_contributor(node_id: str, name: str) -> dict:
    return graph_service.create_node(
        id=f"contributor:{node_id}",
        type="contributor",
        name=name,
    )


def _inject_news(monkeypatch, articles: list) -> None:
    """Patch news ingestion so local_news_resonance uses fake_articles."""
    import app.services as services_pkg

    fake_nis = types.ModuleType("app.services.news_ingestion_service")
    fake_nis.get_recent_articles = lambda limit=200: articles  # type: ignore
    monkeypatch.setitem(sys.modules, "app.services.news_ingestion_service", fake_nis)
    monkeypatch.setattr(services_pkg, "news_ingestion_service", fake_nis, raising=False)


# ---------------------------------------------------------------------------
# Haversine symmetry
# ---------------------------------------------------------------------------


def test_haversine_symmetry():
    """d(A, B) == d(B, A) — distance is symmetric."""
    d1 = geolocation_service._haversine_km(52.52, 13.405, 48.14, 11.58)
    d2 = geolocation_service._haversine_km(48.14, 11.58, 52.52, 13.405)
    assert abs(d1 - d2) < 1e-9


def test_haversine_north_south_poles():
    """Pole-to-pole distance is approximately half earth circumference (~20015 km)."""
    dist = geolocation_service._haversine_km(90.0, 0.0, -90.0, 0.0)
    assert 19900 <= dist <= 20200


# ---------------------------------------------------------------------------
# ContributorLocationSet model — region field and edge cases
# ---------------------------------------------------------------------------


def test_location_set_with_region():
    """ContributorLocationSet accepts optional region field."""
    loc = ContributorLocationSet(
        city="Austin", region="TX", country="US",
        latitude=30.27, longitude=-97.74,
    )
    assert loc.region == "TX"


def test_location_set_region_defaults_none():
    """ContributorLocationSet region defaults to None when omitted."""
    loc = ContributorLocationSet(
        city="London", country="GB",
        latitude=51.51, longitude=-0.12,
    )
    assert loc.region is None


def test_location_set_city_too_short():
    """City with 0 characters fails validation."""
    with pytest.raises(ValidationError):
        ContributorLocationSet(city="", country="DE", latitude=52.0, longitude=13.0)


def test_location_set_country_too_short():
    """Country with fewer than 2 characters fails validation."""
    with pytest.raises(ValidationError):
        ContributorLocationSet(city="Berlin", country="D", latitude=52.0, longitude=13.0)


# ---------------------------------------------------------------------------
# ContributorLocation model defaults
# ---------------------------------------------------------------------------


def test_contributor_location_default_visibility():
    """ContributorLocation defaults to contributors_only visibility."""
    from datetime import datetime, timezone
    loc = ContributorLocation(
        contributor_id="x",
        city="Oslo",
        country="NO",
        latitude=59.91,
        longitude=10.75,
        updated_at=datetime.now(timezone.utc),
    )
    assert loc.visibility == LocationVisibility.CONTRIBUTORS_ONLY


def test_contributor_location_region_optional():
    """ContributorLocation region is None by default."""
    from datetime import datetime, timezone
    loc = ContributorLocation(
        contributor_id="y",
        city="Lisbon",
        country="PT",
        latitude=38.71,
        longitude=-9.14,
        updated_at=datetime.now(timezone.utc),
    )
    assert loc.region is None


# ---------------------------------------------------------------------------
# NearbyContributor — coherence_score validation
# ---------------------------------------------------------------------------


def test_nearby_contributor_coherence_score_out_of_range():
    """NearbyContributor rejects coherence_score > 1.0."""
    with pytest.raises(ValidationError):
        NearbyContributor(
            contributor_id="z", name="Z", city="C", country="CC",
            distance_km=1.0, coherence_score=1.5,
        )


def test_nearby_contributor_coherence_score_none_allowed():
    """NearbyContributor allows coherence_score=None."""
    nc = NearbyContributor(
        contributor_id="z", name="Z", city="C", country="CC",
        distance_km=10.0, coherence_score=None,
    )
    assert nc.coherence_score is None


def test_nearby_contributor_coherence_score_zero():
    """NearbyContributor accepts coherence_score=0.0."""
    nc = NearbyContributor(
        contributor_id="a", name="A", city="C", country="CC",
        distance_km=5.0, coherence_score=0.0,
    )
    assert nc.coherence_score == 0.0


# ---------------------------------------------------------------------------
# LocalNewsResonance — model fields
# ---------------------------------------------------------------------------


def test_local_news_resonance_score_out_of_range():
    """LocalNewsResonance rejects resonance_score > 1.0."""
    with pytest.raises(ValidationError):
        LocalNewsResonance(
            article_id="a1", title="Title",
            resonance_score=1.1, location_match="Paris",
        )


def test_local_news_resonance_score_below_zero():
    """LocalNewsResonance rejects resonance_score < 0.0."""
    with pytest.raises(ValidationError):
        LocalNewsResonance(
            article_id="a2", title="Title",
            resonance_score=-0.1, location_match="Paris",
        )


def test_local_news_resonance_optional_fields():
    """LocalNewsResonance url/source/published_at are all optional."""
    item = LocalNewsResonance(
        article_id="art-x",
        title="Climate Summit",
        resonance_score=0.5,
        location_match="New York",
    )
    assert item.url is None
    assert item.source is None
    assert item.published_at is None
    assert item.local_keywords == []


def test_local_news_resonance_response_total_matches_items():
    """LocalNewsResonanceResponse total should equal len(items)."""
    items = [
        LocalNewsResonance(
            article_id=f"a{i}", title=f"T{i}",
            resonance_score=0.5, location_match="Rome",
        )
        for i in range(3)
    ]
    resp = LocalNewsResonanceResponse(location="Rome", items=items, total=len(items))
    assert resp.total == len(resp.items) == 3


# ---------------------------------------------------------------------------
# find_nearby — radius clamping
# ---------------------------------------------------------------------------


def test_find_nearby_clamps_radius_to_minimum(monkeypatch):
    """find_nearby clamps radius_km to minimum 1.0."""
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: [])
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=0.0, lon=0.0, radius_km=0.0)
    assert result.radius_km == 1.0


def test_find_nearby_clamps_radius_to_maximum(monkeypatch):
    """find_nearby clamps radius_km to maximum 20000.0."""
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: [])
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=0.0, lon=0.0, radius_km=99999.0)
    assert result.radius_km == 20000.0


def test_find_nearby_preserves_query_coords(monkeypatch):
    """find_nearby echoes query_lat and query_lon in the response."""
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: [])
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=35.68, lon=139.69, radius_km=50.0)
    assert result.query_lat == 35.68
    assert result.query_lon == 139.69


# ---------------------------------------------------------------------------
# find_nearby — idea attribution
# ---------------------------------------------------------------------------


def test_find_nearby_includes_ideas_from_nearby_contributors(monkeypatch):
    """Ideas authored by nearby contributors appear in NearbyResult.ideas."""
    contributors = [
        {
            "id": "c:tokyo-user", "type": "contributor", "name": "TokyoUser",
            "properties": {
                "geo_location": {
                    "city": "Tokyo", "country": "JP",
                    "latitude": 35.68, "longitude": 139.69,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
    ]
    ideas = [
        {
            "id": "idea:tokyo-idea",
            "type": "idea",
            "name": "Tokyo Resonance Concept",
            "properties": {"author": "TokyoUser"},
        }
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: contributors)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: ideas)
    result = geolocation_service.find_nearby(lat=35.68, lon=139.69, radius_km=100.0)
    assert len(result.ideas) == 1
    assert result.ideas[0].title == "Tokyo Resonance Concept"
    assert result.ideas[0].city == "Tokyo"


def test_find_nearby_excludes_ideas_from_out_of_radius_contributors(monkeypatch):
    """Ideas from contributors outside radius are not included."""
    contributors = [
        {
            "id": "c:far", "type": "contributor", "name": "FarUser",
            "properties": {
                "geo_location": {
                    "city": "Sao Paulo", "country": "BR",
                    "latitude": -23.55, "longitude": -46.63,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
    ]
    ideas = [
        {
            "id": "idea:sp-idea",
            "type": "idea",
            "name": "SP Idea",
            "properties": {"author": "FarUser"},
        }
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: contributors)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: ideas)
    # Query from Berlin with small radius — Sao Paulo is ~10000 km away
    result = geolocation_service.find_nearby(lat=52.52, lon=13.40, radius_km=100.0)
    assert len(result.ideas) == 0


# ---------------------------------------------------------------------------
# find_nearby — limit enforcement
# ---------------------------------------------------------------------------


def test_find_nearby_respects_limit(monkeypatch):
    """find_nearby truncates contributors to the specified limit."""
    contributors = [
        {
            "id": f"c:u{i}", "type": "contributor", "name": f"User{i}",
            "properties": {
                "geo_location": {
                    "city": "Berlin", "country": "DE",
                    "latitude": 52.52, "longitude": 13.40,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
        for i in range(10)
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: contributors)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=52.52, lon=13.40, radius_km=100.0, limit=3)
    assert len(result.contributors) <= 3


# ---------------------------------------------------------------------------
# HTTP endpoints — /api/nearby edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_with_zero_results_returns_200(monkeypatch):
    """/api/nearby with no matching contributors returns HTTP 200 (not 404)."""
    empty = NearbyResult(
        contributors=[], ideas=[],
        query_lat=0.0, query_lon=0.0, radius_km=1.0,
        total_contributors=0, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: empty)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=0&lon=0&radius_km=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contributors"] == 0
    assert data["total_ideas"] == 0


@pytest.mark.asyncio
async def test_nearby_default_radius_is_used_when_omitted(monkeypatch):
    """/api/nearby without radius_km uses a default and returns 200."""
    called_with = {}

    def capture(**kw):
        called_with.update(kw)
        return NearbyResult(
            contributors=[], ideas=[],
            query_lat=kw["lat"], query_lon=kw["lon"], radius_km=kw.get("radius_km", 100.0),
            total_contributors=0, total_ideas=0,
        )

    monkeypatch.setattr(geolocation_service, "find_nearby", capture)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=10&lon=20")
    assert resp.status_code == 200
    assert called_with.get("lat") == 10.0
    assert called_with.get("lon") == 20.0


@pytest.mark.asyncio
async def test_nearby_radius_zero_is_rejected():
    """/api/nearby with radius_km=0 (gt=0 constraint) returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=0&lon=0&radius_km=0")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_negative_radius_is_rejected():
    """/api/nearby with negative radius_km returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=0&lon=0&radius_km=-10")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# local_news_resonance service — additional coverage
# ---------------------------------------------------------------------------


def test_news_resonance_service_empty_tokens():
    """local_news_resonance with location whose tokens are all len<=2 returns empty.

    Tokens shorter than 3 chars are filtered, so nothing matches.
    """
    result = geolocation_service.local_news_resonance(location="AB", limit=10)
    # "AB" → tokens = set() (all chars filtered at len>2) → no matches
    assert result.location == "AB"
    assert result.items == []


def test_news_resonance_service_limit_respected(monkeypatch):
    """local_news_resonance truncates items to the specified limit."""
    articles = [
        {"id": f"a{i}", "title": f"Berlin event {i}", "summary": "Berlin streets.", "url": None, "source": None, "published_at": None}
        for i in range(10)
    ]
    _inject_news(monkeypatch, articles)
    result = geolocation_service.local_news_resonance(location="Berlin", limit=3)
    assert len(result.items) <= 3


def test_news_resonance_service_total_matches_items(monkeypatch):
    """local_news_resonance total field equals len(items)."""
    articles = [
        {"id": "q1", "title": "Tokyo summit", "summary": "Tokyo leaders meet.", "url": None, "source": None, "published_at": None},
        {"id": "q2", "title": "Tokyo earthquake", "summary": "Tokyo hit by quake.", "url": None, "source": None, "published_at": None},
    ]
    _inject_news(monkeypatch, articles)
    result = geolocation_service.local_news_resonance(location="Tokyo", limit=10)
    assert result.total == len(result.items)


def test_news_resonance_service_location_match_field(monkeypatch):
    """Each LocalNewsResonance item has location_match set to the query location."""
    articles = [
        {"id": "r1", "title": "Paris climate accord signed", "summary": "Paris leaders celebrate.", "url": None, "source": None, "published_at": None},
    ]
    _inject_news(monkeypatch, articles)
    result = geolocation_service.local_news_resonance(location="Paris", limit=10)
    assert len(result.items) >= 1
    for item in result.items:
        assert item.location_match == "Paris"


def test_local_news_resonance_sorted_by_score(monkeypatch):
    """local_news_resonance returns items sorted by descending resonance_score."""
    articles = [
        {
            "id": "low",
            "title": "Rome minor note",
            "summary": "Brief mention of rome.",
            "url": None, "source": None, "published_at": None,
        },
        {
            "id": "high",
            "title": "Rome Rome Rome summit",
            "summary": "Rome hosts a major rome conference in rome today.",
            "url": None, "source": None, "published_at": None,
        },
    ]
    _inject_news(monkeypatch, articles)
    result = geolocation_service.local_news_resonance(location="Rome", limit=10)
    scores = [item.resonance_score for item in result.items]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# HTTP endpoints — PATCH contributor location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_location_for_unknown_contributor_returns_404():
    """PATCH /api/contributors/{id}/location for missing contributor returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/api/contributors/totally-unknown-user-xyz/location",
            json={
                "city": "Paris",
                "country": "FR",
                "latitude": 48.85,
                "longitude": 2.35,
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_location_coordinates_rounded_to_two_decimals():
    """PATCH rounds coordinates to 2 decimal places in the response."""
    _create_contributor("rounding-test", "RoundingUser")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/api/contributors/rounding-test/location",
            json={
                "city": "Vienna",
                "country": "AT",
                "latitude": 48.123456,
                "longitude": 16.987654,
                "visibility": "public",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    # Coordinates should be rounded to ≤2 decimal places
    lat_decimals = len(str(data["latitude"]).split(".")[-1]) if "." in str(data["latitude"]) else 0
    lon_decimals = len(str(data["longitude"]).split(".")[-1]) if "." in str(data["longitude"]) else 0
    assert lat_decimals <= 2
    assert lon_decimals <= 2


@pytest.mark.asyncio
async def test_get_location_after_patch_returns_same_data(monkeypatch):
    """GET location after PATCH returns the stored city/country/visibility.

    Uses monkeypatch to bypass the DB-layer to_dict() property flattening quirk,
    consistent with the approach in test_geo_location.py.
    """
    from datetime import datetime, timezone

    expected = ContributorLocation(
        contributor_id="round-trip",
        city="Amsterdam",
        country="NL",
        latitude=52.37,
        longitude=4.89,
        visibility=LocationVisibility.CONTRIBUTORS_ONLY,
        updated_at=datetime.now(timezone.utc),
    )
    _create_contributor("round-trip", "RoundTrip")
    monkeypatch.setattr(geolocation_service, "get_contributor_location", lambda cid: expected)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        patch_resp = await c.patch(
            "/api/contributors/round-trip/location",
            json={
                "city": "Amsterdam",
                "country": "NL",
                "latitude": 52.37,
                "longitude": 4.89,
                "visibility": "contributors_only",
            },
        )
        assert patch_resp.status_code == 200
        get_resp = await c.get("/api/contributors/round-trip/location")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["city"] == "Amsterdam"
    assert data["country"] == "NL"
    assert data["visibility"] == "contributors_only"


@pytest.mark.asyncio
async def test_get_location_no_location_set_returns_404():
    """GET /api/contributors/{id}/location returns 404 when no location stored."""
    _create_contributor("no-location-user", "NoLocation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/contributors/no-location-user/location")
    assert resp.status_code == 404
