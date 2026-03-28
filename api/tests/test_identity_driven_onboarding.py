"""Acceptance tests for Identity Driven Onboarding (identity-driven-onboarding).

Covers `api/app/routers/auth_keys.py`: contributor-linked API keys, verification
challenges, and proof submission. The spec slug is `identity-driven-onboarding`.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# `auth_keys` imports `contributor_service` lazily; the submodule may be absent
# in minimal trees. Register a minimal stub before loading the app.
# ---------------------------------------------------------------------------
_CS = "app.services.contributor_service"
if _CS not in sys.modules:

    def _stub_get_contributor(_contributor_id: str) -> None:
        return None

    def _stub_create_contributor(**_kwargs: object) -> dict:
        return {}

    _mod = types.ModuleType("contributor_service")
    _mod.get_contributor = _stub_get_contributor
    _mod.create_contributor = _stub_create_contributor
    sys.modules[_CS] = _mod

from app.main import app
from app.routers import auth_keys


@pytest.fixture(autouse=True)
def _isolate_auth_stores() -> None:
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()
    yield
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()


@pytest.mark.asyncio
async def test_post_auth_keys_returns_key_scopes_and_timestamps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Linked identity yields a personal API key; response includes scopes and ISO time."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": "onboard-tester",
                "provider": "github",
                "provider_id": "octocat",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["contributor_id"] == "onboard-tester"
    assert data["api_key"].startswith("cc_onboard-tester_")
    assert "T" in data["created_at"] or "-" in data["created_at"]
    assert set(data["scopes"]) >= {"own:read", "own:write", "contribute"}


@pytest.mark.asyncio
async def test_whoami_with_generated_key_resolves_contributor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Whoami returns authenticated contributor payload for a key from POST /auth/keys."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/auth/keys",
            json={
                "contributor_id": "whoami-user",
                "provider": "github",
                "provider_id": "dev1",
            },
        )
        assert create.status_code == 201
        api_key = create.json()["api_key"]

        # FastAPI treats bare `x_api_key` on this route as a query param (not X-API-Key header).
        me = await client.get("/api/auth/whoami", params={"x_api_key": api_key})

    assert me.status_code == 200
    body = me.json()
    assert body["authenticated"] is True
    assert body["contributor_id"] == "whoami-user"
    assert "scopes" in body


@pytest.mark.asyncio
async def test_whoami_without_key_is_unauthenticated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        me = await client.get("/api/auth/whoami")

    assert me.status_code == 200
    assert me.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_verify_challenge_github_includes_gist_instructions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GitHub challenge instructions describe a public gist containing coherence-verify text."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/verify/challenge",
            json={
                "contributor_id": "gh-user",
                "provider": "github",
                "challenge": "ignored-by-server",
            },
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert "challenge" in payload and len(payload["challenge"]) >= 8
    assert "instructions" in payload
    inst = payload["instructions"]
    assert "gist" in inst.lower()
    assert "coherence-verify:gh-user:" in inst
    assert payload.get("expires_in")


@pytest.mark.asyncio
async def test_verify_challenge_wallet_provider_sign_instructions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/verify/challenge",
            json={
                "contributor_id": "wallet-user",
                "provider": "ethereum",
                "challenge": "x",
            },
        )

    assert resp.status_code == 200
    inst = resp.json()["instructions"]
    assert "Sign" in inst or "sign" in inst
    assert "coherence-verify:wallet-user:" in inst


@pytest.mark.asyncio
async def test_verify_proof_without_challenge_returns_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": "no-challenge",
                "provider": "github",
                "provider_id": "x",
                "proof": "https://gist.github.com/x",
            },
        )

    assert resp.status_code == 400
    assert "challenge" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_proof_wrong_provider_after_challenge_returns_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": "u1", "provider": "github", "challenge": "c"},
        )
        resp = await client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": "u1",
                "provider": "ethereum",
                "provider_id": "0xabc",
                "proof": "sig",
            },
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_proof_ethereum_accepts_proof_containing_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ch = await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": "eth-1", "provider": "ethereum", "challenge": "c"},
        )
        token = ch.json()["challenge"]
        resp = await client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": "eth-1",
                "provider": "ethereum",
                "provider_id": "0xdeadbeef",
                "proof": f"0xsig:{token}:payload",
            },
        )

    assert resp.status_code == 200
    out = resp.json()
    assert out["verified"] is True
    assert out["provider"] == "ethereum"


@pytest.mark.asyncio
@respx.mock
async def test_verify_proof_github_fetches_gist_and_checks_challenge_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ch = await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": "gist-user", "provider": "github", "challenge": "c"},
        )
        token = ch.json()["challenge"]
        gist_url = "https://gist.githubusercontent.com/gist-user/abc/raw/snippet.txt"
        expected_line = f"coherence-verify:gist-user:{token}"
        respx.get(gist_url).mock(return_value=httpx.Response(200, text=expected_line))

        resp = await client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": "gist-user",
                "provider": "github",
                "provider_id": "gist-user",
                "proof": gist_url,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["verified"] is True


@pytest.mark.asyncio
async def test_verify_proof_generic_provider_matches_token_in_proof(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ch = await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": "disc", "provider": "discord", "challenge": "c"},
        )
        token = ch.json()["challenge"]
        resp = await client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": "disc",
                "provider": "discord",
                "provider_id": "user#123",
                "proof": f"profile https://x.com/y {token}",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["verified"] is True
