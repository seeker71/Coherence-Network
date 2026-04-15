"""Tests for the /api/auth/keys HTTP layer.

Uses the real `app.main.app` so the attribution middleware, the router,
and the store are all exercised together end-to-end.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import contributor_key_store as store


BASE = "http://test"


def _reset_table() -> None:
    from app.services.unified_db import session as db_session, ensure_schema

    ensure_schema()
    with db_session() as sess:
        sess.query(store.ContributorApiKeyRecord).delete()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# --- GET /api/auth/keys ---------------------------------------------------


@pytest.mark.asyncio
async def test_list_keys_requires_verified_key():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/api/auth/keys")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_keys_rejects_claimed_header_only():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/api/auth/keys", headers={"X-Contributor-Id": "alice"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_keys_returns_own_keys():
    _reset_table()
    alice_key = store.mint("alice", label="laptop")
    store.mint("alice", label="ci")
    store.mint("bob", label="bobs")  # unrelated

    async with await _client() as c:
        r = await c.get(
            "/api/auth/keys",
            headers={"Authorization": f"Bearer {alice_key.raw_key}"},
        )
    assert r.status_code == 200
    data = r.json()
    labels = sorted((k["label"] or "") for k in data["keys"])
    assert labels == ["ci", "laptop"]
    for k in data["keys"]:
        assert k["contributor_id"] == "alice"
        assert "id" in k and len(k["id"]) == 64
        assert "fingerprint" in k
        # Raw key is NEVER in the response.
        assert "raw_key" not in k


# --- DELETE /api/auth/keys/{id} -------------------------------------------


@pytest.mark.asyncio
async def test_revoke_own_key():
    _reset_table()
    # Mint two — we revoke one and keep the other for auth.
    keep = store.mint("alice", label="keep")
    throwaway = store.mint("alice", label="throwaway")

    async with await _client() as c:
        r = await c.delete(
            f"/api/auth/keys/{throwaway.row.id}",
            headers={"Authorization": f"Bearer {keep.raw_key}"},
        )
    assert r.status_code == 204, r.text

    # Verify the throwaway no longer works.
    assert store.verify(throwaway.raw_key) is None


@pytest.mark.asyncio
async def test_revoke_another_contributors_key_returns_404():
    _reset_table()
    alice_key = store.mint("alice")
    bob_key = store.mint("bob", label="target")

    async with await _client() as c:
        r = await c.delete(
            f"/api/auth/keys/{bob_key.row.id}",
            headers={"Authorization": f"Bearer {alice_key.raw_key}"},
        )
    # 404 not 403 — don't leak existence across contributors.
    assert r.status_code == 404
    # Bob's key still works.
    assert store.verify(bob_key.raw_key) is not None


@pytest.mark.asyncio
async def test_revoke_unknown_key_returns_404():
    _reset_table()
    alice_key = store.mint("alice")
    async with await _client() as c:
        r = await c.delete(
            "/api/auth/keys/nonexistent",
            headers={"Authorization": f"Bearer {alice_key.raw_key}"},
        )
    assert r.status_code == 404


# --- POST /api/auth/keys (label echo) -------------------------------------


@pytest.mark.asyncio
async def test_mint_endpoint_accepts_label():
    _reset_table()
    async with await _client() as c:
        r = await c.post(
            "/api/auth/keys",
            json={
                "contributor_id": "alice",
                "provider": "name",
                "provider_id": "alice",
                "label": "my-laptop",
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["label"] == "my-laptop"
    assert body["api_key"].startswith("cc_alice_")
    # Minted key is visible to the store and works for verification.
    row = store.verify(body["api_key"])
    assert row is not None
    assert row.label == "my-laptop"


# --- /api/auth/whoami uses middleware attribution --------------------------


@pytest.mark.asyncio
async def test_whoami_via_verified_bearer():
    _reset_table()
    minted = store.mint("alice")
    async with await _client() as c:
        r = await c.get(
            "/api/auth/whoami",
            headers={"Authorization": f"Bearer {minted.raw_key}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["contributor_id"] == "alice"
    assert body["source"] == "verified"


@pytest.mark.asyncio
async def test_whoami_via_claimed_header():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/api/auth/whoami", headers={"X-Contributor-Id": "alice"})
    assert r.status_code == 200
    body = r.json()
    # "authenticated" reflects *verified* trust, not just attribution
    assert body["authenticated"] is False
    assert body["contributor_id"] == "alice"
    assert body["source"] == "claimed"
