"""Tests for the identity provider registry and expanded identity endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.services.identity_providers import (
    PROVIDER_REGISTRY,
    SUPPORTED_PROVIDERS,
    get_categories,
    get_provider_info,
    registry_as_dict,
)


# ---------------------------------------------------------------------------
# Provider registry unit tests
# ---------------------------------------------------------------------------


def test_provider_count():
    """Registry should contain 37 providers across 6 categories."""
    assert len(SUPPORTED_PROVIDERS) == 37
    assert len(PROVIDER_REGISTRY) == 6


def test_categories():
    cats = get_categories()
    assert cats == ["Social", "Dev", "Crypto / Web3", "Professional", "Identity", "Custom"]


def test_original_providers_still_present():
    """All original 7 providers must still be in the expanded list."""
    for key in ("github", "google", "ethereum", "bitcoin", "email", "x", "name"):
        assert key in SUPPORTED_PROVIDERS, f"Original provider '{key}' missing"


def test_new_providers_present():
    """Spot-check new providers."""
    for key in ("discord", "telegram", "mastodon", "bluesky", "solana", "nostr",
                "did", "keybase", "openclaw", "gitlab", "linkedin", "orcid"):
        assert key in SUPPORTED_PROVIDERS, f"New provider '{key}' missing"


def test_no_duplicates():
    assert len(SUPPORTED_PROVIDERS) == len(set(SUPPORTED_PROVIDERS))


def test_get_provider_info():
    info = get_provider_info("github")
    assert info is not None
    assert info.label == "GitHub"
    assert info.can_oauth is True

    info = get_provider_info("ethereum")
    assert info is not None
    assert info.can_verify is True

    assert get_provider_info("nonexistent") is None


def test_registry_as_dict():
    d = registry_as_dict()
    assert "Social" in d
    assert isinstance(d["Social"], list)
    assert d["Social"][0]["key"] == "github"
    assert d["Social"][0]["canOAuth"] is True


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def test_providers_endpoint(client):
    resp = client.get("/api/identity/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    cats = data["categories"]
    assert len(cats) == 6
    # Check github is in Social
    social_keys = [p["key"] for p in cats["Social"]]
    assert "github" in social_keys
    assert "discord" in social_keys


def test_link_new_provider(client):
    """Linking a newly-supported provider should succeed."""
    resp = client.post("/api/identity/link", json={
        "contributor_id": "test-user",
        "provider": "discord",
        "provider_id": "testuser#1234",
        "display_name": "Test User",
    })
    assert resp.status_code == 200
    assert resp.json()["provider"] == "discord"


def test_link_unsupported_provider(client):
    """Linking an unsupported provider should fail."""
    resp = client.post("/api/identity/link", json={
        "contributor_id": "test-user",
        "provider": "myspace",
        "provider_id": "tom",
    })
    assert resp.status_code == 422


def test_lookup_after_link(client):
    """After linking, reverse lookup should find the contributor."""
    client.post("/api/identity/link", json={
        "contributor_id": "lookup-test",
        "provider": "solana",
        "provider_id": "SoLaNaAdDrEsS123",
    })
    resp = client.get("/api/identity/lookup/solana/SoLaNaAdDrEsS123")
    assert resp.status_code == 200
    assert resp.json()["contributor_id"] == "lookup-test"


def test_contribution_with_provider_identity(client):
    """Recording a contribution with provider+provider_id instead of contributor_id."""
    resp = client.post("/api/contributions/record", json={
        "provider": "github",
        "provider_id": "alice-dev",
        "type": "code",
        "amount_cc": 5.0,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("contributor_id") is not None


def test_contribution_requires_identity(client):
    """A contribution with neither contributor_id nor provider should fail."""
    resp = client.post("/api/contributions/record", json={
        "type": "code",
        "amount_cc": 1.0,
    })
    assert resp.status_code == 422
