"""Integration tests for end-to-end federation data flow."""

from __future__ import annotations

import json

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


def _register_node(client: TestClient, node_id: str, hostname: str) -> None:
    resp = client.post(
        "/api/federation/nodes",
        json={
            "node_id": node_id,
            "hostname": hostname,
            "os_type": "linux",
            "providers": ["openrouter/deepseek-v3"],
            "capabilities": {},
        },
    )
    assert resp.status_code in (200, 201), resp.text


def _summary(
    node_id: str,
    *,
    slot_id: str,
    decision_point: str = "provider_code_gen",
    sample_count: int = 10,
    successes: int = 9,
    failures: int = 1,
    mean_duration_s: float = 2.0,
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
        "mean_value_score": round(successes / sample_count, 2) if sample_count else 0.0,
        "error_classes_json": {},
    }


def _push_measurements(client: TestClient, node_id: str, summaries: list[dict]) -> None:
    resp = client.post(
        f"/api/federation/nodes/{node_id}/measurements",
        json={"summaries": summaries},
    )
    assert resp.status_code == 201, resp.text


def test_full_flow_register_push_stats_compute_recommendation(client: TestClient):
    """End-to-end flow yields recommendation strategy for strong provider."""
    provider = "openrouter/deepseek-v3"
    node_ids = ["a1b2c3d4e5f60781", "a1b2c3d4e5f60782", "a1b2c3d4e5f60783"]

    for idx, node_id in enumerate(node_ids):
        _register_node(client, node_id=node_id, hostname=f"node-{idx}")
        _push_measurements(
            client,
            node_id,
            [_summary(node_id, slot_id=provider, sample_count=20, successes=19, failures=1)],
        )

    stats_resp = client.get("/api/federation/nodes/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_measurements"] == 60
    assert provider in stats["providers"]
    assert stats["providers"][provider]["node_count"] == 3
    assert stats["providers"][provider]["total_samples"] == 60
    assert stats["providers"][provider]["total_successes"] == 57
    assert stats["providers"][provider]["total_failures"] == 3
    assert len(stats["providers"][provider]["per_node"]) == 3

    compute_resp = client.post("/api/federation/strategies/compute")
    assert compute_resp.status_code == 200
    computed = compute_resp.json()
    assert computed["computed"] >= 1

    recommendations = [
        strategy
        for strategy in computed["strategies"]
        if strategy["strategy_type"] == "provider_recommendation"
    ]
    assert recommendations, f"No provider_recommendation in: {computed}"
    payload = json.loads(recommendations[0]["payload_json"])
    assert payload["recommended_provider"] == provider
    assert payload["node_count"] >= 3
    assert recommendations[0]["advisory_only"] is True


def test_full_flow_register_push_stats_compute_warning(client: TestClient):
    """End-to-end flow yields provider warning for low-success provider."""
    provider = "openrouter/bad-model"
    node_ids = ["b1b2c3d4e5f60781", "b1b2c3d4e5f60782"]

    for idx, node_id in enumerate(node_ids):
        _register_node(client, node_id=node_id, hostname=f"warning-node-{idx}")
        _push_measurements(
            client,
            node_id,
            [_summary(node_id, slot_id=provider, sample_count=20, successes=4, failures=16)],
        )

    stats_resp = client.get("/api/federation/nodes/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_measurements"] == 40
    assert provider in stats["providers"]
    assert any(alert["provider"] == provider for alert in stats["alerts"])

    compute_resp = client.post("/api/federation/strategies/compute")
    assert compute_resp.status_code == 200
    computed = compute_resp.json()
    assert computed["computed"] >= 1

    warnings = [
        strategy
        for strategy in computed["strategies"]
        if strategy["strategy_type"] == "provider_warning"
    ]
    assert warnings, f"No provider_warning in: {computed}"
    payload = json.loads(warnings[0]["payload_json"])
    assert payload["warned_provider"] == provider
    assert payload["success_rate"] < 0.5
    assert payload["node_count"] >= 2
