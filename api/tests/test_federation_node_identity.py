"""Tests for federation node identity, registration, and heartbeat (Spec 132)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_stores(tmp_path, monkeypatch):
    """Isolate DB stores for each test via unified_db."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    from app.services import unified_db
    unified_db.reset_engine()


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Node identity derivation
# ---------------------------------------------------------------------------

def test_node_id_is_stable_for_same_host_and_mac(tmp_path):
    """Same hostname + mac always produces the same node_id."""
    from app.services import node_identity_service as nis

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", tmp_path / "node_id"), \
         patch("socket.gethostname", return_value="test-host"), \
         patch.object(nis, "_get_mac_address", return_value="aabbccddeeff"):
        id1 = nis.get_or_create_node_id()

    # Remove file and regenerate — should be identical
    (tmp_path / "node_id").unlink()

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", tmp_path / "node_id"), \
         patch("socket.gethostname", return_value="test-host"), \
         patch.object(nis, "_get_mac_address", return_value="aabbccddeeff"):
        id2 = nis.get_or_create_node_id()

    assert id1 == id2
    expected = hashlib.sha256(b"test-hostaabbccddeeff").hexdigest()[:16]
    assert id1 == expected


def test_node_id_persisted_and_reused(tmp_path):
    """Once persisted, node_id is read from file without re-derivation."""
    from app.services import node_identity_service as nis

    fake_id = "abcdef0123456789"
    id_file = tmp_path / "node_id"
    id_file.write_text(fake_id)

    with patch.object(nis, "IDENTITY_FILE", id_file):
        result = nis.get_or_create_node_id()

    assert result == fake_id


# ---------------------------------------------------------------------------
# Node registration endpoints
# ---------------------------------------------------------------------------

def _make_node_payload(node_id="a1b2c3d4e5f60789", hostname="test-node"):
    return {
        "node_id": node_id,
        "hostname": hostname,
        "os_type": "macos",
        "providers": ["openai"],
        "capabilities": {"docker": True},
    }


def test_register_node_creates_new_record(client):
    payload = _make_node_payload()
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["node_id"] == "a1b2c3d4e5f60789"
    assert body["status"] == "online"
    assert "registered_at" in body
    assert "last_seen_at" in body


def test_register_node_updates_existing_record(client):
    payload = _make_node_payload()
    resp1 = client.post("/api/federation/nodes", json=payload)
    assert resp1.status_code == 201
    registered_at = resp1.json()["registered_at"]

    # Re-register with updated hostname
    payload["hostname"] = "updated-node"
    resp2 = client.post("/api/federation/nodes", json=payload)
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["node_id"] == "a1b2c3d4e5f60789"
    assert body2["registered_at"] == registered_at  # preserved
    assert body2["status"] == "online"

    # Verify the hostname was updated via list
    list_resp = client.get("/api/federation/nodes")
    nodes = list_resp.json()
    assert len(nodes) == 1
    assert nodes[0]["hostname"] == "updated-node"


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def test_heartbeat_updates_last_seen(client):
    from app.services import federation_service

    register_ts = datetime(2026, 3, 21, 15, 0, 0, tzinfo=timezone.utc)
    heartbeat_ts = datetime(2026, 3, 21, 15, 5, 0, tzinfo=timezone.utc)

    class _ControlledDatetime(datetime):
        _now_values = iter([register_ts, heartbeat_ts])

        @classmethod
        def now(cls, tz=None):
            return next(cls._now_values)

    payload = _make_node_payload()
    with patch.object(federation_service, "datetime", _ControlledDatetime):
        reg_resp = client.post("/api/federation/nodes", json=payload)
        assert reg_resp.status_code == 201
        original_last_seen = reg_resp.json()["last_seen_at"]

        hb_resp = client.post(
            "/api/federation/nodes/a1b2c3d4e5f60789/heartbeat",
            json={"status": "online"},
        )

    assert hb_resp.status_code == 200
    body = hb_resp.json()
    assert body["node_id"] == "a1b2c3d4e5f60789"
    assert body["status"] == "online"
    assert body["last_seen_at"] != original_last_seen

    original_last_seen_dt = datetime.fromisoformat(original_last_seen.replace("Z", "+00:00"))
    updated_last_seen_dt = datetime.fromisoformat(body["last_seen_at"].replace("Z", "+00:00"))
    assert updated_last_seen_dt > original_last_seen_dt


def test_heartbeat_unknown_node_404(client):
    resp = client.post(
        "/api/federation/nodes/0000000000000000/heartbeat",
        json={"status": "online"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Node not found"
