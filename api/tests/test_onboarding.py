"""Tests for identity-driven onboarding (TOFU MVP) — Spec 168.

AC coverage:
  1. POST /api/onboarding/register → 201, contributor_id + session_token + trust_level=tofu
  2. Duplicate handle → 409 handle_taken
  3. GET /api/onboarding/session with valid token → profile
  4. GET /api/onboarding/session with missing/bad token → 401
  5. POST /api/onboarding/upgrade → 200, trust_level=verified
  6. GET /api/onboarding/roi → ROI signals dict
  7. Handle validation: too short, invalid chars → 422
  8. Upgrade unknown contributor → 404
"""
from __future__ import annotations

import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("COHERENCE_ENV", "test")

from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register(client: AsyncClient, handle: str, **kwargs) -> dict:
    resp = await client.post("/api/onboarding/register", json={"handle": handle, **kwargs})
    return resp


# ---------------------------------------------------------------------------
# 1. Happy-path registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_returns_tofu_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _register(client, "alice-test-168a", email="alice@example.com", hint_github="alice")
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["trust_level"] == "tofu"
        assert body["handle"] == "alice-test-168a"
        assert len(body["session_token"]) == 64  # 32 bytes hex
        assert body["created"] is True
        assert "roi_signals" in body
        assert body["roi_signals"]["spec_ref"] == "spec-168"


# ---------------------------------------------------------------------------
# 2. Duplicate handle → 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_duplicate_handle_409() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await _register(client, "bob-test-168b")
        assert first.status_code == 201

        second = await _register(client, "bob-test-168b")
        assert second.status_code == 409
        assert second.json()["detail"] == "handle_taken"


# ---------------------------------------------------------------------------
# 3. Session resolve — valid token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_resolve_valid_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await _register(client, "carol-test-168c", hint_github="carol_gh")
        token = reg.json()["session_token"]

        session = await client.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert session.status_code == 200, session.text
        body = session.json()
        assert body["handle"] == "carol-test-168c"
        assert body["trust_level"] == "tofu"
        assert body["hint_github"] == "carol_gh"
        assert body["linked_identities"] >= 0


# ---------------------------------------------------------------------------
# 4. Session resolve — invalid / missing token → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_invalid_token_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/onboarding/session",
            headers={"Authorization": "Bearer deadbeefdeadbeef"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_session_missing_token_422() -> None:
    """No Authorization header at all → FastAPI returns 422 (missing required header)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/onboarding/session")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. Upgrade TOFU → verified
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upgrade_tofu_to_verified() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await _register(client, "dave-test-168d")
        assert reg.status_code == 201, reg.text
        cid = reg.json()["contributor_id"]

        resp = await client.post(
            "/api/onboarding/upgrade",
            json={"contributor_id": cid, "provider": "github", "provider_id": "dave_gh"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["trust_level"] == "verified"
        assert body["contributor_id"] == cid
        assert body["provider"] == "github"
        assert "roi_signals" in body


@pytest.mark.asyncio
async def test_upgrade_unknown_contributor_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/onboarding/upgrade",
            json={"contributor_id": "onboard:nonexistent123", "provider": "github", "provider_id": "nobody"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_reflects_verified_after_upgrade() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await _register(client, "eve-test-168e")
        assert reg.status_code == 201, reg.text
        reg_body = reg.json()
        token = reg_body["session_token"]
        cid = reg_body["contributor_id"]

        # Upgrade
        up = await client.post(
            "/api/onboarding/upgrade",
            json={"contributor_id": cid, "provider": "ethereum", "provider_id": "0xABCDEF"},
        )
        assert up.status_code == 200, up.text

        # Session should reflect new trust_level
        session = await client.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert session.status_code == 200, session.text
        assert session.json()["trust_level"] == "verified"


# ---------------------------------------------------------------------------
# 6. ROI signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roi_signals_structure() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/onboarding/roi")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "handle_registrations" in body
        assert "verified_count" in body
        assert "verified_ratio" in body
        assert "spec_ref" in body
        assert isinstance(body["handle_registrations"], int)
        assert 0.0 <= body["verified_ratio"] <= 1.0


# ---------------------------------------------------------------------------
# 7. Handle validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_too_short_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _register(client, "ab")  # 2 chars, min is 3
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_handle_invalid_chars_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _register(client, "hello world!")  # spaces and !
        assert resp.status_code == 422
