"""Acceptance tests for Identity Driven Onboarding (identity-driven-onboarding).

Validates API flows in ``app.routers.auth_keys``: identity-linked API keys,
verification challenges, proof submission, and ``whoami``.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _clear_auth_key_stores() -> None:
    """Isolate in-memory key and challenge state between tests."""
    from app.routers import auth_keys

    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()
    yield
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _unique_contributor(prefix: str = "ido") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def test_post_auth_keys_creates_key_with_expected_scopes_and_prefix(client: TestClient) -> None:
    """Contributor receives a one-time API key with onboarding scopes."""
    cid = _unique_contributor()
    resp = client.post(
        "/api/auth/keys",
        json={
            "contributor_id": cid,
            "provider": "github",
            "provider_id": "octocat",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contributor_id"] == cid
    assert data["api_key"].startswith("cc_")
    assert "own:read" in data["scopes"]
    assert "contribute" in data["scopes"]
    assert "created_at" in data


def test_post_auth_keys_links_identity_for_attribution(client: TestClient) -> None:
    """Key issuance links provider identity to contributor (verified=False until proof)."""
    from app.services import contributor_identity_service

    cid = _unique_contributor()
    client.post(
        "/api/auth/keys",
        json={
            "contributor_id": cid,
            "provider": "github",
            "provider_id": "dev-user",
        },
    )
    identities = contributor_identity_service.get_identities(cid)
    assert any(
        i.get("provider") == "github" and i.get("provider_id") == "dev-user"
        for i in identities
    )


def test_verify_challenge_github_includes_coherence_verify_line(client: TestClient) -> None:
    """GitHub challenge instructions reference the gist pattern with contributor id."""
    cid = _unique_contributor()
    r = client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "github", "challenge": "ignored"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "challenge" in body and len(body["challenge"]) >= 8
    assert "instructions" in body
    assert f"coherence-verify:{cid}:" in body["instructions"]
    assert "gist" in body["instructions"].lower()


def test_verify_challenge_wallet_providers_expect_signature(client: TestClient) -> None:
    """Ethereum/Solana challenges ask for a signed message."""
    for provider in ("ethereum", "solana"):
        cid = _unique_contributor(f"wal-{provider}")
        r = client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": cid, "provider": provider, "challenge": "x"},
        )
        assert r.status_code == 200
        ins = r.json()["instructions"]
        assert "Sign" in ins or "sign" in ins
        assert f"coherence-verify:{cid}:" in ins


def test_verify_challenge_generic_provider_includes_token(client: TestClient) -> None:
    """Non-GitHub non-wallet providers get generic profile/bio instructions."""
    cid = _unique_contributor()
    r = client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "mastodon", "challenge": "x"},
    )
    assert r.status_code == 200
    token = r.json()["challenge"]
    assert token in r.json()["instructions"]


def test_verify_proof_rejects_without_prior_challenge(client: TestClient) -> None:
    """Proof submission requires POST /auth/verify/challenge first."""
    cid = _unique_contributor()
    r = client.post(
        "/api/auth/verify/proof",
        json={
            "contributor_id": cid,
            "provider": "github",
            "provider_id": "u",
            "proof": "https://gist.github.com/x",
        },
    )
    assert r.status_code == 400
    assert "challenge" in r.json()["detail"].lower()


def test_verify_proof_rejects_provider_mismatch(client: TestClient) -> None:
    """Pending challenge provider must match proof submission."""
    cid = _unique_contributor()
    client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "github", "challenge": "x"},
    )
    r = client.post(
        "/api/auth/verify/proof",
        json={
            "contributor_id": cid,
            "provider": "ethereum",
            "provider_id": "0xabc",
            "proof": "sig",
        },
    )
    assert r.status_code == 400


def test_verify_proof_ethereum_accepts_signature_containing_challenge_token(
    client: TestClient,
) -> None:
    """MVP wallet path treats proof containing the challenge token as valid."""
    cid = _unique_contributor()
    ch = client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "ethereum", "challenge": "x"},
    ).json()
    token = ch["challenge"]
    r = client.post(
        "/api/auth/verify/proof",
        json={
            "contributor_id": cid,
            "provider": "ethereum",
            "provider_id": "0xwallet",
            "proof": f"0xdeadbeef:{token}",
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["verified"] is True
    assert out["contributor_id"] == cid


def test_verify_proof_ethereum_rejects_missing_challenge_token(client: TestClient) -> None:
    """Wallet proof without the active challenge token is rejected."""
    cid = _unique_contributor()
    client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "ethereum", "challenge": "x"},
    )
    r = client.post(
        "/api/auth/verify/proof",
        json={
            "contributor_id": cid,
            "provider": "ethereum",
            "provider_id": "0xwallet",
            "proof": "0xdeadbeef:no-token-here",
        },
    )
    assert r.status_code == 400
    assert "challenge" in r.json()["detail"].lower() or "token" in r.json()["detail"].lower()


def test_verify_proof_github_fetches_url_and_checks_gist_content(client: TestClient) -> None:
    """GitHub proof fetches the URL and checks for coherence-verify line."""
    cid = _unique_contributor()
    ch = client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "github", "challenge": "x"},
    ).json()
    token = ch["challenge"]
    line = f"coherence-verify:{cid}:{token}"
    mock_resp = MagicMock()
    mock_resp.text = f"hello\n{line}\n"
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        r = client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": "gh-user",
                "proof": "https://gist.githubusercontent.com/x/raw/y",
            },
        )
    assert r.status_code == 200
    mock_get.assert_called_once()
    assert r.json()["verified"] is True


def test_verify_proof_github_fetch_failure_returns_400(client: TestClient) -> None:
    """Broken gist URL yields a 400 from the GitHub verification path."""
    cid = _unique_contributor()
    client.post(
        "/api/auth/verify/challenge",
        json={"contributor_id": cid, "provider": "github", "challenge": "x"},
    )
    with patch("httpx.get", side_effect=OSError("network")):
        r = client.post(
            "/api/auth/verify/proof",
            json={
                "contributor_id": cid,
                "provider": "github",
                "provider_id": "u",
                "proof": "https://example.com/bad",
            },
        )
    assert r.status_code == 400


def test_whoami_authenticates_with_issued_api_key(client: TestClient) -> None:
    """Issued key is accepted via ``x_api_key`` query param on ``GET /auth/whoami``."""
    cid = _unique_contributor()
    key_resp = client.post(
        "/api/auth/keys",
        json={
            "contributor_id": cid,
            "provider": "github",
            "provider_id": "whoami-user",
        },
    )
    api_key = key_resp.json()["api_key"]
    # whoami binds ``x_api_key`` without ``Header()`` — it is a query parameter.
    r = client.get("/api/auth/whoami", params={"x_api_key": api_key})
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["contributor_id"] == cid


def test_whoami_without_key_reports_unauthenticated(client: TestClient) -> None:
    """Missing API key is explicitly unauthenticated."""
    r = client.get("/api/auth/whoami")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False
