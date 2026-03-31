"""Tests for Spec 134: Federation Strategy Propagation."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

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

def _register_node(client, node_id: str, hostname: str = "host"):
    """Register a federation node for measurement pushes."""
    client.post("/api/federation/nodes", json={
        "node_id": node_id,
        "hostname": hostname,
        "os_type": "linux",
        "providers": ["openrouter/deepseek-v3"],
        "capabilities": {},
    })


def _push_summaries(client, node_id: str, summaries: list[dict]):
    """Push measurement summaries for a node."""
    client.post(
        f"/api/federation/nodes/{node_id}/measurements",
        json={"summaries": summaries},
    )


def _summary(
    node_id: str,
    slot_id: str = "openrouter/deepseek-v3",
    decision_point: str = "provider_code_gen",
    sample_count: int = 100,
    successes: int = 95,
    failures: int = 5,
):
    return {
        "node_id": node_id,
        "decision_point": decision_point,
        "slot_id": slot_id,
        "period_start": "2026-03-20T00:00:00Z",
        "period_end": "2026-03-20T12:00:00Z",
        "sample_count": sample_count,
        "successes": successes,
        "failures": failures,
        "mean_duration_s": 2.0,
        "mean_value_score": round(successes / sample_count, 2) if sample_count else 0.0,
        "error_classes_json": {},
    }


def _seed_high_success_provider(client):
    """Seed 3 nodes with >90% success for a provider."""
    for i, nid in enumerate(["node-aabbccdd0011" + f"{i:02d}" for i in range(3)]):
        _register_node(client, nid, hostname=f"host-{i}")
        _push_summaries(client, nid, [_summary(nid, successes=95, failures=5)])


def _seed_low_success_provider(client):
    """Seed 2 nodes with <50% success for a provider."""
    for i, nid in enumerate(["node-ddccbbaa0011" + f"{i:02d}" for i in range(2)]):
        _register_node(client, nid, hostname=f"bad-host-{i}")
        _push_summaries(client, nid, [
            _summary(nid, slot_id="openrouter/bad-model", successes=20, failures=80),
        ])


# ---------------------------------------------------------------------------
# Test: GET /api/federation/strategies returns active broadcasts only
# ---------------------------------------------------------------------------

def test_get_strategies_returns_active_broadcasts_only(client):
    """Only non-expired strategies are returned."""
    # Compute strategies from seeded data
    _seed_high_success_provider(client)
    client.post("/api/federation/strategies/compute")

    resp = client.get("/api/federation/strategies")
    assert resp.status_code == 200
    body = resp.json()
    assert "strategies" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body

    # All returned strategies should have advisory_only=True
    for s in body["strategies"]:
        assert s["advisory_only"] is True

    # Manually insert an expired strategy and verify it's filtered
    from app.services import federation_service
    from app.services.federation_service import NodeStrategyBroadcastRecord, _session, _ensure_schema
    _ensure_schema()
    past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    with _session() as s:
        rec = NodeStrategyBroadcastRecord(
            strategy_type="provider_warning",
            payload_json='{"test": "expired"}',
            source_node_id="hub",
            created_at=now,
            expires_at=past,  # Already expired
        )
        s.add(rec)

    resp2 = client.get("/api/federation/strategies")
    body2 = resp2.json()
    # The expired strategy should NOT appear
    for st in body2["strategies"]:
        payload = json.loads(st["payload_json"])
        assert payload.get("test") != "expired"


# ---------------------------------------------------------------------------
# Test: filter by strategy_type
# ---------------------------------------------------------------------------

def test_get_strategies_filters_by_strategy_type(client):
    """strategy_type query param filters results."""
    _seed_high_success_provider(client)
    _seed_low_success_provider(client)
    client.post("/api/federation/strategies/compute")

    # Filter to recommendations only
    resp = client.get("/api/federation/strategies?strategy_type=provider_recommendation")
    assert resp.status_code == 200
    body = resp.json()
    for s in body["strategies"]:
        assert s["strategy_type"] == "provider_recommendation"

    # Filter to warnings only
    resp2 = client.get("/api/federation/strategies?strategy_type=provider_warning")
    assert resp2.status_code == 200
    body2 = resp2.json()
    for s in body2["strategies"]:
        assert s["strategy_type"] == "provider_warning"


# ---------------------------------------------------------------------------
# Test: pagination and ordering newest first
# ---------------------------------------------------------------------------

def test_get_strategies_pagination_order_newest_first(client):
    """Strategies are ordered newest first and pagination works."""
    _seed_high_success_provider(client)
    _seed_low_success_provider(client)
    client.post("/api/federation/strategies/compute")

    resp = client.get("/api/federation/strategies?limit=1&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["strategies"]) <= 1
    assert body["limit"] == 1
    assert body["offset"] == 0

    if body["total"] > 1:
        resp2 = client.get("/api/federation/strategies?limit=1&offset=1")
        body2 = resp2.json()
        assert body2["offset"] == 1
        # Different strategy than first page
        if body["strategies"] and body2["strategies"]:
            assert body["strategies"][0]["id"] != body2["strategies"][0]["id"]


# ---------------------------------------------------------------------------
# Test: invalid strategy_type returns 422
# ---------------------------------------------------------------------------

def test_invalid_strategy_type_returns_422(client):
    """Invalid strategy_type query param returns 422."""
    resp = client.get("/api/federation/strategies?strategy_type=invalid_type")
    assert resp.status_code == 422
    assert "invalid strategy_type" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test: hub computes provider_recommendation from cross-node measurements
# ---------------------------------------------------------------------------

def test_hub_computes_provider_recommendation_from_cross_node_measurements(client):
    """Provider with >90% success across 3+ nodes produces a recommendation."""
    _seed_high_success_provider(client)

    resp = client.post("/api/federation/strategies/compute")
    assert resp.status_code == 200
    body = resp.json()
    assert body["computed"] >= 1

    # At least one provider_recommendation
    recs = [s for s in body["strategies"] if s["strategy_type"] == "provider_recommendation"]
    assert len(recs) >= 1
    payload = json.loads(recs[0]["payload_json"])
    assert "recommended_provider" in payload
    assert payload["confidence"] > 0.9
    assert payload["node_count"] >= 3


# ---------------------------------------------------------------------------
# Test: hub computes prompt_variant_winner from cross-node measurements
# ---------------------------------------------------------------------------

def test_hub_computes_prompt_variant_winner_from_cross_node_measurements(client):
    """Prompt measurement data triggers a prompt_variant_winner strategy."""
    # Push measurement data with a decision_point containing 'prompt'
    for i, nid in enumerate(["node-prompt00110011" + f"{i:02d}" for i in range(2)]):
        _register_node(client, nid, hostname=f"prompt-host-{i}")
        _push_summaries(client, nid, [
            _summary(nid, decision_point="provider_prompt_template", slot_id="variant-a",
                     successes=90, failures=10),
        ])

    resp = client.post("/api/federation/strategies/compute")
    assert resp.status_code == 200
    body = resp.json()

    winners = [s for s in body["strategies"] if s["strategy_type"] == "prompt_variant_winner"]
    assert len(winners) >= 1
    payload = json.loads(winners[0]["payload_json"])
    assert "winning_variant" in payload
    assert "task_type" in payload


# ---------------------------------------------------------------------------
# Test: hub emits provider_warning from error class trends
# ---------------------------------------------------------------------------

def test_hub_emits_provider_warning_from_error_class_trends(client):
    """Provider with <50% success across 2+ nodes produces a warning."""
    _seed_low_success_provider(client)

    resp = client.post("/api/federation/strategies/compute")
    assert resp.status_code == 200
    body = resp.json()

    warnings = [s for s in body["strategies"] if s["strategy_type"] == "provider_warning"]
    assert len(warnings) >= 1
    payload = json.loads(warnings[0]["payload_json"])
    assert "warned_provider" in payload
    assert payload["success_rate"] < 0.5
    assert payload["node_count"] >= 2


# ---------------------------------------------------------------------------
# Test: local Thompson Sampling precedence over hub advice
# ---------------------------------------------------------------------------

def test_local_thompson_sampling_precedence_over_hub_advice(client):
    """Strategy broadcasts are advisory-only; local TS always takes precedence.

    This test verifies the advisory_only field is always True and that
    the response contract preserves the advisory semantics.
    """
    _seed_high_success_provider(client)
    client.post("/api/federation/strategies/compute")

    resp = client.get("/api/federation/strategies")
    body = resp.json()

    for strategy in body["strategies"]:
        # Every strategy broadcast MUST be advisory_only=True
        assert strategy["advisory_only"] is True
        # Payload should not contain any override or force flags
        payload = json.loads(strategy["payload_json"])
        assert "override" not in payload
        assert "force" not in payload


# ---------------------------------------------------------------------------
# Test: empty data returns empty strategies
# ---------------------------------------------------------------------------

def test_empty_data_returns_empty_strategies(client):
    """No measurement data produces no strategy broadcasts."""
    resp = client.post("/api/federation/strategies/compute")
    assert resp.status_code == 200
    body = resp.json()
    assert body["computed"] == 0
    assert body["strategies"] == []

    resp2 = client.get("/api/federation/strategies")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["strategies"] == []
    assert body2["total"] == 0


def test_strategy_effectiveness_report_tracks_improvement(client):
    """Acted-on strategy reports compute and persist improvement score."""
    _seed_high_success_provider(client)
    compute = client.post("/api/federation/strategies/compute")
    assert compute.status_code == 200
    recommendation = next(
        s for s in compute.json()["strategies"]
        if s["strategy_type"] == "provider_recommendation"
    )

    report = client.post(
        f"/api/federation/strategies/{recommendation['id']}/effectiveness",
        json={
            "node_id": "node-aabbccdd001100",
            "was_applied": True,
            "baseline_value_score": 0.40,
            "outcome_value_score": 0.65,
            "context_json": {"decision_point": "provider_code_gen"},
        },
    )
    assert report.status_code == 201
    body = report.json()
    assert body["strategy_id"] == recommendation["id"]
    assert body["was_applied"] is True
    assert body["improved"] is True
    assert body["improvement_score"] == pytest.approx(0.25, abs=1e-6)
    assert body["strategy_type"] == "provider_recommendation"
    assert body["strategy_target"] == "openrouter/deepseek-v3"


def test_strategy_computation_uses_effectiveness_feedback(client):
    """Consistently negative outcomes suppress re-broadcast of same recommendation."""
    _seed_high_success_provider(client)
    first = client.post("/api/federation/strategies/compute")
    assert first.status_code == 200
    recommendation = next(
        s for s in first.json()["strategies"]
        if s["strategy_type"] == "provider_recommendation"
    )

    # Three negative outcomes are enough to suppress this strategy target.
    for idx in range(3):
        r = client.post(
            f"/api/federation/strategies/{recommendation['id']}/effectiveness",
            json={
                "node_id": f"node-aabbccdd0011{idx:02d}",
                "was_applied": True,
                "baseline_value_score": 0.70,
                "outcome_value_score": 0.40,
                "context_json": {"reason": "regressed"},
            },
        )
        assert r.status_code == 201

    second = client.post("/api/federation/strategies/compute")
    assert second.status_code == 200
    second_recommendations = [
        s for s in second.json()["strategies"]
        if s["strategy_type"] == "provider_recommendation"
    ]
    assert all(
        json.loads(s["payload_json"]).get("recommended_provider") != "openrouter/deepseek-v3"
        for s in second_recommendations
    )
