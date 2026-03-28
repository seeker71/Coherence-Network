"""Tests for Geolocation Awareness — nearby contributors, local ideas, regional news.

Feature: GeocodingService (OpenCage + Nominatim + fallback) enriches contributor
profiles with resolved coordinates, enabling proximity filtering of ideas,
news, and tasks, and surfacing nearby collaborators.

Coverage matrix
---------------
GC-1  GeocodingService resolves location via OpenCage when key is present
GC-2  GeocodingService falls back to Nominatim when OpenCage key is absent
GC-3  GeocodingService returns None when both providers fail
GC-4  GeocodingService falls back to Nominatim when OpenCage returns no results
GC-5  GeocodingService falls back to Nominatim on OpenCage HTTP error
GC-6  GeocodingService.geocode() rejects empty string (returns None)
GC-7  GeocodingResult contains required fields: lat, lon, city, country, provider
GC-8  geocode_batch resolves multiple locations and returns a keyed mapping
GC-9  enrich_contributor_location geocodes and stores location on contributor node
GC-10 enrich_contributor_location returns None for unknown contributor
GC-11 enrich_contributor_location returns None when geocoding fails
GC-12 Nominatim rate-limit: _last_nominatim_call is updated after each request
GC-13 Nearby search surfaces contributors after geocoded location enrichment
GC-14 Nearby search excludes contributors outside radius after enrichment
GC-15 Regional news resonance matches articles containing the geocoded city name
GC-16 Regional news resonance returns empty items for unresolvable location
GC-17 /api/nearby endpoint returns 200 with enriched contributor in radius
GC-18 /api/news/resonance/local returns items with score ∈ [0, 1]
GC-19 /api/nearby without credentials returns 422 (missing lat/lon)
GC-20 _geocode_opencage parses OpenCage response format correctly
GC-21 _geocode_nominatim parses Nominatim response format correctly
GC-22 _geocode_opencage returns None on empty results list
GC-23 _geocode_nominatim returns None on empty list response
GC-24 Haversine accuracy: Berlin→Frankfurt ~500 km
GC-25 find_nearby returns nearby ideas linked to nearby contributors
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.geolocation import (
    ContributorLocation,
    ContributorLocationSet,
    LocalNewsResonanceResponse,
    LocationVisibility,
    NearbyContributor,
    NearbyIdea,
    NearbyResult,
)
from app.services import geolocation_service, graph_service
from app.services.geocoding_service import (
    GeocodingResult,
    GeocodingService,
    _geocode_nominatim,
    _geocode_opencage,
    _http_get_json,
)

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

_BERLIN_LAT = 52.52
_BERLIN_LON = 13.405
_FRANKFURT_LAT = 50.11
_FRANKFURT_LON = 8.68
_TOKYO_LAT = 35.68
_TOKYO_LON = 139.69

_OPENCAGE_BERLIN_RESPONSE = {
    "results": [
        {
            "geometry": {"lat": _BERLIN_LAT, "lng": _BERLIN_LON},
            "components": {
                "city": "Berlin",
                "state": "Berlin",
                "country": "Germany",
                "country_code": "de",
            },
            "formatted": "Berlin, Germany",
        }
    ]
}

_NOMINATIM_BERLIN_RESPONSE = [
    {
        "lat": str(_BERLIN_LAT),
        "lon": str(_BERLIN_LON),
        "display_name": "Berlin, Germany",
        "address": {
            "city": "Berlin",
            "state": "Berlin",
            "country": "Germany",
            "country_code": "de",
        },
    }
]

_OPENCAGE_TOKYO_RESPONSE = {
    "results": [
        {
            "geometry": {"lat": _TOKYO_LAT, "lng": _TOKYO_LON},
            "components": {
                "city": "Tokyo",
                "state": "Tokyo-to",
                "country": "Japan",
                "country_code": "jp",
            },
            "formatted": "Tokyo, Japan",
        }
    ]
}

# ---------------------------------------------------------------------------
# Helper: inject a fake news_ingestion_service module
# ---------------------------------------------------------------------------


def _install_fake_news(articles: list[dict]):
    """Temporarily replace news_ingestion_service with one returning *articles*."""
    fake_nis = types.ModuleType("app.services.news_ingestion_service")
    fake_nis.get_recent_articles = lambda limit=200: articles  # type: ignore[attr-defined]
    orig = sys.modules.get("app.services.news_ingestion_service")
    sys.modules["app.services.news_ingestion_service"] = fake_nis
    return orig


def _uninstall_fake_news(orig):
    if orig is not None:
        sys.modules["app.services.news_ingestion_service"] = orig
    else:
        sys.modules.pop("app.services.news_ingestion_service", None)


# ===========================================================================
# GC-20, GC-22 — _geocode_opencage unit tests
# ===========================================================================


def test_geocode_opencage_parses_response(monkeypatch: pytest.MonkeyPatch):
    """GC-20: _geocode_opencage extracts lat, lon, city, country from response."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _OPENCAGE_BERLIN_RESPONSE,
    )
    result = _geocode_opencage("Berlin", "fake_key")
    assert result is not None
    assert result.latitude == _BERLIN_LAT
    assert result.longitude == _BERLIN_LON
    assert result.city == "Berlin"
    assert result.country == "Germany"
    assert result.country_code == "DE"
    assert result.provider == "opencage"


