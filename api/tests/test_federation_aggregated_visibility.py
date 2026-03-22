"""Tests for Spec 133: Federation Aggregated Visibility."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

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

NODE_A = "a3f8c2e1a3f8c2e1"  # 16-char node IDs
NODE_B = "b7d9e4f2b7d9e4f2"


def _register_node(client, node_id: str, hostname: str = "host", os_type: str = "linux"):
    """Register a federation node."""
    resp = client.post("/api/federation/nodes", json={
        "node_id": node_id,
        "hostname": hostname,
        "os_type": os_type,
        "providers": ["claude"],
        "capabilities": {},
    })
    assert resp.status_code in (200, 201), f"Node registration failed: {resp.text}"


def _push_summaries(client, node_id: str, summaries: list[dict]):
    """Push measurement summaries for a node."""
    resp = client.post(
        f"/api/federation/nodes/{node_id}/measurements",
        json={"summaries": summaries},
    )
    assert resp.status_code == 201, resp.text


def _summary(
    node_id: str = NODE_A,
    decision_point: str = "provider_spec",
    slot_id: str = "claude",
    sample_count: int = 10,
    successes: int = 9,
    failures: int = 1,
    mean_duration_s: float = 70.0,
    mean_value_score: float = 0.8,
) -> dict:
    return {
        "node_id": node_id,
        "decision_point": decision_point,
        "slot_id": slot_id,
        "period_start": "2026-03-20T10:00:00Z",
        "period_end": "2026-03-20T18:00:00Z",
        "sample_count": sample_count,
        "successes": successes,
        "failures": failures,
        "mean_duration_s": mean_duration_s,
        "mean_value_score": mean_value_score,
        "error_classes_json": {},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_aggregated_stats_empty_returns_defaults(client):
    """No data returns empty structures, not errors."""
    resp = client.get("/api/federation/nodes/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["providers"] == {}
    assert body["task_types"] == {}
    assert body["alerts"] == []
    assert body["window_days"] == 7
    assert body["total_measurements"] == 0


def test_aggregated_stats_single_node(client):
    """One node's data aggregated correctly."""
    _register_node(client, NODE_A, hostname="macbook-pro", os_type="darwin")
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, slot_id="claude", sample_count=10, successes=9, failures=1, mean_duration_s=70.0),
    ])

    resp = client.get("/api/federation/nodes/stats")
    assert resp.status_code == 200
    body = resp.json()

    assert NODE_A in body["nodes"]
    assert body["nodes"][NODE_A]["hostname"] == "macbook-pro"

    assert "claude" in body["providers"]
    p = body["providers"]["claude"]
    assert p["node_count"] == 1
    assert p["total_samples"] == 10
    assert p["total_successes"] == 9
    assert p["total_failures"] == 1
    assert p["overall_success_rate"] == 0.9
    assert p["avg_duration_s"] == 70.0
    assert NODE_A in p["per_node"]
    assert p["per_node"][NODE_A]["samples"] == 10

    assert body["total_measurements"] == 10


def test_aggregated_stats_multi_node(client):
    """Two nodes' data combined correctly."""
    _register_node(client, NODE_A)
    _register_node(client, NODE_B)
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, slot_id="claude", sample_count=50, successes=50, failures=0, mean_duration_s=65.0),
    ])
    _push_summaries(client, NODE_B, [
        _summary(node_id=NODE_B, slot_id="claude", sample_count=92, successes=85, failures=7, mean_duration_s=73.0),
    ])

    resp = client.get("/api/federation/nodes/stats")
    body = resp.json()

    p = body["providers"]["claude"]
    assert p["node_count"] == 2
    assert p["total_samples"] == 142
    assert p["total_successes"] == 135
    assert p["total_failures"] == 7
    # (50*65 + 92*73) / 142 = (3250 + 6716) / 142 = 70.18...
    assert 70.0 <= p["avg_duration_s"] <= 70.3
    assert NODE_A in p["per_node"]
    assert NODE_B in p["per_node"]
    assert p["per_node"][NODE_A]["success_rate"] == 1.0
    assert body["total_measurements"] == 142


def test_aggregated_stats_per_task_type(client):
    """Task type breakdown computed correctly."""
    _register_node(client, NODE_A)
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, decision_point="provider_spec", slot_id="claude",
                 sample_count=30, successes=30, failures=0, mean_duration_s=72.5),
        _summary(node_id=NODE_A, decision_point="provider_impl", slot_id="claude",
                 sample_count=20, successes=18, failures=2, mean_duration_s=80.0),
    ])

    resp = client.get("/api/federation/nodes/stats")
    body = resp.json()

    assert "spec" in body["task_types"]
    assert "impl" in body["task_types"]
    spec_claude = body["task_types"]["spec"]["providers"]["claude"]
    assert spec_claude["total_samples"] == 30
    assert spec_claude["success_rate"] == 1.0
    assert spec_claude["avg_duration_s"] == 72.5

    impl_claude = body["task_types"]["impl"]["providers"]["claude"]
    assert impl_claude["total_samples"] == 20
    assert impl_claude["success_rate"] == 0.9


def test_alert_generated_below_50pct(client):
    """Provider with <50% success triggers alert."""
    _register_node(client, NODE_A)
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, slot_id="bad-model", sample_count=10, successes=3, failures=7),
    ])

    resp = client.get("/api/federation/nodes/stats")
    body = resp.json()

    assert len(body["alerts"]) >= 1
    alert = [a for a in body["alerts"] if a["provider"] == "bad-model"][0]
    assert alert["value"] == 0.3
    assert alert["threshold"] == 0.5
    assert "50%" in alert["message"]


def test_window_filter_excludes_old_data(client):
    """Data older than window_days excluded."""
    _register_node(client, NODE_A)
    # Push some data (will have pushed_at = now)
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, slot_id="claude", sample_count=10, successes=10, failures=0),
    ])

    # Manually backdate the pushed_at to 30 days ago
    from app.services import unified_db as _udb
    from app.services.federation_service import NodeMeasurementSummaryRecord
    with _udb.session() as s:
        for rec in s.query(NodeMeasurementSummaryRecord).all():
            old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
            rec.pushed_at = old_ts

    # With window_days=7, old data should be excluded
    resp = client.get("/api/federation/nodes/stats?window_days=7")
    body = resp.json()
    assert body["total_measurements"] == 0
    assert body["providers"] == {}


def test_network_endpoint_compatible_shape(client):
    """/stats/network shape matches /stats plus nodes."""
    _register_node(client, NODE_A)
    _push_summaries(client, NODE_A, [
        _summary(node_id=NODE_A, slot_id="claude", sample_count=10, successes=9, failures=1),
    ])

    resp = client.get("/api/providers/stats/network")
    assert resp.status_code == 200
    body = resp.json()

    # Must have keys matching /api/providers/stats format
    assert "providers" in body
    assert "task_types" in body
    assert "alerts" in body
    assert "summary" in body
    # Plus the extra nodes field
    assert "nodes" in body
    assert "window_days" in body

    # Summary shape matches
    summary = body["summary"]
    assert "total_providers" in summary
    assert "healthy_providers" in summary
    assert "attention_needed" in summary
    assert "total_measurements" in summary

    # Provider shape includes compatibility fields
    p = body["providers"]["claude"]
    assert "total_runs" in p
    assert "successes" in p
    assert "failures" in p
    assert "success_rate" in p
    assert "avg_duration_s" in p
    assert "node_count" in p
    assert "per_node" in p

    # Nodes present
    assert NODE_A in body["nodes"]
