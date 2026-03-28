"""Extended tests for Identity-Driven Onboarding TOFU MVP (Spec 168).

Additional edge-case and boundary coverage beyond test_onboarding.py:

AC-1  register response shape — contributor_id prefix, token length, roi_signals keys
AC-2  handle boundary validation — min (3), max (40), too-long (41) chars
AC-3  duplicate handle 409, case-normalisation idempotency
AC-4  GET /session — optional fields persisted and returned
AC-5  POST /upgrade stub — full detail shape verified
AC-6  GET /roi — empty-state shape and multi-registration counts
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


async def _register(client, handle, **kwargs):
    return await client.post("/api/onboarding/register", json={"handle": handle, **kwargs})


# ---------------------------------------------------------------------------
# AC-1 — Response shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contributor_id_has_onboard_prefix(tmp_path, monkeypatch):
    """contributor_id must start with 'onboard:' per service implementation."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "pre-test1")
    assert resp.status_code == 200
    assert resp.json()["contributor_id"].startswith("onboard:")


@pytest.mark.asyncio
async def test_session_token_is_64_hex_chars(tmp_path, monkeypatch):
    """session_token must be exactly 64 lowercase hex characters."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "pre-test2")
    token = resp.json()["session_token"]
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)


@pytest.mark.asyncio
async def test_register_roi_signals_contains_required_keys(tmp_path, monkeypatch):
    """roi_signals in register response must include all AC-6 keys."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "pre-test3")
    roi = resp.json()["roi_signals"]
    for key in ("handle_registrations", "verified_count", "verified_ratio",
                "avg_time_to_verify_days", "spec_ref"):
        assert key in roi, f"Missing roi_signals key: {key}"
    assert roi["spec_ref"] == "spec-168"


# ---------------------------------------------------------------------------
# AC-2 — Handle boundary validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_min_length_3_is_valid(tmp_path, monkeypatch):
    """A 3-character handle satisfies the lower boundary."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "abc")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_handle_max_length_40_is_valid(tmp_path, monkeypatch):
    """A 40-character handle satisfies the upper boundary."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    handle = "a" * 40
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, handle)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_handle_41_chars_returns_422(tmp_path, monkeypatch):
    """A 41-character handle exceeds the maximum and must return 422."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    handle = "a" * 41
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, handle)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_handle_with_numbers_and_underscore_valid(tmp_path, monkeypatch):
    """Handles with numbers and underscores are valid per AC-2 regex."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "user_42")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_handle_with_special_chars_returns_422(tmp_path, monkeypatch):
    """Handles containing @ are invalid per AC-2 and must return 422."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await _register(c, "alice@domain")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC-3 — Duplicate handle / case normalisation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_uppercase_handle_normalised_and_deduped(tmp_path, monkeypatch):
    """Uppercase handles are lowercased before storage; re-registering 409."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await _register(c, "FRANK-test")
        assert r1.status_code == 200
        assert r1.json()["handle"] == "frank-test"
        r2 = await _register(c, "frank-test")
    assert r2.status_code == 409
    assert r2.json()["detail"] == "handle_taken"


# ---------------------------------------------------------------------------
# AC-4 — Session profile with optional fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_returns_email_and_wallet_hints(tmp_path, monkeypatch):
    """Optional fields email, hint_wallet persisted and returned in /session."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = (await _register(
            c, "grace-test",
            email="grace@example.com",
            hint_wallet="0xABCDEF1234567890"
        )).json()
        token = reg["session_token"]
        sess = (await c.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {token}"}
        )).json()
    assert sess["email"] == "grace@example.com"
    assert sess["hint_wallet"] == "0xABCDEF1234567890"


@pytest.mark.asyncio
async def test_session_linked_identities_is_integer(tmp_path, monkeypatch):
    """linked_identities field in /session must be an integer."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = (await _register(c, "henry-test")).json()
        token = reg["session_token"]
        sess = (await c.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {token}"}
        )).json()
    assert isinstance(sess["linked_identities"], int)
    assert sess["linked_identities"] >= 0


# ---------------------------------------------------------------------------
# AC-5 — Upgrade stub detail shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upgrade_stub_detail_has_upgrade_path(tmp_path, monkeypatch):
    """POST /upgrade 501 detail must include upgrade_path with github and ethereum keys."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/onboarding/upgrade", json={
            "contributor_id": "onboard:stub",
            "provider": "github",
            "provider_id": "gh-99",
        })
    assert resp.status_code == 501
    detail = resp.json()["detail"]
    assert "upgrade_path" in detail
    assert "github" in detail["upgrade_path"]
    assert "ethereum" in detail["upgrade_path"]
    assert detail["current_trust_level"] == "tofu"


# ---------------------------------------------------------------------------
# AC-6 — ROI endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roi_empty_state(tmp_path, monkeypatch):
    """GET /roi with no registrations returns zeros and spec_ref."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/onboarding/roi")
    assert resp.status_code == 200
    roi = resp.json()
    assert roi["handle_registrations"] == 0
    assert roi["verified_count"] == 0
    assert roi["verified_ratio"] == 0.0
    assert roi["spec_ref"] == "spec-168"


@pytest.mark.asyncio
async def test_roi_counts_increment_per_registration(tmp_path, monkeypatch):
    """Each registration increments handle_registrations in /roi."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ct.db")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _register(c, "user-roi-1")
        await _register(c, "user-roi-2")
        await _register(c, "user-roi-3")
        resp = await c.get("/api/onboarding/roi")
    assert resp.status_code == 200
    assert resp.json()["handle_registrations"] == 3