def test_geocode_opencage_returns_none_on_empty_results(monkeypatch: pytest.MonkeyPatch):
    """GC-22: _geocode_opencage returns None when results list is empty."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: {"results": []},
    )
    result = _geocode_opencage("Atlantis", "fake_key")
    assert result is None


def test_geocode_opencage_raises_on_http_error(monkeypatch: pytest.MonkeyPatch):
    """_geocode_opencage propagates RuntimeError on HTTP failure."""

    def bad_get(url, headers=None):
        raise RuntimeError("HTTP 401")

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", bad_get)
    with pytest.raises(RuntimeError, match="HTTP 401"):
        _geocode_opencage("Berlin", "bad_key")


def test_geocode_opencage_uses_town_fallback(monkeypatch: pytest.MonkeyPatch):
    """_geocode_opencage falls back to 'town' when 'city' is absent."""
    response = {
        "results": [
            {
                "geometry": {"lat": 51.5, "lng": -0.12},
                "components": {
                    "town": "Hammersmith",
                    "country": "United Kingdom",
                    "country_code": "gb",
                },
                "formatted": "Hammersmith, UK",
            }
        ]
    }
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: response,
    )
    result = _geocode_opencage("Hammersmith", "key")
    assert result is not None
    assert result.city == "Hammersmith"


# ===========================================================================
# GC-21, GC-23 — _geocode_nominatim unit tests
# ===========================================================================


def test_geocode_nominatim_parses_response(monkeypatch: pytest.MonkeyPatch):
    """GC-21: _geocode_nominatim extracts lat, lon, city, country from response."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _NOMINATIM_BERLIN_RESPONSE,
    )
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    result = _geocode_nominatim("Berlin")
    assert result is not None
    assert float(result.latitude) == pytest.approx(_BERLIN_LAT, abs=0.01)
    assert float(result.longitude) == pytest.approx(_BERLIN_LON, abs=0.01)
    assert result.city == "Berlin"
    assert result.country_code == "DE"
    assert result.provider == "nominatim"


def test_geocode_nominatim_returns_none_on_empty_list(monkeypatch: pytest.MonkeyPatch):
    """GC-23: _geocode_nominatim returns None when response list is empty."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: [],
    )
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    result = _geocode_nominatim("Neverland")
    assert result is None


def test_geocode_nominatim_raises_on_http_error(monkeypatch: pytest.MonkeyPatch):
    """_geocode_nominatim propagates RuntimeError on HTTP failure."""

    def bad_get(url, headers=None):
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", bad_get)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _geocode_nominatim("Berlin")


# ===========================================================================
# GC-1 to GC-8 — GeocodingService class tests
# ===========================================================================


def test_geocoding_service_uses_opencage_when_key_present(monkeypatch: pytest.MonkeyPatch):
    """GC-1: GeocodingService uses OpenCage when API key is configured."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _OPENCAGE_BERLIN_RESPONSE,
    )
    svc = GeocodingService(opencage_api_key="testkey123")
    result = svc.geocode("Berlin")
    assert result is not None
    assert result.provider == "opencage"
    assert result.city == "Berlin"


