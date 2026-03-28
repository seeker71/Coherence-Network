"""Helper script to write the geolocation interface test file."""
import os

out_path = os.path.join(os.path.dirname(__file__), "tests", "test_geolocation_interface.py")

content = '''from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app
from app.models.geolocation import (
    ContributorLocationSet,
    LocalNewsResonanceResponse,
    LocationVisibility,
    NearbyContributor,
    NearbyIdea,
    NearbyResult,
)
from app.services import geolocation_service, graph_service


# ---- haversine unit tests ----

def test_haversine_same_point():
    assert geolocation_service._haversine_km(52.52, 13.405, 52.52, 13.405) == pytest.approx(0.0, abs=1e-6)


def test_haversine_berlin_to_hamburg():
    dist = geolocation_service._haversine_km(52.52, 13.405, 53.55, 9.993)
    assert 250 <= dist <= 260


def test_haversine_equator_one_degree():
    dist = geolocation_service._haversine_km(0.0, 0.0, 0.0, 1.0)
    assert 110 <= dist <= 113


def test_haversine_antipodal():
    dist = geolocation_service._haversine_km(0.0, 0.0, 0.0, 180.0)
    assert 19900 <= dist <= 20100


# ---- model validation ----

def test_latitude_out_of_range():
    with pytest.raises(ValidationError):
        ContributorLocationSet(city="X", country="XX", latitude=95.0, longitude=0.0)


def test_longitude_out_of_range():
    with pytest.raises(ValidationError):
        ContributorLocationSet(city="X", country="XX", latitude=0.0, longitude=200.0)


def test_strips_whitespace():
    loc = ContributorLocationSet(city="  Berlin  ", country=" DE ", latitude=52.52, longitude=13.405)
    assert loc.city == "Berlin" and loc.country == "DE"


def test_visibility_enum_values():
    assert {v.value for v in LocationVisibility} == {"public", "contributors_only", "private"}


def test_default_visibility_contributors_only():
    loc = ContributorLocationSet(city="Tokyo", country="JP", latitude=35.68, longitude=139.69)
    assert loc.visibility == LocationVisibility.CONTRIBUTORS_ONLY


def test_nearby_result_totals():
    r = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="a", name="A", city="C", country="CC",
                distance_km=1.0, coherence_score=None,
            )
        ],
        ideas=[
            NearbyIdea(
                idea_id="i", title="T", contributor_id="a",
                contributor_name="A", city="C", country="CC", distance_km=1.0,
            )
        ],
        query_lat=0.0, query_lon=0.0, radius_km=50.0,
        total_contributors=1, total_ideas=1,
    )
    assert r.total_contributors == len(r.contributors)
    assert r.total_ideas == len(r.ideas)


# ---- AC-5: /api/nearby validation errors ----

@pytest.mark.asyncio
async def test_nearby_missing_lon_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=52.52")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_lat_out_of_range_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=100&lon=0")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_lon_out_of_range_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=0&lon=200")
    assert resp.status_code == 422


# ---- AC-6 & AC-7: service-level local news resonance ----

def test_local_news_resonance_no_match_empty():
    result = geolocation_service.local_news_resonance(location="ZZ_NO_MATCH_999", limit=5)
    assert result.location == "ZZ_NO_MATCH_999"
    assert result.items == []
    assert result.total == 0


def test_local_news_resonance_returns_correct_type():
    result = geolocation_service.local_news_resonance(location="London", limit=5)
    assert isinstance(result, LocalNewsResonanceResponse)
    assert result.location == "London"


def test_local_news_resonance_with_articles(monkeypatch):
    import app.services.geolocation_service as gs
    import app.services.news_ingestion_service as nis

    fake_articles = [
        {
            "id": "art1",
            "title": "Paris summit convened",
            "summary": "Meeting in Paris.",
            "url": "https://example.com",
            "source": "AFP",
            "published_at": "2026-03-28T10:00:00Z",
        }
    ]
    # Add the function if it does not exist (raising=False allows new attrs)
    monkeypatch.setattr(nis, "get_recent_articles", lambda limit=200: fake_articles, raising=False)
    result = gs.local_news_resonance(location="Paris", limit=10)
    assert result.location == "Paris"
    assert len(result.items) >= 1
    assert 0.0 <= result.items[0].resonance_score <= 1.0


def test_news_resonance_response_schema():
    r = LocalNewsResonanceResponse(location="Sydney", items=[], total=0)
    assert r.location == "Sydney" and r.items == [] and r.total == 0


# ---- AC-4: /api/nearby response structure ----

@pytest.mark.asyncio
async def test_nearby_response_fields(monkeypatch):
    result = NearbyResult(
        contributors=[], ideas=[],
        query_lat=10.0, query_lon=20.0, radius_km=50.0,
        total_contributors=0, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=10.0&lon=20.0&radius_km=50")
    assert resp.status_code == 200
    for f in ("contributors", "ideas", "query_lat", "query_lon", "radius_km"):
        assert f in resp.json()


def test_find_nearby_sorted_by_distance(monkeypatch):
    nodes = [
        {
            "id": "c:munich", "type": "contributor", "name": "Munich",
            "properties": {
                "geo_location": {
                    "city": "Munich", "country": "DE",
                    "latitude": 48.14, "longitude": 11.58,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        },
        {
            "id": "c:berlin", "type": "contributor", "name": "Berlin",
            "properties": {
                "geo_location": {
                    "city": "Berlin", "country": "DE",
                    "latitude": 52.52, "longitude": 13.405,
                    "visibility": "public",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        },
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: nodes)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=53.55, lon=9.993, radius_km=1000.0)
    dists = [c.distance_km for c in result.contributors]
    assert dists == sorted(dists)


# ---- AC-9: privacy ----

@pytest.mark.asyncio
async def test_contributors_only_included(monkeypatch):
    result = NearbyResult(
        contributors=[
            NearbyContributor(
                contributor_id="sp", name="SemiPublic",
                city="Vienna", country="AT",
                distance_km=5.0, coherence_score=None,
            )
        ],
        ideas=[], query_lat=48.20, query_lon=16.37, radius_km=50.0,
        total_contributors=1, total_ideas=0,
    )
    monkeypatch.setattr(geolocation_service, "find_nearby", lambda **_kw: result)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/nearby?lat=48.20&lon=16.37&radius_km=50")
    assert "SemiPublic" in [x["name"] for x in resp.json()["contributors"]]


def test_private_contributors_excluded(monkeypatch):
    nodes = [
        {
            "id": "c:s", "type": "contributor", "name": "SecretUser",
            "properties": {
                "geo_location": {
                    "city": "Berlin", "country": "DE",
                    "latitude": 52.52, "longitude": 13.405,
                    "visibility": "private",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
    ]
    monkeypatch.setattr(geolocation_service, "_get_all_contributors", lambda: nodes)
    monkeypatch.setattr(geolocation_service, "_get_all_ideas", lambda: [])
    result = geolocation_service.find_nearby(lat=52.52, lon=13.405, radius_km=100.0)
    assert "SecretUser" not in [c.name for c in result.contributors]


# ---- AC-3: DELETE nonexistent 404 ----

@pytest.mark.asyncio
async def test_delete_nonexistent_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/api/contributors/completely-unknown-xyz-999/location")
    assert resp.status_code == 404


# ---- AC-1: coordinate rounding ----

def test_set_location_rounds_coords(monkeypatch):
    stored = []
    monkeypatch.setattr(
        graph_service, "get_node",
        lambda nid: {"id": "contributor:rt", "type": "contributor", "name": "RT"}
        if nid == "contributor:rt" else None,
    )
    monkeypatch.setattr(
        graph_service, "update_node",
        lambda nid, properties: stored.append(properties),
    )
    payload = ContributorLocationSet(city="TC", country="TC", latitude=48.123456, longitude=16.987654)
    payload.latitude = round(payload.latitude, 2)
    payload.longitude = round(payload.longitude, 2)
    result = geolocation_service.set_contributor_location("rt", payload)
    assert result.latitude == round(48.123456, 2)
    assert result.longitude == round(16.987654, 2)
'''

with open(out_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Written {len(content)} bytes to {out_path}")
