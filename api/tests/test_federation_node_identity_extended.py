"""Extended tests for federation node identity spec 132.

Covers edge cases and deeper verification beyond the six core acceptance tests
in test_federation_node_identity.py.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    from app.services import unified_db
    unified_db.reset_engine()


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Node identity derivation — additional cases
# ---------------------------------------------------------------------------


def test_node_id_length_is_16_hex_chars(tmp_path):
    """Spec: node_id = sha256(hostname + mac).hexdigest()[:16]."""
    from app.services import node_identity_service as nis

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", tmp_path / "node_id"), \
         patch("socket.gethostname", return_value="host1"), \
         patch.object(nis, "_get_mac_address", return_value="112233445566"):
        nid = nis.get_or_create_node_id()

    assert len(nid) == 16
    assert all(c in "0123456789abcdef" for c in nid)


def test_different_hostname_produces_different_id(tmp_path):
    """Changing hostname changes derived identity."""
    from app.services import node_identity_service as nis

    ids = []
    for hostname in ("host-a", "host-b"):
        id_file = tmp_path / f"node_id_{hostname}"
        with patch.object(nis, "IDENTITY_DIR", tmp_path), \
             patch.object(nis, "IDENTITY_FILE", id_file), \
             patch("socket.gethostname", return_value=hostname), \
             patch.object(nis, "_get_mac_address", return_value="aabbccddeeff"):
            ids.append(nis.get_or_create_node_id())

    assert ids[0] != ids[1]


def test_different_mac_produces_different_id(tmp_path):
    """Changing MAC changes derived identity."""
    from app.services import node_identity_service as nis

    ids = []
    for mac in ("aabbccddeeff", "112233445566"):
        id_file = tmp_path / f"node_id_{mac}"
        with patch.object(nis, "IDENTITY_DIR", tmp_path), \
             patch.object(nis, "IDENTITY_FILE", id_file), \
             patch("socket.gethostname", return_value="same-host"), \
             patch.object(nis, "_get_mac_address", return_value=mac):
            ids.append(nis.get_or_create_node_id())

    assert ids[0] != ids[1]


def test_persisted_file_takes_precedence_over_derivation(tmp_path):
    """Spec: always prefer persisted node_id over re-derivation."""
    from app.services import node_identity_service as nis

    stored = "cafebabe12345678"
    id_file = tmp_path / "node_id"
    id_file.write_text(stored)

    with patch.object(nis, "IDENTITY_FILE", id_file), \
         patch("socket.gethostname", return_value="other-host"), \
         patch.object(nis, "_get_mac_address", return_value="000000000000"):
        result = nis.get_or_create_node_id()

    assert result == stored


def test_identity_file_is_created_on_first_derivation(tmp_path):
    """The identity file should be created when it doesn't exist."""
    from app.services import node_identity_service as nis

    id_file = tmp_path / "node_id"
    assert not id_file.exists()

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", id_file), \
         patch("socket.gethostname", return_value="new-host"), \
         patch.object(nis, "_get_mac_address", return_value="ffeeddccbbaa"):
        nid = nis.get_or_create_node_id()

    assert id_file.exists()
    assert id_file.read_text().strip() == nid


# ---------------------------------------------------------------------------
# Registration validation
# ---------------------------------------------------------------------------


def test_register_node_id_must_be_16_chars(client):
    """node_id must be exactly 16 chars per Pydantic model."""
    payload = {
        "node_id": "short",
        "hostname": "test",
        "os_type": "linux",
        "providers": [],
        "capabilities": {},
    }
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 422


def test_register_response_has_correct_fields(client):
    """Response must include node_id, status, registered_at, last_seen_at."""
    payload = {
        "node_id": "a1b2c3d4e5f60789",
        "hostname": "test-node",
        "os_type": "linux",
        "providers": ["openrouter"],
        "capabilities": {"python": True},
    }
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) >= {"node_id", "status", "registered_at", "last_seen_at"}