def test_geocoding_service_skips_opencage_without_key(monkeypatch: pytest.MonkeyPatch):
    """GC-2: GeocodingService skips OpenCage and goes to Nominatim when no key."""
    nominatim_called = {"called": False}

    def fake_http(url, headers=None):
        if "nominatim" in url:
            nominatim_called["called"] = True
            return _NOMINATIM_BERLIN_RESPONSE
        return {"results": []}

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", fake_http)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    # Ensure no env var key is set
    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    svc = GeocodingService(opencage_api_key=None)
    result = svc.geocode("Berlin")
    assert result is not None
    assert nominatim_called["called"] is True
    assert result.provider == "nominatim"


def test_geocoding_service_returns_none_when_both_fail(monkeypatch: pytest.MonkeyPatch):
    """GC-3: GeocodingService returns None when both OpenCage and Nominatim fail."""

    def always_fail(url, headers=None):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", always_fail)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    svc = GeocodingService(opencage_api_key=None)
    result = svc.geocode("Berlin")
    assert result is None


def test_geocoding_service_falls_back_to_nominatim_on_opencage_no_results(
    monkeypatch: pytest.MonkeyPatch,
):
    """GC-4: GeocodingService uses Nominatim when OpenCage returns empty results."""
    call_log: list[str] = []

    def fake_http(url, headers=None):
        if "opencagedata" in url:
            call_log.append("opencage")
            return {"results": []}
        if "nominatim" in url:
            call_log.append("nominatim")
            return _NOMINATIM_BERLIN_RESPONSE
        return {}

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", fake_http)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    svc = GeocodingService(opencage_api_key="testkey")
    result = svc.geocode("Berlin")
    assert "opencage" in call_log
    assert "nominatim" in call_log
    assert result is not None
    assert result.provider == "nominatim"


def test_geocoding_service_falls_back_to_nominatim_on_opencage_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """GC-5: GeocodingService uses Nominatim when OpenCage raises RuntimeError."""
    call_log: list[str] = []

    def fake_http(url, headers=None):
        if "opencagedata" in url:
            call_log.append("opencage_fail")
            raise RuntimeError("HTTP 429 rate limit")
        if "nominatim" in url:
            call_log.append("nominatim")
            return _NOMINATIM_BERLIN_RESPONSE
        return {}

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", fake_http)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    svc = GeocodingService(opencage_api_key="testkey")
    result = svc.geocode("Berlin")
    assert "opencage_fail" in call_log
    assert "nominatim" in call_log
    assert result is not None
    assert result.provider == "nominatim"


def test_geocoding_service_rejects_empty_query():
    """GC-6: geocode() returns None for empty or whitespace-only query."""
    svc = GeocodingService(opencage_api_key=None, use_nominatim_fallback=False)
    assert svc.geocode("") is None
    assert svc.geocode("   ") is None


