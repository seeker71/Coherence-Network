"""Tests for the attribution middleware.

We build a minimal FastAPI app containing only the middleware and one
probe route, so these tests are fast and decoupled from the rest of the
API surface. The store is exercised for real — same DB the store uses
in production.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.attribution import AttributionMiddleware
from app.services import contributor_key_store as store


def _reset_table() -> None:
    from app.services.unified_db import session as db_session, ensure_schema

    ensure_schema()
    with db_session() as sess:
        sess.query(store.ContributorApiKeyRecord).delete()


def _build_probe_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AttributionMiddleware)

    @app.get("/_probe")
    async def probe(request: Request):
        return {
            "contributor_id": getattr(request.state, "contributor_id", None),
            "source": getattr(request.state, "attribution_source", None),
            "scopes": list(getattr(request.state, "contributor_scopes", []) or []),
        }

    return app


async def _client():
    return AsyncClient(transport=ASGITransport(app=_build_probe_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_no_headers_yields_none_attribution():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/_probe")
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] is None
    assert body["source"] is None
    assert body["scopes"] == []
    # Response header still reports "none" so clients know we looked.
    assert r.headers.get("X-Attribution-Source") == "none"
    assert "X-Attributed-To" not in r.headers


@pytest.mark.asyncio
async def test_verified_key_attributes_and_echoes_headers():
    _reset_table()
    minted = store.mint("alice", label="laptop")
    async with await _client() as c:
        r = await c.get(
            "/_probe",
            headers={"Authorization": f"Bearer {minted.raw_key}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["source"] == "verified"
    assert "own:read" in body["scopes"]
    assert r.headers["X-Attributed-To"] == "alice"
    assert r.headers["X-Attribution-Source"] == "verified"


@pytest.mark.asyncio
async def test_revoked_key_does_not_attribute():
    _reset_table()
    minted = store.mint("alice")
    store.revoke(minted.row.id, owner_contributor_id="alice")
    async with await _client() as c:
        r = await c.get(
            "/_probe",
            headers={"Authorization": f"Bearer {minted.raw_key}"},
        )
    body = r.json()
    assert body["contributor_id"] is None
    assert body["source"] is None
    assert r.headers.get("X-Attribution-Source") == "none"


@pytest.mark.asyncio
async def test_claimed_contributor_id_header_only():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/_probe", headers={"X-Contributor-Id": "alice"})
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["source"] == "claimed"
    assert body["scopes"] == []
    assert r.headers["X-Attributed-To"] == "alice"
    assert r.headers["X-Attribution-Source"] == "claimed"


@pytest.mark.asyncio
async def test_verified_key_wins_over_claimed_header():
    _reset_table()
    minted = store.mint("alice", label="laptop")
    async with await _client() as c:
        r = await c.get(
            "/_probe",
            headers={
                "Authorization": f"Bearer {minted.raw_key}",
                "X-Contributor-Id": "bob",  # lie
            },
        )
    body = r.json()
    assert body["contributor_id"] == "alice"  # verified wins
    assert body["source"] == "verified"


@pytest.mark.asyncio
async def test_non_bearer_authorization_header_falls_through():
    _reset_table()
    async with await _client() as c:
        r = await c.get(
            "/_probe",
            headers={"Authorization": "Basic some-basic-auth-blob"},
        )
    body = r.json()
    assert body["contributor_id"] is None
    assert body["source"] is None


@pytest.mark.asyncio
async def test_bearer_with_wrong_prefix_is_not_looked_up():
    _reset_table()
    async with await _client() as c:
        r = await c.get(
            "/_probe",
            headers={"Authorization": "Bearer not-a-cc-key"},
        )
    body = r.json()
    # Bearer but not cc_ → middleware does not look up the store.
    assert body["contributor_id"] is None


@pytest.mark.asyncio
async def test_empty_contributor_id_header_ignored():
    _reset_table()
    async with await _client() as c:
        r = await c.get("/_probe", headers={"X-Contributor-Id": "   "})
    body = r.json()
    assert body["contributor_id"] is None
    assert body["source"] is None
