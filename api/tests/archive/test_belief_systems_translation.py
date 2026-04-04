"""Integration tests for worldview lens registry and spec-181 translations."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_get_lenses_returns_builtin_worldviews() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/lenses")
        assert r.status_code == 200
        data = r.json()
        assert "lenses" in data and data["total"] >= 6
        ids = {x["lens_id"] for x in data["lenses"]}
        for required in ("libertarian", "engineer", "institutionalist", "entrepreneur", "spiritual", "systemic"):
            assert required in ids


@pytest.mark.asyncio
async def test_get_lens_unknown_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/lenses/not-a-real-lens-xyz")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_idea_translation_libertarian_spec181() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "id": "pov-libertarian-test",
            "name": "Decentralized coordination network",
            "description": "Permissionless participation and voluntary alignment without central gatekeepers.",
            "potential_value": 10.0,
            "estimated_cost": 2.0,
            "confidence": 0.7,
            "tags": ["decentralization", "network"],
        }
        c = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
        assert c.status_code == 201

        tr = await client.get("/api/ideas/pov-libertarian-test/translations/libertarian")
        assert tr.status_code == 200
        t = tr.json()
        assert t["idea_id"] == "pov-libertarian-test"
        assert t["lens_id"] == "libertarian"
        assert t["spec_ref"] == "spec-181"
        assert len(t["translated_summary"]) > 20
        assert t["risk_framing"]
        assert t["opportunity_framing"]
        assert isinstance(t["emphasis"], list)


@pytest.mark.asyncio
async def test_idea_translations_batch() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/ideas/pov-libertarian-test/translations")
        assert r.status_code == 200
        data = r.json()
        assert data["idea_id"] == "pov-libertarian-test"
        assert data["total"] == len(data["translations"])
        assert data["total"] >= 5


@pytest.mark.asyncio
async def test_unknown_lens_on_translation_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/ideas/pov-libertarian-test/translations/unknown-lens-abc")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_lenses_roi() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/lenses/roi")
        assert r.status_code == 200
        j = r.json()
        assert j["spec_ref"] == "spec-181"
        assert "total_translations_generated" in j


@pytest.mark.asyncio
async def test_news_feed_pov_filter() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/news/feed", params={"pov": "engineer", "limit": 5})
        assert r.status_code == 200
        j = r.json()
        assert j.get("pov") == "engineer"


@pytest.mark.asyncio
async def test_news_feed_bad_pov_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/news/feed", params={"pov": "klingon-lens"})
        assert r.status_code == 422