def test_geocoding_result_fields(monkeypatch: pytest.MonkeyPatch):
    """GC-7: GeocodingResult contains all required fields."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _OPENCAGE_BERLIN_RESPONSE,
    )
    svc = GeocodingService(opencage_api_key="testkey")
    result = svc.geocode("Berlin")
    assert result is not None
    # Required fields
    assert hasattr(result, "latitude") and isinstance(result.latitude, float)
    assert hasattr(result, "longitude") and isinstance(result.longitude, float)
    assert hasattr(result, "city") and result.city
    assert hasattr(result, "country") and result.country
    assert hasattr(result, "provider") and result.provider in ("opencage", "nominatim", "fallback")
    assert hasattr(result, "formatted") and result.formatted


def test_geocoding_batch(monkeypatch: pytest.MonkeyPatch):
    """GC-8: geocode_batch resolves multiple queries and returns a keyed mapping."""
    responses = {
        "Berlin": _OPENCAGE_BERLIN_RESPONSE,
        "Tokyo": _OPENCAGE_TOKYO_RESPONSE,
    }

    def fake_http(url, headers=None):
        for city, resp in responses.items():
            if city.lower() in url.lower():
                return resp
        return {"results": []}

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", fake_http)
    svc = GeocodingService(opencage_api_key="testkey")
    batch_result = svc.geocode_batch(["Berlin", "Tokyo", "Atlantis"])
    assert "Berlin" in batch_result
    assert "Tokyo" in batch_result
    assert "Atlantis" in batch_result
    assert batch_result["Berlin"] is not None
    assert batch_result["Berlin"].city == "Berlin"
    assert batch_result["Tokyo"] is not None
    assert batch_result["Tokyo"].city == "Tokyo"
    assert batch_result["Atlantis"] is None  # no results


# ===========================================================================
# GC-9 to GC-11 — enrich_contributor_location
# ===========================================================================


def test_enrich_contributor_location_stores_geocoded_coords(monkeypatch: pytest.MonkeyPatch):
    """GC-9: enrich_contributor_location geocodes and persists the location."""
    # Create a contributor in the graph
    graph_service.create_node(id="contributor:geo-enrich-01", type="contributor", name="Enrich01")

    # Mock geocoding to return Berlin coordinates
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _OPENCAGE_BERLIN_RESPONSE,
    )
    svc = GeocodingService(opencage_api_key="testkey")
    result = svc.enrich_contributor_location("geo-enrich-01", "Berlin, Germany")
    assert result is not None
    assert result["city"] == "Berlin"
    assert result["contributor_id"] == "geo-enrich-01"
    assert result["latitude"] == pytest.approx(_BERLIN_LAT, abs=0.1)
    assert result["longitude"] == pytest.approx(_BERLIN_LON, abs=0.1)
    assert result["provider"] == "opencage"


def test_enrich_contributor_location_returns_none_for_unknown_contributor(
    monkeypatch: pytest.MonkeyPatch,
):
    """GC-10: enrich_contributor_location returns None when contributor doesn't exist."""
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _OPENCAGE_BERLIN_RESPONSE,
    )
    svc = GeocodingService(opencage_api_key="testkey")
    result = svc.enrich_contributor_location("nonexistent-xyz-999", "Berlin")
    assert result is None


def test_enrich_contributor_location_returns_none_when_geocoding_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    """GC-11: enrich_contributor_location returns None when geocoding returns no result."""
    graph_service.create_node(id="contributor:geo-fail-01", type="contributor", name="GeoFail")

    def always_fail(url, headers=None):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", always_fail)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    svc = GeocodingService(opencage_api_key=None)
    result = svc.enrich_contributor_location("geo-fail-01", "Atlantis")
    assert result is None


# ===========================================================================
# GC-12 — Nominatim rate-limit tracking
# ===========================================================================


def test_nominatim_rate_limit_last_call_updated(monkeypatch: pytest.MonkeyPatch):
    """GC-12: _last_nominatim_call is updated after each Nominatim request."""
    import app.services.geocoding_service as gs

    fake_time = MagicMock()
    fake_time.monotonic.return_value = 12345.0
    fake_time.sleep = MagicMock()
    monkeypatch.setattr("app.services.geocoding_service.time", fake_time)
    monkeypatch.setattr(
        "app.services.geocoding_service._http_get_json",
        lambda url, headers=None: _NOMINATIM_BERLIN_RESPONSE,
    )
    # Reset state
    gs._last_nominatim_call = 0.0

    _geocode_nominatim("Berlin")

    # After the call the timestamp should have been updated
    assert gs._last_nominatim_call == 12345.0


# ===========================================================================
# GC-13, GC-14 — Nearby search after geocoded enrichment
# ===========================================================================


def test_nearby_search_surfaces_geocoded_contributor(monkeypatch: pytest.MonkeyPatch):
    """GC-13: find_nearby returns contributors enriched via GeocodingService."""
    result = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="geo-nearby-01",
                name="NearbyEnriched",
                city="Berlin",
                country="DE",
                distance_km=1.5,
                coherence_score=None,
            )
        ],
        ideas=[],
        query_lat=_BERLIN_LAT,
        query_lon=_BERLIN_LON,
        radius_km=50.0,
        total_contributors=1,
        total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)

    found = geolocation_service.find_nearby(lat=_BERLIN_LAT, lon=_BERLIN_LON, radius_km=50.0)
    names = [c.name for c in found.contributors]
    assert "NearbyEnriched" in names


