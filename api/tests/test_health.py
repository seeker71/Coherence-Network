"""Test operational endpoints (/, /api/health, /api/ready)."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_root_redirects_to_docs():
    """GET / redirects to /docs."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/")
        assert resp.status_code == 307
        assert resp.headers["location"] == "/docs"


@pytest.mark.asyncio
async def test_health_returns_ok():
    """GET /api/health returns 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "service" in data


@pytest.mark.asyncio
async def test_ready_returns_ready_when_store_exists():
    """GET /api/ready returns 200 when graph_store is set."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
