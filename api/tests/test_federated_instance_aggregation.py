"""Tests for Spec 143: Federated Instance Aggregation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

AUTH_HEADERS = {"X-API-Key": "dev-key"}


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
# Helpers
# ---------------------------------------------------------------------------

NODE_ALPHA = "node_alpha_123456"  # 17 chars, will be sliced to 16
NODE_BETA = "node_beta_6789012"   # 17 chars, will be sliced to 16


def _register_node(client, node_id: str, trust_level: str = "verified"):
    """Register a federation node with a specific trust level."""
    # Note: Currently federation_service.register_or_update_node doesn't take trust_level.
    # We might need to manually update it in the DB or via an internal helper.
    resp = client.post("/api/federation/nodes", json={
        "node_id": node_id[:16],  # Ensure 16 chars
        "hostname": f"host-{node_id}",
        "os_type": "linux",
        "providers": ["openrouter/deepseek-v3"],
        "capabilities": {},
    })
    assert resp.status_code in (200, 201)
    
    # Manually set trust level for testing if needed
    from app.services import unified_db as _udb
    from app.services.federation_service import FederatedInstanceRecord
    with _udb.session() as s:
        # Check if FederatedInstanceRecord exists, if not create one
        inst = s.query(FederatedInstanceRecord).filter_by(instance_id=node_id[:16]).first()
        if not inst:
            inst = FederatedInstanceRecord(
                instance_id=node_id[:16],
                name=f"Node {node_id}",
                endpoint_url=f"http://{node_id}.local",
                registered_at=datetime.now(timezone.utc).isoformat(),
                trust_level=trust_level
            )
            s.add(inst)
        else:
            inst.trust_level = trust_level


def _aggregate_payload(
    node_id: str,
    strategy_type: str = "provider_recommendation",
    sample_count: int = 84,
    success_rate: float = 0.91,
) -> dict:
    return {
        "envelope": {
            "schema_version": "v1",
            "node_id": node_id[:16],
            "sent_at": "2026-03-22T16:30:00Z",
            "payload_hash": "sha256:3a4b...",
            "signature": "base64:MEUC..."
        },
        "payload": {
            "strategy_type": strategy_type,
            "window_start": "2026-03-22T15:30:00Z",
            "window_end": "2026-03-22T16:30:00Z",
            "sample_count": sample_count,
            "metrics": {
                "provider": "openrouter/deepseek-v3",
                "success_rate": success_rate,
                "avg_duration_s": 63.4
            }
        }
    }


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------

def test_accepts_verified_partner_payload_and_returns_202(client):
    """Hub accepts payloads from verified partners."""
    node_id = NODE_ALPHA[:16]
    _register_node(client, node_id, trust_level="verified")
    
    payload = _aggregate_payload(node_id)
    resp = client.post(f"/api/federation/instances/{node_id}/aggregate", json=payload)
    
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert "merge_key" in body
    assert body["trust_tier"] == "verified"


def test_rejects_unverified_partner_with_403(client):
    """Hub rejects payloads from unknown or low-trust nodes."""
    node_id = "unknown_node_id_"
    payload = _aggregate_payload(node_id)
    
    resp = client.post(f"/api/federation/instances/{node_id}/aggregate", json=payload)
    assert resp.status_code == 403


def test_rejects_malformed_payload_with_422(client):
    """Hub rejects payloads missing required fields."""
    node_id = NODE_ALPHA[:16]
    _register_node(client, node_id, trust_level="verified")
    
    payload = _aggregate_payload(node_id)
    del payload["payload"]["sample_count"]
    
    resp = client.post(f"/api/federation/instances/{node_id}/aggregate", json=payload)
    assert resp.status_code == 422


def test_duplicate_payload_is_idempotent_409(client):
    """Duplicate payloads are rejected with 409 to prevent double-counting."""
    node_id = NODE_ALPHA[:16]
    _register_node(client, node_id, trust_level="verified")
    
    payload = _aggregate_payload(node_id)
    
    # First submission
    resp1 = client.post(f"/api/federation/instances/{node_id}/aggregate", json=payload)
    assert resp1.status_code == 202
    
    # Duplicate submission
    resp2 = client.post(f"/api/federation/instances/{node_id}/aggregate", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["dedupe"] is True


def test_weighted_mean_merge_is_deterministic(client):
    """Multiple submissions are merged using weighted mean correctly."""
    node_a = NODE_ALPHA[:16]
    node_b = NODE_BETA[:16]
    _register_node(client, node_a, trust_level="verified")
    _register_node(client, node_b, trust_level="verified")
    
    # Node A: 100 samples, 0.9 success
    payload_a = _aggregate_payload(node_a, sample_count=100, success_rate=0.9)
    client.post(f"/api/federation/instances/{node_a}/aggregate", json=payload_a)
    
    # Node B: 200 samples, 0.6 success
    payload_b = _aggregate_payload(node_b, sample_count=200, success_rate=0.6)
    client.post(f"/api/federation/instances/{node_b}/aggregate", json=payload_b)
    
    # Trigger merge or check aggregated view (Implementation detail: how is merge triggered?)
    # For now, we assume an endpoint exists to view aggregated results
    resp = client.get("/api/federation/aggregates?strategy_type=provider_recommendation")
    assert resp.status_code == 200
    aggregates = resp.json()["aggregates"]
    
    # Weighted mean: (100*0.9 + 200*0.6) / 300 = (90 + 120) / 300 = 210 / 300 = 0.7
    found = False
    for agg in aggregates:
        if agg["metrics"]["provider"] == "openrouter/deepseek-v3":
            assert agg["metrics"]["success_rate"] == pytest.approx(0.7)
            assert agg["sample_count"] == 300
            assert node_a in agg["source_nodes"]
            assert node_b in agg["source_nodes"]
            found = True
    assert found


def test_majority_vote_tie_break_is_deterministic(client):
    """Majority vote handles ties deterministically."""
    # This might require a different strategy type or payload
    pass


def test_warning_union_merge_preserves_provenance(client):
    """Warning union preserves all unique warnings and their sources."""
    pass


def test_local_thompson_sampling_precedence_preserved(client):
    """Federated guidance does not hard-override local sampling."""
    # This would require checking the orchestrator/model routing logic
    pass
