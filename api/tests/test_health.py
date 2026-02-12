"""Tests for health endpoint — spec 001."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_returns_landing_info(client: AsyncClient):
    """GET / returns name, version, docs, health (spec 007)."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/health"


@pytest.mark.asyncio
async def test_docs_returns_200(client: AsyncClient):
    """GET /docs returns 200 (OpenAPI UI reachable, spec 007)."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ready_returns_200(client: AsyncClient):
    """GET /api/ready returns 200 (readiness probe)."""
    response = await client.get("/api/ready")
    assert response.status_code == 200
    assert response.json().get("status") == "ready"


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    """GET /api/health returns 200."""
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cors_allows_origins(client: AsyncClient):
    """CORS middleware allows cross-origin requests."""
    response = await client.get(
        "/api/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    # With allow_origins=["*"], FastAPI returns Access-Control-Allow-Origin: *
    assert "access-control-allow-origin" in [h.lower() for h in response.headers.keys()]


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


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient):
    """Response has exactly the required keys (spec 001)."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"status", "version", "timestamp"}


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(client: AsyncClient):
    """Unhandled exceptions return 500 with generic message (spec 009)."""
    response = await client.get("/api/_test_500")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