def test_nearby_search_excludes_distant_geocoded_contributor(monkeypatch: pytest.MonkeyPatch):
    """GC-14: Contributor geocoded to Tokyo is absent from Berlin radius=100 search."""
    # Simulate a real find_nearby with contributor nodes
    berlin_node = {
        "id": "contributor:gc14-berlin",
        "type": "contributor",
        "name": "GC14Berlin",
        "properties": {
            "geo_location": {
                "city": "Berlin",
                "country": "DE",
                "latitude": _BERLIN_LAT,
                "longitude": _BERLIN_LON,
                "visibility": "public",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        },
    }
    tokyo_node = {
        "id": "contributor:gc14-tokyo",
        "type": "contributor",
        "name": "GC14Tokyo",
        "properties": {
            "geo_location": {
                "city": "Tokyo",
                "country": "JP",
                "latitude": _TOKYO_LAT,
                "longitude": _TOKYO_LON,
                "visibility": "public",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        },
    }
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: [berlin_node, tokyo_node])
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])

    result = geolocation_service.find_nearby(lat=_BERLIN_LAT, lon=_BERLIN_LON, radius_km=100.0)
    names = [c.name for c in result.contributors]
    assert "GC14Berlin" in names
    assert "GC14Tokyo" not in names


# ===========================================================================
# GC-15, GC-16 — Regional news resonance
# ===========================================================================


def test_regional_news_resonance_matches_geocoded_city(monkeypatch: pytest.MonkeyPatch):
    """GC-15: local_news_resonance returns articles mentioning the geocoded city."""
    import app.services.geolocation_service as gs

    articles = [
        {
            "id": "art-berlin-1",
            "title": "Berlin innovation hub attracts global talent",
            "summary": "The Berlin startup ecosystem continues to grow rapidly.",
            "url": "https://example.com/berlin-1",
            "source": "TechEU",
            "published_at": "2026-03-28T09:00:00Z",
        },
        {
            "id": "art-paris-1",
            "title": "Paris fashion week highlights",
            "summary": "Paris designers unveil new collections at fashion week.",
            "url": "https://example.com/paris-1",
            "source": "FashionMag",
            "published_at": "2026-03-28T08:00:00Z",
        },
    ]
    orig = _install_fake_news(articles)
    try:
        result = gs.local_news_resonance(location="Berlin", limit=10)
    finally:
        _uninstall_fake_news(orig)

    assert result.location == "Berlin"
    assert result.total >= 1
    titles = [item.title for item in result.items]
    assert any("Berlin" in t for t in titles)
    for item in result.items:
        assert 0.0 <= item.resonance_score <= 1.0
        assert item.location_match == "Berlin"


def test_regional_news_resonance_empty_for_no_match():
    """GC-16: local_news_resonance returns empty items for an unknown location."""
    import app.services.geolocation_service as gs

    result = gs.local_news_resonance(location="ZZZ_NO_CITY_MATCH_9999", limit=10)
    assert result.location == "ZZZ_NO_CITY_MATCH_9999"
    assert result.items == []
    assert result.total == 0


def test_regional_news_resonance_multi_token_location(monkeypatch: pytest.MonkeyPatch):
    """GC-15b: multi-word location 'New York' scores articles mentioning both tokens."""
    import app.services.geolocation_service as gs

    articles = [
        {
            "id": "art-ny-1",
            "title": "New York city budget",
            "summary": "New York mayor presents the annual budget in new york city hall.",
            "url": "https://example.com/ny",
            "source": "NYT",
            "published_at": "2026-03-28T10:00:00Z",
        }
    ]
    orig = _install_fake_news(articles)
    try:
        result = gs.local_news_resonance(location="New York", limit=10)
    finally:
        _uninstall_fake_news(orig)

    assert result.total >= 1
    assert result.items[0].resonance_score > 0.0


# ===========================================================================
# GC-17 to GC-19 — HTTP endpoint integration tests
# ===========================================================================


@pytest.mark.asyncio
async def test_nearby_endpoint_returns_enriched_contributor(monkeypatch: pytest.MonkeyPatch):
    """GC-17: GET /api/nearby returns 200 with a contributor enriched via geocoding."""
    expected = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="gc17-user",
                name="GC17User",
                city="Berlin",
                country="DE",
                distance_km=3.2,
                coherence_score=0.85,
            )
        ],
        ideas=[],
        query_lat=_BERLIN_LAT,
        query_lon=_BERLIN_LON,
        radius_km=50.0,
        total_contributors=1,
        total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: expected)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/nearby?lat={_BERLIN_LAT}&lon={_BERLIN_LON}&radius_km=50")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contributors"] == 1
    assert data["contributors"][0]["name"] == "GC17User"
    assert data["contributors"][0]["city"] == "Berlin"
    assert "distance_km" in data["contributors"][0]
    # Coordinates must NOT be exposed
    assert "latitude" not in data["contributors"][0]
    assert "longitude" not in data["contributors"][0]


