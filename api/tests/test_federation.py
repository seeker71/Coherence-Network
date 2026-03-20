"""Tests for the minimum federation layer."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.fixture(autouse=True)
def _isolate_stores(tmp_path, monkeypatch):
    """Isolate DB stores for each test via unified_db."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    # Reset the unified_db engine so it picks up the new path
    from app.services import unified_db
    unified_db.reset_engine()


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def _register_instance(client, instance_id="remote-1"):
    return client.post("/api/federation/instances", json={
        "instance_id": instance_id,
        "name": f"Remote Instance {instance_id}",
        "endpoint_url": f"https://{instance_id}.example.com",
    }, headers=AUTH_HEADERS)


# ---- Instance CRUD ----

def test_register_instance_and_list(client):
    resp = _register_instance(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["instance_id"] == "remote-1"
    assert body["trust_level"] == 0.5

    resp2 = client.get("/api/federation/instances")
    assert resp2.status_code == 200
    instances = resp2.json()
    assert len(instances) == 1
    assert instances[0]["instance_id"] == "remote-1"


def test_get_instance(client):
    _register_instance(client)
    resp = client.get("/api/federation/instances/remote-1")
    assert resp.status_code == 200
    assert resp.json()["instance_id"] == "remote-1"


def test_get_instance_not_found(client):
    resp = client.get("/api/federation/instances/nonexistent")
    assert resp.status_code == 404


# ---- Payload with lineage link -> governance ChangeRequest ----

def test_payload_lineage_link_creates_governance_request(client):
    _register_instance(client)
    payload = {
        "source_instance_id": "remote-1",
        "timestamp": "2026-03-20T00:00:00Z",
        "lineage_links": [
            {
                "idea_id": "fed-idea-1",
                "spec_id": "fed-spec-1",
                "implementation_refs": [],
                "contributors": {"idea": "remote-alice"},
                "investments": [],
                "estimated_cost": 5.0,
            }
        ],
    }
    resp = client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    result = resp.json()
    assert result["links_received"] == 1
    assert result["governance_requests_created"] == 1
    assert result["errors"] == []

    # Verify governance request exists
    gov_resp = client.get("/api/governance/change-requests")
    assert gov_resp.status_code == 200
    requests = gov_resp.json()
    federation_requests = [r for r in requests if r["request_type"] == "federation_import"]
    assert len(federation_requests) >= 1
    assert federation_requests[0]["payload"]["federation_type"] == "lineage_link"


# ---- Payload with usage event -> governance ChangeRequest ----

def test_payload_usage_event_creates_governance_request(client):
    _register_instance(client)
    payload = {
        "source_instance_id": "remote-1",
        "timestamp": "2026-03-20T00:00:00Z",
        "usage_events": [
            {
                "lineage_id": "lnk_abc123",
                "source": "remote-api",
                "metric": "page_views",
                "value": 42.0,
            }
        ],
    }
    resp = client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    result = resp.json()
    assert result["events_received"] == 1
    assert result["governance_requests_created"] == 1

    gov_resp = client.get("/api/governance/change-requests")
    requests = gov_resp.json()
    federation_requests = [r for r in requests if r["request_type"] == "federation_import"]
    assert len(federation_requests) >= 1
    assert federation_requests[0]["payload"]["federation_type"] == "usage_event"


# ---- Unregistered instance -> error ----

def test_unregistered_instance_rejected(client):
    payload = {
        "source_instance_id": "unknown-instance",
        "timestamp": "2026-03-20T00:00:00Z",
        "lineage_links": [{"idea_id": "x", "spec_id": "y", "contributors": {}, "investments": [], "estimated_cost": 1.0}],
    }
    resp = client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["errors"]) > 0
    assert "not registered" in result["errors"][0]
    assert result["rejected"] == 1


# ---- Empty payload -> no errors ----

def test_empty_payload_no_errors(client):
    _register_instance(client)
    payload = {
        "source_instance_id": "remote-1",
        "timestamp": "2026-03-20T00:00:00Z",
    }
    resp = client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    result = resp.json()
    assert result["links_received"] == 0
    assert result["events_received"] == 0
    assert result["governance_requests_created"] == 0
    assert result["errors"] == []


# ---- Approve governance requests -> data integrates ----

