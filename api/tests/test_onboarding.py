"""Tests for TOFU onboarding (Spec 168 — identity-driven-onboarding).

AC-1  register -> contributor_id, session_token, trust_level=tofu
AC-2  duplicate handle -> 409 handle_taken
AC-3  GET /session valid token -> profile
AC-4  GET /session invalid token -> 401
AC-5  POST /upgrade -> 501 stub (Spec 169)
AC-6  GET /roi -> roi_signals with spec_ref
AC-7  full happy path register->session
AC-8  handle too short -> 422
AC-9  handle invalid chars -> 422
"""
from __future__ import annotations
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


async def _register(client, handle, **kwargs):
    return await client.post("/api/onboarding/register", json={"handle": handle, **kwargs})


@pytest.mark.asyncio
async def test_register_returns_tofu_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "alice-test")
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["trust_level"] == "tofu"
    assert d["handle"] == "alice-test"
    assert len(d["session_token"]) == 64
    assert d["created"] is True
    assert d["roi_signals"]["handle_registrations"] >= 1
    assert d["roi_signals"]["spec_ref"] == "spec-168"


@pytest.mark.asyncio
async def test_duplicate_handle_returns_409(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await _register(c, "bob-test")).status_code == 200
        r2 = await _register(c, "bob-test")
    assert r2.status_code == 409
    assert r2.json()["detail"] == "handle_taken"


@pytest.mark.asyncio
async def test_get_session_valid_token(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = (await _register(c, "carol-test")).json()
        token = reg["session_token"]
        resp = await c.get("/api/onboarding/session", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    p = resp.json()
    assert p["handle"] == "carol-test"
    assert p["trust_level"] == "tofu"
    assert p["contributor_id"] == reg["contributor_id"]


@pytest.mark.asyncio
async def test_get_session_invalid_token_401(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/onboarding/session", headers={"Authorization": "Bearer deadbeef0000"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_session_missing_header_422(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/onboarding/session")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upgrade_returns_501(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/onboarding/upgrade", json={"contributor_id": "onboard:abc", "provider": "github", "provider_id": "gh-1"})
    assert resp.status_code == 501
    assert resp.json()["detail"]["spec_ref"] == "spec-168"


@pytest.mark.asyncio
async def test_roi_signals(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _register(c, "dave-test")
        resp = await c.get("/api/onboarding/roi")
    assert resp.status_code == 200
    roi = resp.json()
    assert roi["handle_registrations"] >= 1
    assert "verified_ratio" in roi
    assert roi["spec_ref"] == "spec-168"


@pytest.mark.asyncio
async def test_full_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = (await _register(c, "eve-test", hint_github="octocat")).json()
        assert reg["trust_level"] == "tofu"
        token = reg["session_token"]
        sess = (await c.get("/api/onboarding/session", headers={"Authorization": f"Bearer {token}"})).json()
        assert sess["hint_github"] == "octocat"
        upg = await c.post("/api/onboarding/upgrade", json={"contributor_id": reg["contributor_id"], "provider": "github", "provider_id": "gh-octocat"})
        assert upg.status_code == 501  # stub until Spec 169


@pytest.mark.asyncio
async def test_handle_too_short_422(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await _register(c, "ab")).status_code == 422


@pytest.mark.asyncio
async def test_handle_invalid_chars_422(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await _register(c, "alice test")).status_code == 422
