"""Tests for health endpoint — spec 001.

These tests define the API contract for GET /api/health (spec 001).
Do not modify tests to make implementation pass; fix the implementation instead.

Spec 001 acceptance tests (all must pass). Requirement → Test mapping:
  - GET /api/health returns 200 → test_health_returns_200
  - Response is valid JSON (Content-Type application/json; body parses as JSON) → test_health_response_is_valid_json
  - Response includes required fields (status, version, timestamp); status is "ok"; basic ISO8601 → test_health_returns_valid_json
  - timestamp is ISO8601 UTC (parseable; Z or +00:00) → test_health_timestamp_iso8601_utc
  - Response has exactly the required keys (no extra top-level keys) → test_health_response_schema
  - version is semantic-version format (^\\d+\\.\\d+\\.\\d+) → test_health_version_semver
  - Response fields (status, version, timestamp) are strings → test_health_response_value_types
  - Full API contract (200, exact keys, status ok, semver, ISO8601 UTC) → test_health_api_contract

Verification: Every spec 001 requirement has exactly one corresponding test; no requirement is untested.

Spec 007 (landing/docs): Requirement → Test mapping:
  - GET /docs returns 200 (OpenAPI UI reachable) → test_docs_returns_200

Run 001-only tests: cd api && pytest tests/test_health.py -v -k 'health'
Run docs contract test: cd api && pytest tests/test_health.py::test_docs_returns_200 -v
"""

import re
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def client():
    """ASGI client for testing (spec 001, 007, 009, 014)."""
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
    response = await client.get("/docs", follow_redirects=True)
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
async def test_health_response_is_valid_json(client: AsyncClient):
    """Response is valid JSON (Content-Type application/json; body parses as JSON). — spec 001"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    ct = response.headers.get("content-type", "")
    assert "application/json" in ct
    data = response.json()  # must not raise
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_health_returns_valid_json(client: AsyncClient):
    """Response includes required fields (status, version, timestamp; basic ISO8601). — spec 001"""
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
    """Response has exactly the required keys (no extra top-level keys). — spec 001"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    required = {"status", "version", "timestamp"}
    assert set(data.keys()) == required, "response must have exactly status, version, timestamp"
    assert len(data) == 3, "response must have no extra top-level keys"


@pytest.mark.asyncio
async def test_health_timestamp_iso8601_utc(client: AsyncClient):
    """timestamp is ISO8601 UTC (parseable; Z or +00:00). — spec 001"""
    response = await client.get("/api/health")
    data = response.json()
    ts = data["timestamp"]
    assert ts.endswith("Z") or ts.endswith("+00:00"), "timestamp must end with Z or +00:00"
    # Parse as ISO8601; normalize Z to +00:00 for fromisoformat
    normalized = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    assert dt.tzinfo is not None, "timestamp must be UTC (Z or +00:00)"


@pytest.mark.asyncio
async def test_health_version_semver(client: AsyncClient):
    """version is semantic-version format (version matches ^\\d+\\.\\d+\\.\\d+). — spec 001"""
    response = await client.get("/api/health")
    data = response.json()
    version = data["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"version must match exactly MAJOR.MINOR.PATCH: {version}"


@pytest.mark.asyncio
async def test_health_response_value_types(client: AsyncClient):
    """Response fields are strings per spec 001: status, version, timestamp."""
    response = await client.get("/api/health")
    data = response.json()
    assert isinstance(data["status"], str), "status must be string"
    assert isinstance(data["version"], str), "version must be string"
    assert isinstance(data["timestamp"], str), "timestamp must be string"


@pytest.mark.asyncio
async def test_health_api_contract(client: AsyncClient):
    """Full API contract for GET /api/health (spec 001): 200, exact keys, status ok, semver, ISO8601 UTC."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/json")
    data = response.json()
    assert set(data.keys()) == {"status", "version", "timestamp"}
    assert data["status"] == "ok"
    assert re.fullmatch(r"\d+\.\d+\.\d+", data["version"]), f"version must match MAJOR.MINOR.PATCH: {data['version']}"
    ts = data["timestamp"]
    assert ts.endswith("Z") or ts.endswith("+00:00"), "timestamp must end with Z or +00:00"
    normalized = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    assert dt.tzinfo is not None, "timestamp must be ISO8601 UTC (Z or +00:00)"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(client: AsyncClient):
    """Unhandled exceptions return 500 with generic message (spec 009)."""
    response = await client.get("/api/_test_500")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