def test_approve_federation_link_integrates(client):
    _register_instance(client)
    # Send a lineage link via federation
    payload = {
        "source_instance_id": "remote-1",
        "timestamp": "2026-03-20T00:00:00Z",
        "lineage_links": [
            {
                "idea_id": "fed-idea-2",
                "spec_id": "fed-spec-2",
                "implementation_refs": [],
                "contributors": {"idea": "remote-bob"},
                "investments": [],
                "estimated_cost": 10.0,
            }
        ],
    }
    client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)

    # Find the governance request
    gov_resp = client.get("/api/governance/change-requests")
    requests = gov_resp.json()
    fed_request = [r for r in requests if r["request_type"] == "federation_import"][0]

    # Approve it (federation imports require 2 approvals)
    vote_resp = client.post(
        f"/api/governance/change-requests/{fed_request['id']}/votes",
        json={"voter_id": "admin", "decision": "yes"},
        headers=AUTH_HEADERS,
    )
    assert vote_resp.status_code == 200
    vote_resp2 = client.post(
        f"/api/governance/change-requests/{fed_request['id']}/votes",
        json={"voter_id": "admin2", "decision": "yes"},
        headers=AUTH_HEADERS,
    )
    assert vote_resp2.status_code == 200
    updated = vote_resp2.json()
    assert updated["status"] in ("approved", "applied")

    # Verify the lineage link was created
    links_resp = client.get("/api/value-lineage/links")
    assert links_resp.status_code == 200
    links = links_resp.json()["links"]
    fed_links = [l for l in links if l["idea_id"] == "fed-idea-2"]
    assert len(fed_links) == 1


# ---- Local valuation re-computation ----

def test_compute_local_valuation(client):
    from app.services.federation_service import compute_local_valuation

    links = [{"estimated_cost": 10.0}, {"estimated_cost": 5.0}]
    events = [{"value": 20.0}, {"value": 30.0}]
    result = compute_local_valuation(links, events)
    assert result["measured_value_total"] == 50.0
    assert result["estimated_cost"] == 15.0
    assert result["roi_ratio"] == round(50.0 / 15.0, 4)
    assert result["link_count"] == 2
    assert result["event_count"] == 2


# ---- Sync history ----

def test_sync_history_records_operation(client):
    _register_instance(client)
    payload = {
        "source_instance_id": "remote-1",
        "timestamp": "2026-03-20T00:00:00Z",
        "lineage_links": [
            {
                "idea_id": "fed-idea-3",
                "spec_id": "fed-spec-3",
                "implementation_refs": [],
                "contributors": {},
                "investments": [],
                "estimated_cost": 1.0,
            }
        ],
    }
    client.post("/api/federation/sync", json=payload, headers=AUTH_HEADERS)

    resp = client.get("/api/federation/sync/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1
    assert history[0]["source_instance_id"] == "remote-1"
    assert history[0]["links_received"] == 1


# ---- Full round-trip ----

def test_full_round_trip(client):
    # 1. Register
    _register_instance(client, "rt-instance")

    # 2. Send payload with a lineage link
    sync_resp = client.post("/api/federation/sync", json={
        "source_instance_id": "rt-instance",
        "timestamp": "2026-03-20T12:00:00Z",
        "lineage_links": [
            {
                "idea_id": "rt-idea",
                "spec_id": "rt-spec",
                "implementation_refs": ["rt-impl"],
                "contributors": {"idea": "rt-alice", "implementation": "rt-bob"},
                "investments": [],
                "estimated_cost": 8.0,
            }
        ],
    }, headers=AUTH_HEADERS)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["governance_requests_created"] == 1

    # 3. Approve (federation imports require 2 approvals)
    gov_resp = client.get("/api/governance/change-requests")
    fed_reqs = [r for r in gov_resp.json() if r["request_type"] == "federation_import"]
    assert len(fed_reqs) >= 1

    vote_resp = client.post(
        f"/api/governance/change-requests/{fed_reqs[0]['id']}/votes",
        json={"voter_id": "admin", "decision": "yes"},
        headers=AUTH_HEADERS,
    )
    assert vote_resp.status_code == 200
    vote_resp2 = client.post(
        f"/api/governance/change-requests/{fed_reqs[0]['id']}/votes",
        json={"voter_id": "admin2", "decision": "yes"},
        headers=AUTH_HEADERS,
    )
    assert vote_resp2.status_code == 200

    # 4. Verify integrated
    links_resp = client.get("/api/value-lineage/links")
    links = links_resp.json()["links"]
    rt_links = [l for l in links if l["idea_id"] == "rt-idea"]
    assert len(rt_links) == 1
    assert rt_links[0]["estimated_cost"] == 8.0

    # 5. Verify sync history
    history_resp = client.get("/api/federation/sync/history")
    history = history_resp.json()
    assert any(h["source_instance_id"] == "rt-instance" for h in history)
