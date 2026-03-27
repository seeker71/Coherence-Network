"""Tests for CLI Noninteractive Identity (Spec 148).

Verifies the API contracts used by the CLI's non-interactive identity flow:
- Link identity without authentication (open registration)
- Auto-detected identity registration (env var, git, hostname sources)
- Identity lookup by provider
- Identity retrieval for a contributor
- Identity unlinking
- The `cc identity set` non-interactive command pattern
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Non-interactive identity registration (mirrors ensureIdentity() in CLI)
# ---------------------------------------------------------------------------


class TestNonInteractiveIdentityRegistration:
    """The CLI's non-interactive path registers identity via POST /api/identity/link
    with provider='name' and the auto-detected contributor_id."""

    def test_link_name_identity(self, client):
        """Non-interactive flow first links a 'name' provider identity."""
        resp = client.post("/api/identity/link", json={
            "contributor_id": "auto-agent-001",
            "provider": "name",
            "provider_id": "auto-agent-001",
            "display_name": "auto-agent-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["contributor_id"] == "auto-agent-001"
        assert data["provider"] == "name"

    def test_link_email_identity_after_name(self, client):
        """Non-interactive flow also links git email if available."""
        # First link name (primary)
        client.post("/api/identity/link", json={
            "contributor_id": "ci-bot",
            "provider": "name",
            "provider_id": "ci-bot",
            "display_name": "ci-bot",
        })
        # Then link email (secondary, from git config)
        resp = client.post("/api/identity/link", json={
            "contributor_id": "ci-bot",
            "provider": "email",
            "provider_id": "ci-bot@example.com",
            "display_name": "ci-bot",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "email"
        assert data["provider_id"] == "ci-bot@example.com"

    def test_retrieve_linked_identities(self, client):
        """After non-interactive registration, GET returns all linked identities."""
        # Register name + email
        client.post("/api/identity/link", json={
            "contributor_id": "test-contributor",
            "provider": "name",
            "provider_id": "test-contributor",
            "display_name": "test-contributor",
        })
        client.post("/api/identity/link", json={
            "contributor_id": "test-contributor",
            "provider": "email",
            "provider_id": "test@example.com",
            "display_name": "test-contributor",
        })

        resp = client.get("/api/identity/test-contributor")
        assert resp.status_code == 200
        identities = resp.json()
        assert isinstance(identities, list)
        providers = {i["provider"] for i in identities}
        assert "name" in providers
        assert "email" in providers

    def test_empty_identities_for_unknown_contributor(self, client):
        """GET for a non-existent contributor returns empty list, not 404."""
        resp = client.get("/api/identity/nonexistent-user-xyz")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# cc identity set <id> — direct identity setting for agents/scripts
# ---------------------------------------------------------------------------


class TestIdentitySetCommand:
    """The `cc identity set <id>` command writes to local config and does NOT
    call the API. These tests verify that when an agent subsequently uses the
    API with its set identity, the API accepts it correctly."""

    def test_link_after_set_identity(self, client):
        """After `cc identity set`, the CLI can link providers for the set ID."""
        contributor_id = "my-scripted-agent"
        resp = client.post("/api/identity/link", json={
            "contributor_id": contributor_id,
            "provider": "github",
            "provider_id": "scripted-agent-gh",
            "display_name": "scripted-agent-gh",
        })
        assert resp.status_code == 200
        assert resp.json()["contributor_id"] == contributor_id

    def test_set_identity_with_hyphens_and_dots(self, client):
        """Identity IDs with hyphens and dots work correctly."""
        contributor_id = "agent-worker.01"
        client.post("/api/identity/link", json={
            "contributor_id": contributor_id,
            "provider": "name",
            "provider_id": contributor_id,
            "display_name": contributor_id,
        })
        resp = client.get(f"/api/identity/{contributor_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Identity lookup by provider (used by cc identity lookup)
# ---------------------------------------------------------------------------


class TestIdentityLookup:
    """Verify the lookup endpoint used by `cc identity lookup <provider> <id>`."""

    def test_lookup_existing_identity(self, client):
        """Lookup returns the contributor_id for a known provider:id pair."""
        client.post("/api/identity/link", json={
            "contributor_id": "alice",
            "provider": "github",
            "provider_id": "alice-gh",
            "display_name": "Alice",
        })
        resp = client.get("/api/identity/lookup/github/alice-gh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contributor_id"] == "alice"
        assert data["provider"] == "github"
        assert data["provider_id"] == "alice-gh"

    def test_lookup_nonexistent_identity(self, client):
        """Lookup returns 404 for an unknown provider:id pair."""
        resp = client.get("/api/identity/lookup/github/nobody-here-12345")
        assert resp.status_code == 404

    def test_lookup_email_identity(self, client):
        """Lookup works for email provider (used in non-interactive git flow)."""
        client.post("/api/identity/link", json={
            "contributor_id": "bob",
            "provider": "email",
            "provider_id": "bob@example.com",
            "display_name": "Bob",
        })
        resp = client.get("/api/identity/lookup/email/bob@example.com")
        assert resp.status_code == 200
        assert resp.json()["contributor_id"] == "bob"


# ---------------------------------------------------------------------------
# Identity unlinking (cc identity unlink <provider>)
# ---------------------------------------------------------------------------


class TestIdentityUnlink:
    """Verify the unlink endpoint used by `cc identity unlink <provider>`."""

    def test_unlink_existing_identity(self, client):
        """Unlinking a linked provider returns success."""
        client.post("/api/identity/link", json={
            "contributor_id": "charlie",
            "provider": "discord",
            "provider_id": "charlie#1234",
            "display_name": "Charlie",
        })
        resp = client.delete("/api/identity/charlie/discord")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unlinked"
        assert data["provider"] == "discord"

    def test_unlink_nonexistent_identity(self, client):
        """Unlinking a non-linked provider returns 404."""
        resp = client.delete("/api/identity/nobody/github")
        assert resp.status_code == 404

    def test_unlinked_identity_no_longer_lookupable(self, client):
        """After unlinking, lookup should return 404."""
        client.post("/api/identity/link", json={
            "contributor_id": "dave",
            "provider": "telegram",
            "provider_id": "dave_tg",
            "display_name": "Dave",
        })
        # Verify it's linkable first
        resp = client.get("/api/identity/lookup/telegram/dave_tg")
        assert resp.status_code == 200

        # Unlink
        client.delete("/api/identity/dave/telegram")

        # Now lookup should fail
        resp = client.get("/api/identity/lookup/telegram/dave_tg")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unsupported provider validation
# ---------------------------------------------------------------------------


class TestProviderValidation:
    """The API rejects unsupported providers with 422."""

    def test_unsupported_provider_rejected(self, client):
        """Linking with an unknown provider returns 422."""
        resp = client.post("/api/identity/link", json={
            "contributor_id": "test-user",
            "provider": "totally_fake_provider",
            "provider_id": "handle",
            "display_name": "handle",
        })
        assert resp.status_code == 422

    def test_supported_providers_accepted(self, client):
        """Core providers used by CLI non-interactive flow are accepted."""
        for provider, pid in [("name", "agent"), ("email", "a@b.com"), ("github", "gh-user")]:
            resp = client.post("/api/identity/link", json={
                "contributor_id": f"test-{provider}",
                "provider": provider,
                "provider_id": pid,
                "display_name": pid,
            })
            assert resp.status_code == 200, f"Provider '{provider}' should be accepted"


# ---------------------------------------------------------------------------
# Identity overwrite / idempotency
# ---------------------------------------------------------------------------


class TestIdentityIdempotency:
    """Non-interactive flow may re-register on every invocation. Verify idempotency."""

    def test_relink_same_identity_is_idempotent(self, client):
        """Linking the same provider:id twice does not error."""
        payload = {
            "contributor_id": "repeat-agent",
            "provider": "name",
            "provider_id": "repeat-agent",
            "display_name": "repeat-agent",
        }
        resp1 = client.post("/api/identity/link", json=payload)
        assert resp1.status_code == 200

        resp2 = client.post("/api/identity/link", json=payload)
        assert resp2.status_code == 200

    def test_relink_updates_display_name(self, client):
        """Re-linking with a new display_name updates the record."""
        client.post("/api/identity/link", json={
            "contributor_id": "evolving-agent",
            "provider": "name",
            "provider_id": "evolving-agent",
            "display_name": "Old Name",
        })
        client.post("/api/identity/link", json={
            "contributor_id": "evolving-agent",
            "provider": "name",
            "provider_id": "evolving-agent",
            "display_name": "New Name",
        })
        resp = client.get("/api/identity/evolving-agent")
        assert resp.status_code == 200
        identities = resp.json()
        name_ids = [i for i in identities if i["provider"] == "name"]
        assert len(name_ids) >= 1
        assert name_ids[0]["display_name"] == "New Name"


# ---------------------------------------------------------------------------
# Providers list endpoint (used by cc identity link help)
# ---------------------------------------------------------------------------


class TestProvidersEndpoint:
    """The /api/identity/providers endpoint lists available providers."""

    def test_providers_returns_categories(self, client):
        resp = client.get("/api/identity/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        # Should have multiple categories
        assert len(data["categories"]) > 0

    def test_core_providers_in_list(self, client):
        """The providers used by non-interactive CLI flow must be present."""
        resp = client.get("/api/identity/providers")
        data = resp.json()
        # Flatten all provider keys
        all_keys = []
        for cat_providers in data["categories"].values():
            for p in cat_providers:
                all_keys.append(p["key"])
        for required in ("name", "email", "github"):
            assert required in all_keys, f"Provider '{required}' must be available"
