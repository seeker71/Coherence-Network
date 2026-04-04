"""Tests for forward geocoding (OpenCage → Nominatim → fallback) and geo task proximity.

Spec: specs/geolocation-awareness-geocoding.md
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import geolocation_service
from app.services import geocoding_service


# ---------------------------------------------------------------------------
# Geocoding chain (unit)
# ---------------------------------------------------------------------------


def test_forward_geocode_opencage_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenCage is used first when OPENCAGE_API_KEY is present and returns geometry."""

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "results": [
                    {
                        "geometry": {"lat": 52.51, "lng": 13.38},
                        "formatted": "Berlin, Germany",
                    }
                ]
            }

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        def get(self, url: str, **kwargs):
            assert "opencagedata.com" in url
            return _Resp()

        def close(self) -> None:
            pass

    monkeypatch.setenv("OPENCAGE_API_KEY", "test-opencage-key")
    monkeypatch.setattr(geocoding_service.httpx, "Client", _Client)

    r = geocoding_service.forward_geocode("Berlin")
    assert r.found is True
    assert r.source == "opencage"
    assert r.latitude == pytest.approx(52.51, rel=1e-3)
    assert r.longitude == pytest.approx(13.38, rel=1e-3)
    assert r.display_name


def test_forward_geocode_nominatim_when_opencage_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nominatim is used when OpenCage is skipped or returns no results."""

    class _Empty:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"results": []}

    class _Nom:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list:
            return [
                {
                    "lat": "48.8566",
                    "lon": "2.3522",
                    "display_name": "Paris, France",
                }
            ]

    class _Client:
        def __init__(self, *a, **k) -> None:
            self._calls = 0

        def get(self, url: str, **kwargs):
            self._calls += 1
            if "opencagedata.com" in url:
                return _Empty()
            if "nominatim.openstreetmap.org" in url:
                assert "User-Agent" in kwargs.get("headers", {})
                return _Nom()
            raise AssertionError(f"unexpected url {url}")

        def close(self) -> None:
            pass

    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    monkeypatch.setattr(geocoding_service.httpx, "Client", _Client)

    r = geocoding_service.forward_geocode("Paris")
    assert r.found is True
    assert r.source == "nominatim"
    assert r.latitude == pytest.approx(48.86, rel=1e-2)
    assert r.longitude == pytest.approx(2.35, rel=1e-2)


def test_forward_geocode_static_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When remote providers fail, built-in city centers match known tokens."""

    class _Fail:
        def __init__(self, *a, **k) -> None:
            pass

        def get(self, *a, **k):
            raise geocoding_service.httpx.HTTPError("network down")

        def close(self) -> None:
            pass

    monkeypatch.delenv("OPENCAGE_API_KEY", raising=False)
    monkeypatch.setattr(geocoding_service.httpx, "Client", _Fail)

    r = geocoding_service.forward_geocode("Berlin meetup")
    assert r.found is True
    assert r.source == "fallback"
    assert r.latitude == pytest.approx(52.52, rel=1e-2)
    assert r.longitude == pytest.approx(13.41, rel=1e-2)


def test_forward_geocode_short_query_not_found() -> None:
    r = geocoding_service.forward_geocode("x")
    assert r.found is False


# ---------------------------------------------------------------------------
# Agent task proximity (service)
# ---------------------------------------------------------------------------


def test_filter_tasks_by_context_geo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with geo_lat/geo_lon in context are filtered by Haversine radius."""

    fake_tasks = [
        {
            "id": "near-task",
            "direction": "Regional work",
            "status": "pending",
            "task_type": "test",
            "context": {"geo_lat": 52.52, "geo_lon": 13.405},
        },
        {
            "id": "far-task",
            "direction": "Far away",
            "status": "pending",
            "task_type": "test",
            "context": {"geo_lat": 40.0, "geo_lon": -74.0},
        },
    ]

    def fake_list_tasks(limit: int = 20, offset: int = 0, **_kwargs):
        return fake_tasks, len(fake_tasks), 0

    monkeypatch.setattr("app.services.agent_service.list_tasks", fake_list_tasks)

    rows, r_used = geolocation_service.filter_agent_tasks_by_proximity(
        lat=52.52, lon=13.405, radius_km=50.0, limit=10
    )
    assert r_used == 50.0
    ids = [r["task_id"] for r in rows]
    assert "near-task" in ids
    assert "far-task" not in ids
    assert all(r["distance_km"] >= 0.0 for r in rows)


def test_filter_tasks_by_contributor_location(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with contributor_id use stored contributor coordinates."""

    from datetime import datetime, timezone

    from app.models.geolocation import ContributorLocation, LocationVisibility

    fake_tasks = [
        {
            "id": "contrib-task",
            "direction": "Local",
            "status": "pending",
            "task_type": "impl",
            "context": {"contributor_id": "geo-alice"},
        },
    ]

    def fake_list_tasks(limit: int = 20, offset: int = 0, **_kwargs):
        return fake_tasks, 1, 0

    loc = ContributorLocation(
        contributor_id="geo-alice",
        city="Berlin",
        country="DE",
        latitude=52.52,
        longitude=13.405,
        visibility=LocationVisibility.PUBLIC,
        updated_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr("app.services.agent_service.list_tasks", fake_list_tasks)
    monkeypatch.setattr(geolocation_service, "get_contributor_location", lambda _cid: loc)

    rows, _ = geolocation_service.filter_agent_tasks_by_proximity(
        lat=52.52, lon=13.405, radius_km=100.0, limit=10
    )
    assert len(rows) == 1
    assert rows[0]["task_id"] == "contrib-task"
    assert rows[0]["distance_km"] == pytest.approx(0.0, abs=0.5)


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_geocode_forward_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.geocoding import GeocodeForwardResponse, GeocodeSource

    monkeypatch.setattr(
        geocoding_service,
        "forward_geocode",
        lambda q: GeocodeForwardResponse(
            query=q,
            found=True,
            latitude=51.51,
            longitude=-0.13,
            display_name="London",
            source=GeocodeSource.FALLBACK.value,
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/geocode/forward?q=London+UK")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["source"] == "fallback"
    assert "latitude" in body


@pytest.mark.asyncio
async def test_api_geocode_forward_query_too_short_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/geocode/forward?q=x")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_geo_tasks_nearby_validation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/geo/tasks/nearby?lat=200&lon=0&radius_km=50")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_geo_tasks_nearby_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        geolocation_service,
        "filter_agent_tasks_by_proximity",
        lambda **kw: (
            [
                {
                    "task_id": "t1",
                    "direction": "d",
                    "status": "pending",
                    "task_type": "impl",
                    "distance_km": 1.0,
                }
            ],
            50.0,
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/geo/tasks/nearby?lat=0&lon=0&radius_km=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["tasks"][0]["task_id"] == "t1"
