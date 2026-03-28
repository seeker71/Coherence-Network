"""Acceptance tests for Bot Discord (idea: bot-discord).

Spec (in-repo contract): Discord is a first-class Social identity provider. Users and
automations (including a future Discord bot) attribute work via the same identity APIs as
other providers — registry metadata, link, list, lookup, unlink.

There is no `/api/agent/discord/*` webhook in this tree yet; these tests lock the
identity-layer acceptance criteria that any Discord bot integration must respect.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.identity_providers import get_provider_info


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_discord_provider_registry_metadata() -> None:
    """Discord appears in Social with human label and placeholder guidance."""
    info = get_provider_info("discord")
    assert info is not None
    assert info.key == "discord"
    assert info.label == "Discord"
    assert "username" in info.placeholder.lower() or "user id" in info.placeholder.lower()
    assert info.category == "Social"
    assert info.can_oauth is False


def test_discord_listed_in_providers_api(client: TestClient) -> None:
    """GET /api/identity/providers exposes Discord with stable JSON shape."""
    resp = client.get("/api/identity/providers")
    assert resp.status_code == 200
    social = resp.json()["categories"]["Social"]
    discord_rows = [p for p in social if p.get("key") == "discord"]
    assert len(discord_rows) == 1
    row = discord_rows[0]
    assert row["label"] == "Discord"
    assert row["category"] == "Social"
    assert "placeholder" in row
    assert row.get("canOAuth") is False
    assert row.get("canVerify") is False


def test_discord_link_and_list_identities(client: TestClient) -> None:
    """Link Discord identity; GET /api/identity/{id} returns the link."""
    cid = "bot-discord-tester"
    link = client.post(
        "/api/identity/link",
        json={
            "contributor_id": cid,
            "provider": "discord",
            "provider_id": "user#9999",
            "display_name": "Discord Tester",
        },
    )
    assert link.status_code == 200
    assert link.json()["provider"] == "discord"

    got = client.get(f"/api/identity/{cid}")
    assert got.status_code == 200
    identities = got.json()
    assert any(
        i.get("provider") == "discord" and i.get("provider_id") == "user#9999" for i in identities
    )


def test_discord_lookup_round_trip(client: TestClient) -> None:
    """Reverse lookup resolves Discord provider_id to contributor."""
    cid = "discord-lookup-user"
    client.post(
        "/api/identity/link",
        json={
            "contributor_id": cid,
            "provider": "discord",
            "provider_id": "snowflake-12345",
        },
    )
    lu = client.get("/api/identity/lookup/discord/snowflake-12345")
    assert lu.status_code == 200
    assert lu.json()["contributor_id"] == cid


def test_discord_unlink(client: TestClient) -> None:
    """Unlink removes Discord from contributor profile."""
    cid = "discord-unlink-user"
    client.post(
        "/api/identity/link",
        json={
            "contributor_id": cid,
            "provider": "discord",
            "provider_id": "to-remove",
        },
    )
    rem = client.delete(f"/api/identity/{cid}/discord")
    assert rem.status_code == 200
    assert rem.json()["status"] == "unlinked"

    lu = client.get("/api/identity/lookup/discord/to-remove")
    assert lu.status_code == 404
