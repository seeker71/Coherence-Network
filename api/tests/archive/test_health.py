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
async def test_version_endpoint():
    """GET /api/version returns 200 with the version from setup.py."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_ping_returns_pong_and_timestamp():
    """GET /api/ping returns pong true with a UTC timestamp."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pong"] is True
        assert isinstance(data["timestamp"], str)
        assert data["timestamp"]


@pytest.mark.asyncio
async def test_health_returns_ok():
    """GET /api/health returns 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data
        assert "started_at" in data
        assert isinstance(data["uptime_seconds"], int)
        assert "uptime_human" in data


@pytest.mark.asyncio
async def test_health_exposes_deployed_sha_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123sha")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deployed_sha"] == "abc123sha"
        assert data["deployed_sha_source"] == "RAILWAY_GIT_COMMIT_SHA"


@pytest.mark.asyncio
async def test_ready_returns_ready_when_store_exists(monkeypatch: pytest.MonkeyPatch):
    """GET /api/ready returns 200 when graph_store is set."""
    # Keep this baseline readiness check independent of caller environment variables.
    monkeypatch.setenv("GLOBAL_PERSISTENCE_REQUIRED", "0")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "version" in data
        assert "timestamp" in data
        assert "started_at" in data
        assert isinstance(data["uptime_seconds"], int)
        assert "uptime_human" in data


@pytest.mark.asyncio
async def test_ready_fails_when_global_persistence_required_and_contract_fails(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOBAL_PERSISTENCE_REQUIRED", "1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ready")
        assert resp.status_code == 503
        detail = resp.json().get("detail") or {}
        assert detail.get("error") == "persistence_contract_failed"
        assert isinstance(detail.get("failures"), list)
        assert detail["failures"]


@pytest.mark.asyncio
async def test_persistence_contract_endpoint_returns_domain_report(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOBAL_PERSISTENCE_REQUIRED", "0")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health/persistence")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["required"] is False
        assert "domains" in payload
        assert "ideas" in payload["domains"]
        assert "specs_and_pseudocode" in payload["domains"]
        assert "commit_evidence_tracking" in payload["domains"]


@pytest.mark.asyncio
async def test_health_returns_ok_with_required_fields() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"

    required_fields = [
        "status",
        "version",
        "timestamp",
        "started_at",
        "uptime_seconds",
        "uptime_human",
    ]
    for field in required_fields:
        assert field in payload

    assert isinstance(payload["version"], str)
    assert isinstance(payload["timestamp"], str)
    assert isinstance(payload["started_at"], str)
    assert isinstance(payload["uptime_seconds"], int)
    assert isinstance(payload["uptime_human"], str)