def test_register_preserves_providers_and_capabilities(client):
    """Providers and capabilities should be stored and retrievable."""
    payload = {
        "node_id": "abcdef0123456789",
        "hostname": "cap-node",
        "os_type": "macos",
        "providers": ["openai", "openrouter"],
        "capabilities": {"docker": True, "max_parallel_tasks": 4},
    }
    client.post("/api/federation/nodes", json=payload)

    list_resp = client.get("/api/federation/nodes")
    nodes = list_resp.json()
    node = next(n for n in nodes if n["node_id"] == "abcdef0123456789")
    assert "openai" in node.get("providers_json", node.get("providers", []))
    assert "openrouter" in node.get("providers_json", node.get("providers", []))


def test_register_upsert_preserves_registered_at(client):
    """Spec: first registration sets registered_at; repeat updates mutable fields."""
    payload = {
        "node_id": "1111222233334444",
        "hostname": "first-name",
        "os_type": "linux",
        "providers": [],
        "capabilities": {},
    }
    r1 = client.post("/api/federation/nodes", json=payload)
    assert r1.status_code == 201
    original_registered = r1.json()["registered_at"]

    payload["hostname"] = "second-name"
    payload["os_type"] = "vps"
    r2 = client.post("/api/federation/nodes", json=payload)
    assert r2.status_code == 200
    assert r2.json()["registered_at"] == original_registered


def test_register_multiple_distinct_nodes(client):
    """Multiple nodes can register independently."""
    node_ids = ["aaaa000000000001", "aaaa000000000002", "aaaa000000000003"]
    for i, nid in enumerate(node_ids):
        payload = {
            "node_id": nid,
            "hostname": f"host-{i}",
            "os_type": "linux",
            "providers": [],
            "capabilities": {},
        }
        resp = client.post("/api/federation/nodes", json=payload)
        assert resp.status_code == 201

    nodes = client.get("/api/federation/nodes").json()
    registered_ids = {n["node_id"] for n in nodes}
    assert all(nid in registered_ids for nid in node_ids)


# ---------------------------------------------------------------------------
# Heartbeat edge cases
# ---------------------------------------------------------------------------


def test_heartbeat_returns_correct_fields(client):
    """Heartbeat response includes node_id, status, last_seen_at."""
    payload = {
        "node_id": "hb00000000000001",
        "hostname": "hb-node",
        "os_type": "linux",
        "providers": [],
        "capabilities": {},
    }
    client.post("/api/federation/nodes", json=payload)

    hb_resp = client.post(
        "/api/federation/nodes/hb00000000000001/heartbeat",
        json={"status": "online"},
    )
    assert hb_resp.status_code == 200
    body = hb_resp.json()
    assert body["node_id"] == "hb00000000000001"
    assert body["status"] == "online"
    assert "last_seen_at" in body


def test_heartbeat_default_status_is_online(client):
    """Spec: heartbeat status defaults to 'online'."""
    payload = {
        "node_id": "hb00000000000002",
        "hostname": "hb-node-2",
        "os_type": "linux",
        "providers": [],
        "capabilities": {},
    }
    client.post("/api/federation/nodes", json=payload)

    hb_resp = client.post(
        "/api/federation/nodes/hb00000000000002/heartbeat",
        json={},
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "online"


def test_heartbeat_refreshes_status_to_online(client):
    """Heartbeat can refresh status back to online."""
    payload = {
        "node_id": "hb00000000000003",
        "hostname": "hb-node-3",
        "os_type": "linux",
        "providers": [],
        "capabilities": {},
    }
    client.post("/api/federation/nodes", json=payload)

    hb_resp = client.post(
        "/api/federation/nodes/hb00000000000003/heartbeat",
        json={"status": "online"},
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "online"


def test_heartbeat_unknown_node_returns_detail_message(client):
    """Spec: 404 response body is {"detail": "Node not found"}."""
    resp = client.post(
        "/api/federation/nodes/doesnotexist0000/heartbeat",
        json={"status": "online"},
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Node not found"}


def test_registration_response_is_deterministic_json(client):
    """Spec: endpoints return deterministic JSON suitable for automation."""
    payload = {
        "node_id": "det0000000000001",
        "hostname": "det-node",
        "os_type": "macos",
        "providers": ["openai"],
        "capabilities": {"docker": False},
    }
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert isinstance(body["node_id"], str)
    assert isinstance(body["status"], str)
    assert isinstance(body["registered_at"], str)
    assert isinstance(body["last_seen_at"], str)
