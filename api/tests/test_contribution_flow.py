"""Tests for Contribution as Flow — resonance-weighted contribution scoring.

Flow-centric: HTTP in, JSON out — no internal service imports.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


# ---------------------------------------------------------------------------
# Flow metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_returns_metrics():
    """GET /api/contributions/flow returns flow metrics."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/contributions/flow")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "workspace_id" in body
        assert "total_contributions" in body
        assert "total_cc_flow" in body
        assert "unique_contributors" in body
        assert "ideas_receiving_flow" in body
        assert "flow_per_idea" in body
        assert isinstance(body["flow_per_idea"], list)
        assert "flow_reciprocity" in body
        assert "top_flowing_ideas" in body


@pytest.mark.asyncio
async def test_flow_reciprocity_is_bounded():
    """Flow reciprocity must be between 0 and 1."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/contributions/flow")
        assert r.status_code == 200
        body = r.json()
        assert 0.0 <= body["flow_reciprocity"] <= 1.0


@pytest.mark.asyncio
async def test_flow_period_is_30_days():
    """Period must be 30 days."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/contributions/flow")
        assert r.status_code == 200
        body = r.json()
        assert body["period_days"] == 30


@pytest.mark.asyncio
async def test_flow_workspace_param():
    """Workspace parameter is passed through."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/contributions/flow?workspace_id=test-ws")
        assert r.status_code == 200
        body = r.json()
        assert body["workspace_id"] == "test-ws"