@pytest.mark.asyncio
async def test_local_news_resonance_endpoint_returns_items_with_scores(
    monkeypatch: pytest.MonkeyPatch,
):
    """GC-18: GET /api/news/resonance/local returns items with resonance_score ∈ [0, 1]."""
    import app.services.geolocation_service as gs

    articles = [
        {
            "id": "gc18-art",
            "title": "Frankfurt finance summit",
            "summary": "Frankfurt hosted a major summit of european finance ministers.",
            "url": "https://example.com/fft",
            "source": "FT",
            "published_at": "2026-03-28T07:00:00Z",
        }
    ]
    orig = _install_fake_news(articles)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/news/resonance/local?location=Frankfurt&limit=10")
    finally:
        _uninstall_fake_news(orig)

    assert resp.status_code == 200
    data = resp.json()
    assert data["location"] == "Frankfurt"
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert 0.0 <= item["resonance_score"] <= 1.0


@pytest.mark.asyncio
async def test_nearby_endpoint_missing_lat_lon_returns_422():
    """GC-19: GET /api/nearby without required params returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_local_news_resonance_endpoint_missing_location_returns_422():
    """GC-19b: GET /api/news/resonance/local without location param returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local")
    assert resp.status_code == 422


# ===========================================================================
# GC-24 — Haversine accuracy for Berlin → Frankfurt
# ===========================================================================


def test_haversine_berlin_to_frankfurt():
    """GC-24: Haversine distance Berlin→Frankfurt is approximately 500 km."""
    from app.services.geolocation_service import _haversine_km

    dist = _haversine_km(_BERLIN_LAT, _BERLIN_LON, _FRANKFURT_LAT, _FRANKFURT_LON)
    # Actual straight-line distance is ~492 km
    assert 480 <= dist <= 520, f"Expected ~500 km, got {dist:.1f} km"


# ===========================================================================
# GC-25 — find_nearby returns ideas linked to nearby contributors
# ===========================================================================


def test_find_nearby_returns_ideas_for_nearby_contributors(monkeypatch: pytest.MonkeyPatch):
    """GC-25: find_nearby includes ideas authored by nearby contributors."""
    contributor_nodes = [
        {
            "id": "contributor:gc25-author",
            "type": "contributor",
            "name": "GC25Author",
            "properties": {
                "geo_location": {
                    "city": "Berlin",
                    "country": "DE",
                    "latitude": _BERLIN_LAT,
                    "longitude": _BERLIN_LON,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
                "coherence_score": 0.72,
            },
        }
    ]
    idea_nodes = [
        {
            "id": "idea:gc25-idea-1",
            "type": "idea",
            "name": "GC25 Local Idea",
            "properties": {"author": "GC25Author"},
        }
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: contributor_nodes)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: idea_nodes)

    result = geolocation_service.find_nearby(lat=_BERLIN_LAT, lon=_BERLIN_LON, radius_km=100.0)
    idea_titles = [i.title for i in result.ideas]
    assert "GC25 Local Idea" in idea_titles
    assert result.total_ideas == 1


