"""Contract tests for non-interactive identity (R3, R6)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import config_service


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def test_resolve_cli_contributor_id_env_precedence(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"contributor_id": "from-config"}), encoding="utf-8")
    monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)

    monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
    monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)
    cid, src = config_service.resolve_cli_contributor_id()
    assert cid == "from-config"
    assert src == "config.json"

    monkeypatch.setenv("COHERENCE_CONTRIBUTOR", "legacy")
    cid, src = config_service.resolve_cli_contributor_id()
    assert cid == "legacy"
    assert "legacy" in src

    monkeypatch.setenv("COHERENCE_CONTRIBUTOR_ID", "canonical")
    cid, src = config_service.resolve_cli_contributor_id()
    assert cid == "canonical"
    assert "COHERENCE_CONTRIBUTOR_ID" in src


def test_identity_me_missing_key(client: TestClient) -> None:
    r = client.get("/api/identity/me")
    assert r.status_code == 401


def test_identity_me_invalid_key(client: TestClient) -> None:
    r = client.get("/api/identity/me", headers={"X-API-Key": "not-a-real-key-xxxxxxxx"})
    assert r.status_code == 401


def test_identity_me_ok(client: TestClient) -> None:
    # Register a personal API key via the same flow as the CLI
    link = client.post(
        "/api/identity/link",
        json={
            "contributor_id": "me-endpoint-user",
            "provider": "name",
            "provider_id": "me-endpoint-user",
            "display_name": "me-endpoint-user",
        },
    )
    assert link.status_code == 200
    keys = client.post(
        "/api/auth/keys",
        json={
            "contributor_id": "me-endpoint-user",
            "provider": "name",
            "provider_id": "me-endpoint-user",
        },
    )
    assert keys.status_code == 201, keys.text
    api_key = keys.json()["api_key"]

    r = client.get("/api/identity/me", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] == "me-endpoint-user"
    assert body["source"] == "api_key"
    assert body["linked_accounts"] >= 1
