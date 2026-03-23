"""Tests for API authentication middleware."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


AUTH_HEADERS = {"X-API-Key": "dev-key"}
ADMIN_HEADERS = {"X-Admin-Key": "dev-admin"}


@pytest.mark.asyncio
async def test_post_ideas_without_key_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas is open — no API key needed for idea submission."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/ideas", json={
            "id": "no-key-test",
            "name": "No Key",
            "description": "Should succeed without key",
            "potential_value": 10.0,
            "estimated_cost": 5.0,
        })

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_post_with_correct_key_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas",
            json={
                "id": "correct-key-test",
                "name": "Correct Key",
                "description": "Should succeed",
                "potential_value": 10.0,
                "estimated_cost": 5.0,
            },
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_without_key_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET endpoints remain public (no auth needed)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoint_without_admin_key_returns_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Admin endpoints require X-Admin-Key."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/admin/reset-database")

    # The existing admin endpoint uses X-Admin-Key → returns 403 (its own auth)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_endpoint_with_correct_admin_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Admin endpoint with correct key gets past auth (may fail for other reasons)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("ADMIN_API_KEY", "dev-admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/reset-database",
            headers={"X-Admin-Key": "dev-admin"},
        )

    # The admin endpoint should get past auth. It returns 400 because
    # the test graph store is not PostgreSQL, which is expected.
    assert resp.status_code == 400
    assert "PostgreSQL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_production_mode_with_default_key_returns_500(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """In production mode, default keys must not be accepted on protected endpoints."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("COHERENCE_ENV", "production")

    # We need to reload the auth module to pick up the env change
    import importlib
    import app.middleware.auth as auth_mod
    orig_production = auth_mod._PRODUCTION
    orig_api_key = auth_mod._API_KEY
    try:
        auth_mod._PRODUCTION = True
        auth_mod._API_KEY = "dev-key"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Use a protected endpoint (idea update still requires API key)
            resp = await client.patch(
                "/api/ideas/prod-test",
                json={"actual_value": 42.0},
                headers={"X-API-Key": "dev-key"},
            )

        assert resp.status_code == 500
        assert "production" in resp.json()["detail"].lower()
    finally:
        auth_mod._PRODUCTION = orig_production
        auth_mod._API_KEY = orig_api_key


@pytest.mark.asyncio
async def test_multiple_protected_endpoints_require_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify auth is enforced on several different protected endpoints."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("FEDERATION_STORE_PATH", str(tmp_path / "federation.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST endpoints that still require API key should return 401 without one
        endpoints = [
            ("/api/governance/change-requests", {"request_type": "idea_create", "title": "x", "payload": {}}),
            ("/api/spec-registry", {"spec_id": "x", "title": "x", "summary": "x"}),
            ("/api/value-lineage/links", {"idea_id": "x", "spec_id": "x", "contributors": {}, "estimated_cost": 1}),
        ]

        for url, body in endpoints:
            resp = await client.post(url, json=body)
            assert resp.status_code == 401, f"{url} should require auth, got {resp.status_code}"
