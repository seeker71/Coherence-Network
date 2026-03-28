"""Integration tests for Identity-Driven Onboarding (identity-driven-onboarding).

The API routes in ``auth_keys`` import ``app.services.contributor_service``, which is not
present as a submodule in this repository. Tests register a minimal in-memory stub via
``sys.modules`` so the onboarding flow can be exercised without modifying production modules.
"""

from __future__ import annotations

import re
import sys
import types
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Stub: contributor graph CRUD expected by ``auth_keys`` (missing package module)
# ---------------------------------------------------------------------------


def _register_contributor_service_stub() -> None:
    key = "app.services.contributor_service"
    if key in sys.modules:
        return

    mod = types.ModuleType("contributor_service")

    def get_contributor(contributor_id: str):
        from app.services import graph_service

        return graph_service.get_node(f"contributor:{contributor_id}")

    def create_contributor(*, name: str, contributor_type: str = "HUMAN") -> None:
        from app.services import graph_service

        node_id = f"contributor:{name}"
        if graph_service.get_node(node_id):
            return
        graph_service.create_node(
            id=node_id,
            type="contributor",
            name=name,
            description=f"{contributor_type} contributor",
            phase="water",
            properties={
                "contributor_type": contributor_type,
                "email": f"{name}@coherence.network",
                "legacy_id": str(uuid4()),
            },
        )

    mod.get_contributor = get_contributor  # type: ignore[attr-defined]
    mod.create_contributor = create_contributor  # type: ignore[attr-defined]
    sys.modules[key] = mod


_register_contributor_service_stub()

from app.main import app  # noqa: E402
from app.routers import auth_keys  # noqa: E402

REQUIRED_SCOPES = ["own:read", "own:write", "contribute", "stake", "vote"]
KEY_PATTERN = re.compile(r"^cc_(?P<cid>[a-zA-Z0-9\-]+)_(?P<hex>[0-9a-f]{32})$")


@pytest.fixture(autouse=True)
def _reset_onboarding_stores() -> None:
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()
    yield


@pytest.mark.asyncio
async def test_generate_api_key_creates_contributor() -> None:
    """POST /api/auth/keys links identity (TOFU), ensures contributor exists, returns 201."""
    cid = f"onboard-gen-{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": f"gh-{cid}",
            },
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "api_key" in data
    assert data["contributor_id"] == cid
    assert REQUIRED_SCOPES == data["scopes"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        id_resp = await client.get(f"/api/identity/{cid}")
    assert id_resp.status_code == 200
    identities = id_resp.json()
    assert any(
        i.get("provider") == "github"
        and i.get("provider_id") == f"gh-{cid}"
        and i.get("verified") is False
        for i in identities
    )


@pytest.mark.asyncio
async def test_whoami_returns_contributor_info() -> None:
    """GET /api/auth/whoami with generated key returns authenticated contributor + scopes."""
    cid = f"onboard-whoami-{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": f"gh-{cid}",
            },
        )
    assert gen.status_code == 201
    api_key = gen.json()["api_key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        me = await client.get("/api/auth/whoami", headers={"X-API-Key": api_key})
    assert me.status_code == 200
    body = me.json()
    assert body["authenticated"] is True
    assert body["contributor_id"] == cid
    assert body["provider"] == "github"
    assert body["provider_id"] == f"gh-{cid}"
    assert body["scopes"] == REQUIRED_SCOPES


@pytest.mark.asyncio
async def test_duplicate_contributor_is_idempotent() -> None:
    """Contributor create conflict must not be 500; key generation still returns 201."""
    cid = f"onboard-dup-{uuid4().hex[:8]}"
    create_body = {"name": cid, "type": "HUMAN", "email": f"{cid}@coherence.network"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/contributors", json=create_body)
        second = await client.post("/api/contributors", json=create_body)

    assert first.status_code == 201
    assert second.status_code != 500
    assert second.status_code in (409, 422)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        k1 = await client.post(
            "/api/auth/keys",
            json={"contributor_id": cid, "provider": "github", "provider_id": "dup-handle"},
        )
        k2 = await client.post(
            "/api/auth/keys",
            json={"contributor_id": cid, "provider": "github", "provider_id": "dup-handle"},
        )
    assert k1.status_code == 201
    assert k2.status_code == 201
    assert k1.json()["api_key"] != k2.json()["api_key"]


@pytest.mark.asyncio
async def test_key_format_matches_pattern() -> None:
    """Personal API keys match cc_<contributor_id>_<32 hex> (see spec verification scenario)."""
    cid = f"alice-test-{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": "alice-gh-test",
            },
        )
    assert resp.status_code == 201
    raw = resp.json()["api_key"]
    m = KEY_PATTERN.match(raw)
    assert m is not None, raw
    assert m.group("cid") == cid
    assert len(m.group("hex")) == 32


@pytest.mark.asyncio
async def test_scopes_include_required_permissions() -> None:
    """Generated keys expose the five MVP scopes on create and via whoami."""
    cid = f"onboard-scope-{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": f"gh-{cid}",
            },
        )
        assert gen.status_code == 201
        assert gen.json()["scopes"] == REQUIRED_SCOPES
        who = await client.get(
            "/api/auth/whoami",
            headers={"X-API-Key": gen.json()["api_key"]},
        )
    assert who.json()["scopes"] == REQUIRED_SCOPES


@pytest.mark.asyncio
async def test_verification_challenge_flow() -> None:
    """Challenge endpoint returns token + instructions; unknown provider must not 500."""
    cid = f"onboard-chal-{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gh = await client.post(
            "/api/auth/verify/challenge",
            json={
                "contributor_id": cid,
                "provider": "github",
                "challenge": "",
            },
        )
    assert gh.status_code == 200
    payload = gh.json()
    assert re.fullmatch(r"[0-9a-f]{32}", payload["challenge"])
    assert "coherence-verify" in payload["instructions"]
    assert "gist" in payload["instructions"].lower()
    assert payload.get("expires_in")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = await client.post(
            "/api/auth/verify/challenge",
            json={
                "contributor_id": cid,
                "provider": "fakeprovider",
                "challenge": "",
            },
        )
    assert bad.status_code < 500


@pytest.mark.asyncio
async def test_whoami_unauthenticated_message() -> None:
    """No key and invalid key responses match onboarding UX (spec scenario 5)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        none_key = await client.get("/api/auth/whoami")
    assert none_key.status_code == 200
    assert none_key.json() == {
        "authenticated": False,
        "message": "No API key provided. Run: cc setup",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = await client.get(
            "/api/auth/whoami",
            headers={"X-API-Key": "cc_fake_00000000000000000000000000000000"},
        )
    assert bad.status_code == 200
    assert bad.json()["authenticated"] is False
    assert bad.json()["message"] == "Invalid API key"