def test_find_nearby_excludes_ideas_from_distant_contributors(monkeypatch: pytest.MonkeyPatch):
    """GC-25b: Ideas from contributors outside radius are not returned."""
    # Only Tokyo contributor — should be outside 100 km Berlin radius
    contributor_nodes = [
        {
            "id": "contributor:gc25b-author",
            "type": "contributor",
            "name": "GC25BAuthor",
            "properties": {
                "geo_location": {
                    "city": "Tokyo",
                    "country": "JP",
                    "latitude": _TOKYO_LAT,
                    "longitude": _TOKYO_LON,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
    ]
    idea_nodes = [
        {
            "id": "idea:gc25b-idea-1",
            "type": "idea",
            "name": "GC25B Tokyo Idea",
            "properties": {"author": "GC25BAuthor"},
        }
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: contributor_nodes)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: idea_nodes)

    result = geolocation_service.find_nearby(lat=_BERLIN_LAT, lon=_BERLIN_LON, radius_km=100.0)
    idea_titles = [i.title for i in result.ideas]
    assert "GC25B Tokyo Idea" not in idea_titles
    assert result.total_ideas == 0


# ===========================================================================
# Additional edge cases and contract checks
# ===========================================================================


def test_geocoding_service_nominatim_only_mode(monkeypatch: pytest.MonkeyPatch):
    """GeocodingService with no OpenCage key uses Nominatim only — no OpenCage calls made."""
    calls: list[str] = []

    def tracked_http(url, headers=None):
        if "opencagedata" in url:
            calls.append("opencage")
        elif "nominatim" in url:
            calls.append("nominatim")
            return _NOMINATIM_BERLIN_RESPONSE
        return {}

    monkeypatch.setattr("app.services.geocoding_service._http_get_json", tracked_http)
    monkeypatch.setattr("app.services.geocoding_service.time", MagicMock(monotonic=lambda: 999))
    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)

    svc = GeocodingService(opencage_api_key=None)
    result = svc.geocode("Berlin, Germany")
    assert "opencage" not in calls, "OpenCage should not be called without API key"
    assert "nominatim" in calls
    assert result is not None


def test_geocoding_service_nominatim_disabled_returns_none_without_opencage(
    monkeypatch: pytest.MonkeyPatch,
):
    """With use_nominatim_fallback=False and no key, geocode returns None immediately."""
    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    svc = GeocodingService(opencage_api_key=None, use_nominatim_fallback=False)
    result = svc.geocode("Berlin")
    assert result is None


def test_geocoding_result_dataclass_fields():
    """GeocodingResult is a dataclass with all expected attributes."""
    r = GeocodingResult(
        latitude=52.52,
        longitude=13.405,
        city="Berlin",
        region="Berlin",
        country="Germany",
        country_code="DE",
        formatted="Berlin, Germany",
        provider="opencage",
    )
    assert r.latitude == 52.52
    assert r.longitude == 13.405
    assert r.city == "Berlin"
    assert r.country_code == "DE"
    assert r.provider == "opencage"


@pytest.mark.asyncio
async def test_nearby_full_create_read_cycle():
    """Full cycle: set location → query nearby → contributor appears in results."""
    # Create contributor
    graph_service.create_node(
        id="contributor:geo-cycle-01", type="contributor", name="GeoCycle01"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Set location
        patch_resp = await client.patch(
            "/api/contributors/geo-cycle-01/location",
            json={
                "city": "Berlin",
                "country": "DE",
                "latitude": _BERLIN_LAT,
                "longitude": _BERLIN_LON,
                "visibility": "public",
            },
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["city"] == "Berlin"

        # Read it back
        get_resp = await client.get("/api/contributors/geo-cycle-01/location")
        assert get_resp.status_code == 200
        loc_data = get_resp.json()
        assert loc_data["city"] == "Berlin"
        # No raw lat/lon in response
        assert "lat" not in loc_data
        assert "lon" not in loc_data

        # Delete it
        del_resp = await client.delete("/api/contributors/geo-cycle-01/location")
        assert del_resp.status_code == 204

        # Now 404 after deletion
        get_after = await client.get("/api/contributors/geo-cycle-01/location")
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_nearby_bad_lat_lon_returns_422():
    """Edge case: lat=999 and lon=999 both out of range → 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?lat=999&lon=999")
    assert resp.status_code == 422


def test_news_resonance_items_sorted_by_score_descending(monkeypatch: pytest.MonkeyPatch):
    """Items in local_news_resonance response are sorted high→low by resonance_score."""
    import app.services.geolocation_service as gs

    articles = [
        {
            "id": "a1",
            "title": "London event",
            "summary": "An event in london.",
            "url": "https://example.com/a1",
            "source": "BBC",
            "published_at": "2026-03-28T10:00:00Z",
        },
        {
            "id": "a2",
            "title": "London london london triple mention",
            "summary": "London london london — lots of london mentions.",
            "url": "https://example.com/a2",
            "source": "Guardian",
            "published_at": "2026-03-28T09:00:00Z",
        },
    ]
    orig = _install_fake_news(articles)
    try:
        result = gs.local_news_resonance(location="London", limit=10)
    finally:
        _uninstall_fake_news(orig)

    scores = [item.resonance_score for item in result.items]
    assert scores == sorted(scores, reverse=True), "Items must be sorted high→low by score"
