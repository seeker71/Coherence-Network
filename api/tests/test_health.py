"""Tests for health endpoint — spec 001."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    """GET /api/health returns 200."""
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_valid_json(client: AsyncClient):
    """Response includes status, version, timestamp (ISO8601)."""
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    # Basic ISO8601 check
    ts = data["timestamp"]
    assert "T" in ts and "Z" in ts
