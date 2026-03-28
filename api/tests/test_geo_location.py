"""Integration tests for the Geolocation Interface (Spec 170).

Tests cover:
  - PATCH /api/contributors/{id}/location — set location
  - GET  /api/contributors/{id}/location  — retrieve location (no lat/lon exposed)
  - DELETE /api/contributors/{id}/location — remove location
  - GET  /api/nearby                      — nearby contributors & ideas
  - GET  /api/news/resonance/local        — local news resonance

AC references are noted per test.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_contributor(node_id: str, name: str) -> dict:
    """Create a contributor graph node whose id matches the router's lookup."""
    return graph_service.create_node(
        id=f"contributor:{node_id}",
        type="contributor",
        name=name,
    )


# ---------------------------------------------------------------------------
# AC 1 & 2 — set location, response must NOT contain lat/lon
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_contributor_location_returns_profile() -> None:
    """PATCH sets location and returns a ContributorLocation without raw lat/lon.

    AC-1: endpoint accepts city/country/lat/lon/visibility.
    AC-2: response never exposes raw lat/lon.
    """
    _make_contributor("alice", "Alice")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/contributors/alice/location",
            json={
                "city": "Berlin",
                "country": "DE",
                "latitude": 52.52,
                "longitude": 13.405,
                "visibility": "public",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["city"] == "Berlin"
    assert data["country"] == "DE"
    assert data["contributor_id"] == "alice"
    assert data["visibility"] == "public"
    # lat/lon must NOT be in the top-level response body
    assert "lat" not in data
    assert "lon" not in data


@pytest.mark.asyncio
async def test_set_location_stores_updated_at() -> None:
    """PATCH response includes an updated_at timestamp (ISO 8601)."""
    _make_contributor("bob-ts", "Bob TS")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/contributors/bob-ts/location",
            json={
                "city": "Hamburg",
                "country": "DE",
                "latitude": 53.55,
                "longitude": 10.0,
                "visibility": "public",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "updated_at" in data
    assert data["updated_at"]  # non-empty


# ---------------------------------------------------------------------------
# AC 2 — GET location: city/country/visibility present; raw coords absent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_contributor_location_returns_profile_without_raw_coords() -> None:
    """GET returns stored location; lat/lon are NOT in the response body.

    AC-2: raw coordinates must never be returned to callers.
    """
    _make_contributor("carol", "Carol")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First set it
        await client.patch(
            "/api/contributors/carol/location",
            json={
                "city": "Munich",
                "country": "DE",
                "latitude": 48.14,
                "longitude": 11.58,
                "visibility": "contributors_only",
            },
        )
        resp = await client.get("/api/contributors/carol/location")

    assert resp.status_code == 200
    data = resp.json()
    assert data["city"] == "Munich"
    assert data["country"] == "DE"
    assert data["contributor_id"] == "carol"
    assert "lat" not in data
    assert "lon" not in data


@pytest.mark.asyncio
async def test_get_contributor_location_not_found_returns_404() -> None:
    """GET on a contributor without location returns 404.

    AC-2 edge: non-existent contributor → 404.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/contributors/no-such-contributor/location")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC 3 — DELETE location removes contributor from nearby queries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_contributor_location_returns_204_and_removes_entry() -> None:
    """DELETE returns 204 and GET afterwards returns 404.

    AC-3: right-to-delete; subsequent lookup returns 404.
    """
    _make_contributor("dave", "Dave")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch(
            "/api/contributors/dave/location",
            json={
                "city": "Copenhagen",
                "country": "DK",
                "latitude": 55.68,
                "longitude": 12.57,
                "visibility": "public",
            },
        )
        del_resp = await client.delete("/api/contributors/dave/location")
        get_resp = await client.get("/api/contributors/dave/location")

    assert del_resp.status_code == 204
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_absent_location_returns_404() -> None:
    """Second DELETE on already-removed location returns 404, not 500.

    AC-3 edge: idempotent delete behaviour.
    """
    _make_contributor("eve", "Eve")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No location ever set → should return 404 on delete
        resp = await client.delete("/api/contributors/eve/location")
    # The service returns False when node has no location; router raises 404
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC 4 & 9 — nearby: public included, private excluded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_returns_public_contributors_within_radius() -> None:
    """GET /api/nearby returns public contributor; private contributor excluded.

    AC-4: contributors array includes distance_km, name, id, visibility.
    AC-9: private contributors are excluded regardless of distance.
    """
    _make_contributor("frank", "Frank")
    _make_contributor("grace", "Grace")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Frank: public, Berlin (≈0 km from query point)
        await client.patch(
            "/api/contributors/frank/location",
            json={
                "city": "Berlin",
                "country": "DE",
                "latitude": 52.52,
                "longitude": 13.40,
                "visibility": "public",
            },
        )
        # Grace: private, also Berlin — must be excluded
        await client.patch(
            "/api/contributors/grace/location",
            json={
                "city": "Berlin",
                "country": "DE",
                "latitude": 52.52,
                "longitude": 13.40,
                "visibility": "private",
            },
        )
        resp = await client.get("/api/nearby?lat=52.52&lon=13.40&radius_km=100")

    assert resp.status_code == 200
    data = resp.json()
    assert "contributors" in data
    contributor_names = [c["name"] for c in data["contributors"]]
    assert "Frank" in contributor_names
    assert "Grace" not in contributor_names
    # Each entry must include distance_km
    for entry in data["contributors"]:
        assert "distance_km" in entry
        assert entry["distance_km"] >= 0.0


@pytest.mark.asyncio
async def test_nearby_excludes_contributors_outside_radius() -> None:
    """GET /api/nearby does not return contributors beyond radius_km.

    AC-4: only items within the specified radius are returned.
    """
    _make_contributor("hank", "Hank")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Hamburg — ≈254 km from Berlin query point
        await client.patch(
            "/api/contributors/hank/location",
            json={
                "city": "Hamburg",
                "country": "DE",
                "latitude": 53.55,
                "longitude": 10.0,
                "visibility": "public",
            },
        )
        resp = await client.get("/api/nearby?lat=52.52&lon=13.40&radius_km=100")

    assert resp.status_code == 200
    data = resp.json()
    contributor_names = [c["name"] for c in data["contributors"]]
    assert "Hank" not in contributor_names


# ---------------------------------------------------------------------------
# AC 5 — /api/nearby without required params → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nearby_missing_lat_lon_returns_422() -> None:
    """GET /api/nearby without lat/lon returns 422.

    AC-5: missing required query params yield a validation error.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nearby?radius_km=50")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC 6 & 7 — local news resonance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_news_resonance_returns_valid_response() -> None:
    """GET /api/news/resonance/local returns location-tagged items.

    AC-6: response includes location field and items list.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=Berlin")

    assert resp.status_code == 200
    data = resp.json()
    assert "location" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_local_news_resonance_missing_location_returns_422() -> None:
    """GET /api/news/resonance/local without location returns 422.

    AC-7: missing required query param yields validation error.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC 1 edge — invalid visibility value returns 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_location_invalid_visibility_returns_422() -> None:
    """PATCH with an invalid visibility value returns 422.

    AC-1 edge: only public / contributors_only / private are valid.
    """
    _make_contributor("ivan", "Ivan")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/contributors/ivan/location",
            json={
                "city": "Oslo",
                "country": "NO",
                "latitude": 59.91,
                "longitude": 10.75,
                "visibility": "invisible",  # invalid
            },
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC 3 — delete removes contributor from nearby results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_location_removes_contributor_from_nearby() -> None:
    """After DELETE, contributor no longer appears in GET /api/nearby.

    AC-3: right-to-delete clears all geo data.
    """
    _make_contributor("julia", "Julia")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch(
            "/api/contributors/julia/location",
            json={
                "city": "Berlin",
                "country": "DE",
                "latitude": 52.52,
                "longitude": 13.40,
                "visibility": "public",
            },
        )
        # Verify she appears in nearby before deletion
        before = await client.get("/api/nearby?lat=52.52&lon=13.40&radius_km=50")
        names_before = [c["name"] for c in before.json()["contributors"]]
        assert "Julia" in names_before

        await client.delete("/api/contributors/julia/location")

        after = await client.get("/api/nearby?lat=52.52&lon=13.40&radius_km=50")
        names_after = [c["name"] for c in after.json()["contributors"]]
        assert "Julia" not in names_after
