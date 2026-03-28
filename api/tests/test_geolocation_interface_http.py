"""HTTP-level acceptance tests for Geolocation Interface (geolocation-interface).

Fills gaps vs specs/170-geo-location.md acceptance criteria where coverage was
only at the service layer:

  AC-1  PATCH response rounds latitude/longitude to two decimal places (HTTP).
  AC-6  GET /api/news/resonance/local returns location, items, total (HTTP).
  AC-7  GET /api/news/resonance/local without location query → 422 (HTTP).
"""
from __future__ import annotations

import sys
import types

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.geolocation import LocalNewsResonanceResponse
from app.services import geolocation_service, graph_service


def _make_contributor(node_id: str, name: str) -> dict:
    return graph_service.create_node(
        id=f"contributor:{node_id}",
        type="contributor",
        name=name,
    )


@pytest.mark.asyncio
async def test_patch_location_http_rounds_coordinates_to_two_decimals() -> None:
    """AC-1: router rounds coords; JSON body uses two-decimal precision."""
    _make_contributor("http-round-ac1", "HTTP Round")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/contributors/http-round-ac1/location",
            json={
                "city": "Vienna",
                "country": "AT",
                "latitude": 48.123456789,
                "longitude": 16.987654321,
                "visibility": "public",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["latitude"] == pytest.approx(48.12, abs=1e-9)
    assert data["longitude"] == pytest.approx(16.99, abs=1e-9)


@pytest.mark.asyncio
async def test_local_news_resonance_http_missing_location_returns_422() -> None:
    """AC-7: location query parameter is required."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_local_news_resonance_http_empty_location_returns_422() -> None:
    """AC-7: empty location fails min_length validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_local_news_resonance_http_returns_json_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: response includes location, items with bounded resonance_score, total."""
    fake_articles = [
        {
            "id": "art-http-1",
            "title": "Oslo climate initiative expands",
            "summary": "Leaders in Oslo announced new green targets.",
            "url": "https://example.com/oslo",
            "source": "NRK",
            "published_at": "2026-03-28T12:00:00Z",
        }
    ]
    fake_nis = types.ModuleType("app.services.news_ingestion_service")
    fake_nis.get_recent_articles = lambda limit=200: fake_articles  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.services.news_ingestion_service", fake_nis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=Oslo&limit=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["location"] == "Oslo"
    assert "items" in body and isinstance(body["items"], list)
    assert "total" in body
    assert body["total"] == len(body["items"])
    for item in body["items"]:
        assert 0.0 <= item["resonance_score"] <= 1.0


@pytest.mark.asyncio
async def test_local_news_resonance_http_unmatched_location_empty_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-7: no matching articles yields empty items (HTTP 200, not 5xx)."""
    monkeypatch.setattr(
        geolocation_service,
        "local_news_resonance",
        lambda location, limit=20: LocalNewsResonanceResponse(
            location=location, items=[], total=0
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/news/resonance/local?location=ZZNoMatchCity999")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0
