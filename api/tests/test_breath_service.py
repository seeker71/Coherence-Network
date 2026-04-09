"""Tests for Breath-Aware Lifecycle — gas/water/ice phase distribution.

Flow-centric: HTTP in, JSON out — no internal service imports.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "breath-idea") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    iid = idea_id or _uid()
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Description for breath test {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Breath endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_breath_returns_rhythm():
    """GET /api/ideas/{id}/breath returns rhythm with gas/water/ice."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        idea = await _create_idea(c)
        r = await c.get(f"/api/ideas/{idea['id']}/breath")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rhythm" in body
        rhythm = body["rhythm"]
        assert "gas" in rhythm
        assert "water" in rhythm
        assert "ice" in rhythm
        assert body["idea_id"] == idea["id"]
        assert "total_specs" in body
        assert "state" in body


@pytest.mark.asyncio
async def test_breath_health_is_bounded():
    """Breath health must be between 0 and 1."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        idea = await _create_idea(c)
        r = await c.get(f"/api/ideas/{idea['id']}/breath")
        assert r.status_code == 200
        body = r.json()
        assert 0.0 <= body["breath_health"] <= 1.0


@pytest.mark.asyncio
async def test_breath_overview_returns_ideas():
    """GET /api/ideas/breath-overview returns portfolio breath data."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/breath-overview")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "ideas" in body
        assert isinstance(body["ideas"], list)
        assert "portfolio_rhythm" in body
        assert "portfolio_breath_health" in body
        pr = body["portfolio_rhythm"]
        assert "gas" in pr
        assert "water" in pr
        assert "ice" in pr
        assert 0.0 <= body["portfolio_breath_health"] <= 1.0


@pytest.mark.asyncio
async def test_breath_state_values():
    """Breath state must be one of the valid states."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        idea = await _create_idea(c)
        r = await c.get(f"/api/ideas/{idea['id']}/breath")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] in ("breathing", "inhaling", "exhaling", "holding")


@pytest.mark.asyncio
async def test_breath_404_for_nonexistent():
    """GET /api/ideas/{bad_id}/breath returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/nonexistent-breath-idea/breath")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Resonance endpoint on ideas router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_resonance_returns_list():
    """GET /api/ideas/{id}/resonance returns a list (possibly empty)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        idea = await _create_idea(c)
        r = await c.get(f"/api/ideas/{idea['id']}/resonance")
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
