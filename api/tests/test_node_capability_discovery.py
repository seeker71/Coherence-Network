"""Tests for Spec 137: node capability discovery registration and aggregation."""

from __future__ import annotations

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


def _caps(executors: list[str] | None = None, tools: list[str] | None = None, cpu: int = 8, mem: float = 16.0):
    return {
        "executors": executors or ["claude", "openrouter"],
        "tools": tools or ["git", "python3", "gh"],
        "hardware": {
            "cpu_count": cpu,
            "memory_total_gb": mem,
            "gpu_available": False,
            "gpu_type": None,
        },
        "models_by_executor": {"openrouter": ["openrouter/free"]},
        "probed_at": "2026-03-21T15:00:00Z",
    }


def test_registration_includes_capabilities(client):
    """Node registration persists full capability manifest to list endpoint."""
    payload = {
        "node_id": "a1b2c3d4e5f60789",
        "hostname": "node-a",
        "os_type": "linux",
        "providers": ["claude", "openrouter"],
        "capabilities": _caps(),
    }
    reg = client.post("/api/federation/nodes", json=payload)
    assert reg.status_code == 201

    listed = client.get("/api/federation/nodes")
    assert listed.status_code == 200
    nodes = listed.json()
    assert len(nodes) == 1
    assert nodes[0]["capabilities"]["executors"] == ["claude", "openrouter"]
    assert nodes[0]["capabilities"]["tools"] == ["git", "python3", "gh"]


def test_get_node_metadata_populates_capabilities(monkeypatch):
    """Node metadata helper returns probe-derived providers/capabilities."""
    from app.models.federation import NodeCapabilities
    from app.services import node_identity_service as nis

    fake_caps = NodeCapabilities(
        executors=["claude", "openrouter"],
        tools=["git"],
        hardware={"cpu_count": 8, "memory_total_gb": 16.0, "gpu_available": False, "gpu_type": None},
        models_by_executor={"openrouter": ["openrouter/free"]},
        probed_at="2026-03-21T15:00:00Z",
    )
    monkeypatch.setattr(nis, "get_or_create_node_id", lambda: "a1b2c3d4e5f60789")
    monkeypatch.setattr(nis.socket, "gethostname", lambda: "node-local")
    monkeypatch.setattr(nis.platform, "system", lambda: "Linux")
    monkeypatch.setattr("app.services.node_identity_service.CapabilityProbe.probe", lambda: fake_caps)

    metadata = nis.get_node_metadata()
    assert metadata["providers"] == ["claude", "openrouter"]
    assert metadata["capabilities"]["tools"] == ["git"]


def test_heartbeat_refreshes_capabilities(client):
    """Heartbeat refresh query applies updated capability manifest."""
    payload = {
        "node_id": "a1b2c3d4e5f60789",
        "hostname": "node-a",
        "os_type": "linux",
        "providers": ["openrouter"],
        "capabilities": _caps(executors=["openrouter"]),
    }
    reg = client.post("/api/federation/nodes", json=payload)
    assert reg.status_code == 201

    hb = client.post(
        "/api/federation/nodes/a1b2c3d4e5f60789/heartbeat?refresh_capabilities=true",
        json={
            "status": "online",
            "capabilities": _caps(executors=["claude", "cursor", "openrouter"], tools=["git", "docker"]),
        },
    )
    assert hb.status_code == 200
    assert hb.json()["capabilities_refreshed"] is True

    listed = client.get("/api/federation/nodes")
    node = listed.json()[0]
    assert node["providers"] == ["claude", "cursor", "openrouter"]
    assert node["capabilities"]["tools"] == ["git", "docker"]


def test_fleet_capabilities_endpoint(client):
    """Fleet capability endpoint returns aggregated executor/tool/hardware coverage."""
    node_a = {
        "node_id": "a1b2c3d4e5f60789",
        "hostname": "node-a",
        "os_type": "linux",
        "providers": ["claude", "openrouter"],
        "capabilities": _caps(executors=["claude", "openrouter"], tools=["git", "python3"], cpu=8, mem=16.0),
    }
    node_b = {
        "node_id": "f9e8d7c6b5a40321",
        "hostname": "node-b",
        "os_type": "macos",
        "providers": ["openrouter"],
        "capabilities": _caps(executors=["openrouter"], tools=["git", "docker"], cpu=4, mem=8.0),
    }
    assert client.post("/api/federation/nodes", json=node_a).status_code == 201
    assert client.post("/api/federation/nodes", json=node_b).status_code == 201

    resp = client.get("/api/federation/nodes/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_nodes"] == 2
    assert body["executors"]["openrouter"]["node_count"] == 2
    assert body["executors"]["claude"]["node_count"] == 1
    assert body["tools"]["git"]["node_count"] == 2
    assert body["hardware_summary"]["total_cpus"] == 12
    assert body["hardware_summary"]["total_memory_gb"] == 24.0
