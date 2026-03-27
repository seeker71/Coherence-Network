"""Tests for multi-node federation: identity, registration, capability reporting.

Covers Spec 132 scenarios that require multiple simultaneous nodes:
- Stable identity derivation across process restarts
- Multi-node list completeness and correctness
- Provider and capability field persistence and retrieval
- Fleet capability aggregation
- Node deletion
- Heartbeat with git_sha and capability refresh
- get_node_metadata structure
- Input validation (node_id length constraints)
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory DB."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    from app.services import unified_db
    unified_db.reset_engine()


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def _node(
    node_id: str = "a1b2c3d4e5f60001",
    hostname: str = "node-alpha",
    os_type: str = "linux",
    providers: list | None = None,
    capabilities: dict | None = None,
) -> dict:
    return {
        "node_id": node_id,
        "hostname": hostname,
        "os_type": os_type,
        "providers": ["claude"] if providers is None else providers,
        "capabilities": capabilities if capabilities is not None else {},
    }


# ---------------------------------------------------------------------------
# Node identity derivation — get_node_metadata
# ---------------------------------------------------------------------------

def test_get_node_metadata_structure(tmp_path):
    """get_node_metadata returns all required keys with correct types."""
    from app.services import node_identity_service as nis
    from app.services.capability_probe import CapabilityProbe
    from app.models.federation import NodeCapabilities

    fake_caps = NodeCapabilities(
        executors=["claude"],
        tools=["git"],
        hardware={"cpu_count": 4, "memory_total_gb": 16.0},
        models_by_executor={"claude": ["claude-haiku-4-5-20251001"]},
    )
    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", tmp_path / "node_id"), \
         patch("socket.gethostname", return_value="test-host"), \
         patch.object(nis, "_get_mac_address", return_value="aabbccddeeff"), \
         patch.object(CapabilityProbe, "probe", return_value=fake_caps):

        meta = nis.get_node_metadata()

    assert "node_id" in meta
    assert "hostname" in meta
    assert "os_type" in meta
    assert "providers" in meta
    assert "capabilities" in meta
    assert isinstance(meta["node_id"], str) and len(meta["node_id"]) == 16
    assert meta["hostname"] == "test-host"
    assert meta["os_type"] in ("macos", "windows", "linux")
    assert isinstance(meta["providers"], list)
    assert isinstance(meta["capabilities"], dict)


def test_get_node_metadata_node_id_deterministic(tmp_path):
    """Two calls with same system state yield identical node_id."""
    from app.services import node_identity_service as nis
    from app.services.capability_probe import CapabilityProbe
    from app.models.federation import NodeCapabilities

    fake_caps = NodeCapabilities()
    id_file = tmp_path / "node_id"

    kwargs = dict(
        IDENTITY_DIR=tmp_path,
        IDENTITY_FILE=id_file,
    )
    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", id_file), \
         patch("socket.gethostname", return_value="stable-host"), \
         patch.object(nis, "_get_mac_address", return_value="112233445566"), \
         patch.object(CapabilityProbe, "probe", return_value=fake_caps):
        m1 = nis.get_node_metadata()

    id_file.unlink()

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", id_file), \
         patch("socket.gethostname", return_value="stable-host"), \
         patch.object(nis, "_get_mac_address", return_value="112233445566"), \
         patch.object(CapabilityProbe, "probe", return_value=fake_caps):
        m2 = nis.get_node_metadata()

    assert m1["node_id"] == m2["node_id"]
    expected = hashlib.sha256(b"stable-host112233445566").hexdigest()[:16]
    assert m1["node_id"] == expected


def test_get_node_metadata_different_hosts_different_ids(tmp_path):
    """Different hostname+mac combinations produce distinct node_ids."""
    from app.services import node_identity_service as nis
    from app.services.capability_probe import CapabilityProbe
    from app.models.federation import NodeCapabilities

    fake_caps = NodeCapabilities()
    id_file_a = tmp_path / "node_id_a"
    id_file_b = tmp_path / "node_id_b"

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", id_file_a), \
         patch("socket.gethostname", return_value="host-a"), \
         patch.object(nis, "_get_mac_address", return_value="aaaaaaaaaaaa"), \
         patch.object(CapabilityProbe, "probe", return_value=fake_caps):
        ma = nis.get_node_metadata()

    with patch.object(nis, "IDENTITY_DIR", tmp_path), \
         patch.object(nis, "IDENTITY_FILE", id_file_b), \
         patch("socket.gethostname", return_value="host-b"), \
         patch.object(nis, "_get_mac_address", return_value="bbbbbbbbbbbb"), \
         patch.object(CapabilityProbe, "probe", return_value=fake_caps):
        mb = nis.get_node_metadata()

    assert ma["node_id"] != mb["node_id"]


# ---------------------------------------------------------------------------
# Multi-node registration and listing
# ---------------------------------------------------------------------------

def test_register_multiple_nodes_all_appear_in_list(client):
    """Registering N nodes returns all N in GET /api/federation/nodes."""
    nodes = [
        _node("a1b2c3d4e5f60001", "alpha", "linux"),
        _node("b2c3d4e5f6070002", "beta", "macos"),
        _node("c3d4e5f608090003", "gamma", "windows"),
    ]
    for n in nodes:
        resp = client.post("/api/federation/nodes", json=n)
        assert resp.status_code == 201, f"Registration failed for {n['node_id']}: {resp.text}"

    list_resp = client.get("/api/federation/nodes")
    assert list_resp.status_code == 200
    listed = {n["node_id"]: n for n in list_resp.json()}

    for n in nodes:
        assert n["node_id"] in listed, f"{n['node_id']} missing from list"
        assert listed[n["node_id"]]["hostname"] == n["hostname"]
        assert listed[n["node_id"]]["os_type"] == n["os_type"]


def test_node_providers_persisted_and_returned(client):
    """Providers reported at registration are returned in the node list."""
    providers = ["claude", "openrouter", "cursor"]
    resp = client.post("/api/federation/nodes", json=_node(
        node_id="d4e5f60708090004",
        hostname="provider-node",
        providers=providers,
    ))
    assert resp.status_code == 201

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == "d4e5f60708090004")
    assert sorted(node["providers"]) == sorted(providers)


def test_node_capabilities_persisted_and_returned(client):
    """Capabilities dict reported at registration is stored and retrievable."""
    caps = {"docker": True, "gpu": False, "cpu_count": 8, "memory_total_gb": 32.0}
    resp = client.post("/api/federation/nodes", json=_node(
        node_id="e5f6070809010005",
        hostname="cap-node",
        capabilities=caps,
    ))
    assert resp.status_code == 201

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == "e5f6070809010005")
    for k, v in caps.items():
        assert node["capabilities"].get(k) == v, f"capability {k} mismatch"


def test_re_registration_does_not_duplicate(client):
    """Re-registering the same node_id updates it without creating a second entry."""
    node_id = "f607080910110006"
    client.post("/api/federation/nodes", json=_node(node_id, "first-hostname"))
    client.post("/api/federation/nodes", json=_node(node_id, "second-hostname"))

    list_resp = client.get("/api/federation/nodes")
    matching = [n for n in list_resp.json() if n["node_id"] == node_id]
    assert len(matching) == 1
    assert matching[0]["hostname"] == "second-hostname"


def test_re_registration_preserves_registered_at(client):
    """registered_at timestamp is frozen on first registration; re-reg does not change it."""
    node_id = "a2b3c4d5e6f70007"
    resp1 = client.post("/api/federation/nodes", json=_node(node_id, "host-v1"))
    assert resp1.status_code == 201
    original_ts = resp1.json()["registered_at"]

    resp2 = client.post("/api/federation/nodes", json=_node(node_id, "host-v2"))
    assert resp2.status_code == 200
    assert resp2.json()["registered_at"] == original_ts


# ---------------------------------------------------------------------------
# Node deletion
# ---------------------------------------------------------------------------

def test_delete_node_removes_it_from_list(client):
    """DELETE /api/federation/nodes/{node_id} removes the node."""
    node_id = "b3c4d5e6f7080008"
    client.post("/api/federation/nodes", json=_node(node_id))

    del_resp = client.delete(f"/api/federation/nodes/{node_id}")
    assert del_resp.status_code == 204

    list_resp = client.get("/api/federation/nodes")
    ids = [n["node_id"] for n in list_resp.json()]
    assert node_id not in ids


def test_delete_nonexistent_node_returns_404(client):
    """Deleting a node that was never registered returns 404."""
    resp = client.delete("/api/federation/nodes/0000000000000000")
    assert resp.status_code == 404


def test_delete_one_node_leaves_others_intact(client):
    """Deleting node A does not affect node B."""
    id_a = "c4d5e6f708090009"
    id_b = "d5e6f70809100010"
    client.post("/api/federation/nodes", json=_node(id_a, "node-a"))
    client.post("/api/federation/nodes", json=_node(id_b, "node-b"))

    client.delete(f"/api/federation/nodes/{id_a}")

    list_resp = client.get("/api/federation/nodes")
    ids = [n["node_id"] for n in list_resp.json()]
    assert id_a not in ids
    assert id_b in ids


# ---------------------------------------------------------------------------
# Heartbeat — git_sha and capability refresh
# ---------------------------------------------------------------------------

def test_heartbeat_stores_git_sha(client):
    """Heartbeat with git_sha stores it in capabilities and exposes it in list."""
    node_id = "e6f7080910110011"
    client.post("/api/federation/nodes", json=_node(node_id))

    hb_resp = client.post(
        f"/api/federation/nodes/{node_id}/heartbeat",
        json={"status": "online", "git_sha": "abc123def456"},
    )
    assert hb_resp.status_code == 200

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == node_id)
    assert node["git_sha"] == "abc123def456"


def test_heartbeat_with_capability_refresh_updates_providers(client):
    """refresh_capabilities=true replaces provider list from capabilities.executors."""
    node_id = "f708091011120012"
    client.post("/api/federation/nodes", json=_node(node_id, providers=["claude"]))

    hb_resp = client.post(
        f"/api/federation/nodes/{node_id}/heartbeat?refresh_capabilities=true",
        json={
            "status": "online",
            "capabilities": {
                "executors": ["claude", "openrouter"],
                "tools": ["git", "docker"],
                "hardware": {"cpu_count": 4},
            },
        },
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["capabilities_refreshed"] is True

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == node_id)
    assert "openrouter" in node["providers"]


def test_heartbeat_without_refresh_flag_does_not_overwrite_providers(client):
    """Without refresh_capabilities=true, providers remain unchanged after heartbeat."""
    node_id = "a809101112130013"
    client.post("/api/federation/nodes", json=_node(node_id, providers=["claude"]))

    client.post(
        f"/api/federation/nodes/{node_id}/heartbeat",
        json={
            "status": "online",
            "capabilities": {"executors": ["cursor"]},
        },
    )

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == node_id)
    # providers must still be the original ones
    assert "claude" in node["providers"]
    assert "cursor" not in node["providers"]


# ---------------------------------------------------------------------------
# Fleet capability summary
# ---------------------------------------------------------------------------

def test_fleet_capabilities_aggregates_across_nodes(client):
    """GET /api/federation/nodes/capabilities returns summary across all nodes."""
    nodes = [
        _node("b910111213140014", "alpha", capabilities={
            "executors": ["claude"],
            "tools": ["git", "docker"],
            "hardware": {"cpu_count": 4, "memory_total_gb": 8.0, "gpu_available": False},
        }),
        _node("c011121314150015", "beta", capabilities={
            "executors": ["claude", "openrouter"],
            "tools": ["git", "npm"],
            "hardware": {"cpu_count": 8, "memory_total_gb": 32.0, "gpu_available": True},
        }),
    ]
    for n in nodes:
        client.post("/api/federation/nodes", json=n)

    resp = client.get("/api/federation/nodes/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_nodes"] == 2


def test_fleet_capabilities_empty_when_no_nodes(client):
    """Fleet capability summary with no nodes returns total_nodes=0."""
    resp = client.get("/api/federation/nodes/capabilities")
    assert resp.status_code == 200
    assert resp.json()["total_nodes"] == 0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_register_node_rejects_short_node_id(client):
    """node_id shorter than 16 chars is rejected with 422."""
    payload = _node(node_id="tooshort")
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 422


def test_register_node_rejects_long_node_id(client):
    """node_id longer than 16 chars is rejected with 422."""
    payload = _node(node_id="a" * 17)
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 422


def test_register_node_accepts_exactly_16_char_id(client):
    """node_id of exactly 16 chars is accepted."""
    payload = _node(node_id="1234567890abcdef")
    resp = client.post("/api/federation/nodes", json=payload)
    assert resp.status_code == 201


def test_register_node_empty_providers_list(client):
    """Registering with an empty providers list is valid and stored correctly."""
    node_id = "d112131415160016"
    resp = client.post("/api/federation/nodes", json=_node(node_id, providers=[]))
    assert resp.status_code == 201

    list_resp = client.get("/api/federation/nodes")
    node = next(n for n in list_resp.json() if n["node_id"] == node_id)
    assert node["providers"] == []


# ---------------------------------------------------------------------------
# End-to-end: full register → heartbeat → list cycle for two nodes
# ---------------------------------------------------------------------------

def test_full_lifecycle_two_nodes(client):
    """
    Scenario: Two nodes register, heartbeat, and appear in the fleet list.

    Setup:   No nodes registered
    Action:  Register node-1 and node-2 → send heartbeats → list fleet
    Expected:
      - Both appear in list with correct hostname/os_type
      - Both show status=online
      - last_seen_at is not empty
      - Providers from registration are preserved
    Edge:    Heartbeat for non-existent node → 404
    """
    id1, id2 = "e213141516170017", "f314151617180018"

    # Register both nodes
    r1 = client.post("/api/federation/nodes", json=_node(id1, "node-one", "macos", ["claude"]))
    r2 = client.post("/api/federation/nodes", json=_node(id2, "node-two", "linux", ["openrouter"]))
    assert r1.status_code == 201
    assert r2.status_code == 201

    # Heartbeat both
    h1 = client.post(f"/api/federation/nodes/{id1}/heartbeat", json={"status": "online"})
    h2 = client.post(f"/api/federation/nodes/{id2}/heartbeat", json={"status": "online"})
    assert h1.status_code == 200
    assert h2.status_code == 200

    # List and verify
    fleet = {n["node_id"]: n for n in client.get("/api/federation/nodes").json()}
    assert id1 in fleet and id2 in fleet
    assert fleet[id1]["status"] == "online"
    assert fleet[id2]["status"] == "online"
    assert fleet[id1]["hostname"] == "node-one"
    assert fleet[id2]["hostname"] == "node-two"
    assert "claude" in fleet[id1]["providers"]
    assert "openrouter" in fleet[id2]["providers"]
    assert fleet[id1]["last_seen_at"]
    assert fleet[id2]["last_seen_at"]

    # Edge: heartbeat for unknown node
    miss = client.post("/api/federation/nodes/0000000000000000/heartbeat", json={"status": "online"})
    assert miss.status_code == 404
