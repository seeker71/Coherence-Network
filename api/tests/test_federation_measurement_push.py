"""Tests for Spec 131: Federation Measurement Push."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

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
# Helper: build a valid summary dict
# ---------------------------------------------------------------------------

def _summary(
    node_id: str = "node-alpha",
    decision_point: str = "provider_code_gen",
    slot_id: str = "openrouter/deepseek-v3",
    sample_count: int = 10,
    successes: int = 8,
    failures: int = 2,
    mean_duration_s: float = 2.5,
    mean_value_score: float = 0.75,
    error_classes_json: dict | None = None,
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
        "error_classes_json": error_classes_json or {},
    }


# ---------------------------------------------------------------------------
# POST endpoint tests
# ---------------------------------------------------------------------------

def test_post_summaries_201(client):
    """Valid batch returns 201 with stored count."""
    resp = client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": [_summary()]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["stored"] == 1
    assert body["node_id"] == "node-alpha"


def test_post_node_id_mismatch_422(client):
    """Path vs summary node_id mismatch returns 422."""
    resp = client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": [_summary(node_id="node-beta")]},
    )
    assert resp.status_code == 422
    assert "mismatch" in resp.json()["detail"].lower()


def test_post_sample_count_mismatch_422(client):
    """sample_count != successes + failures returns 422."""
    resp = client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": [_summary(sample_count=99, successes=8, failures=2)]},
    )
    assert resp.status_code == 422
    assert "sample_count" in resp.json()["detail"].lower()


def test_post_empty_batch_422(client):
    """Empty summaries list returns 422."""
    resp = client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET endpoint tests
# ---------------------------------------------------------------------------

def test_get_summaries_returns_stored(client):
    """GET returns previously POSTed summaries."""
    client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": [_summary()]},
    )
    resp = client.get("/api/federation/nodes/node-alpha/measurements")
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_id"] == "node-alpha"
    assert body["total"] == 1
    assert len(body["summaries"]) == 1
    s = body["summaries"][0]
    assert s["decision_point"] == "provider_code_gen"
    assert s["slot_id"] == "openrouter/deepseek-v3"
    assert "id" in s
    assert "pushed_at" in s


def test_get_summaries_filter_by_decision_point(client):
    """decision_point query param filters results."""
    client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={
            "summaries": [
                _summary(decision_point="dp_a"),
                _summary(decision_point="dp_b"),
            ]
        },
    )
    resp = client.get("/api/federation/nodes/node-alpha/measurements?decision_point=dp_a")
    body = resp.json()
    assert body["total"] == 1
    assert body["summaries"][0]["decision_point"] == "dp_a"


def test_get_summaries_pagination(client):
    """limit/offset pagination works correctly."""
    summaries = [_summary(slot_id=f"slot-{i}") for i in range(5)]
    client.post(
        "/api/federation/nodes/node-alpha/measurements",
        json={"summaries": summaries},
    )
    resp = client.get("/api/federation/nodes/node-alpha/measurements?limit=2&offset=0")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["summaries"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    resp2 = client.get("/api/federation/nodes/node-alpha/measurements?limit=2&offset=2")
    body2 = resp2.json()
    assert body2["total"] == 5
    assert len(body2["summaries"]) == 2
    assert body2["offset"] == 2


# ---------------------------------------------------------------------------
# Client push service tests
# ---------------------------------------------------------------------------

def test_push_aggregates_measurements_correctly(tmp_path):
    """Push client computes correct aggregates from raw SlotSelector data."""
    from app.services.federation_push_service import compute_summaries

    now = datetime.now(timezone.utc)
    measurements = [
        {
            "slot_id": "model-a",
            "value_score": 1.0,
            "resource_cost": 1.0,
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "duration_s": 2.0,
        },
        {
            "slot_id": "model-a",
            "value_score": 0.0,
            "resource_cost": 1.0,
            "timestamp": (now - timedelta(minutes=20)).isoformat(),
            "duration_s": 4.0,
            "error_class": "timeout",
        },
        {
            "slot_id": "model-a",
            "value_score": 0.8,
            "resource_cost": 1.0,
            "timestamp": (now - timedelta(minutes=10)).isoformat(),
        },
    ]
    store_dir = tmp_path / "slot_measurements"
    store_dir.mkdir()
    (store_dir / "provider_code_gen.json").write_text(json.dumps(measurements))

    last_push = (now - timedelta(hours=1)).isoformat()
    result = compute_summaries(store_dir, last_push, node_id="test-node")

    assert len(result) == 1
    s = result[0]
    assert s["node_id"] == "test-node"
    assert s["decision_point"] == "provider_code_gen"
    assert s["slot_id"] == "model-a"
    assert s["sample_count"] == 3
    assert s["successes"] == 2  # value_score > 0.0
    assert s["failures"] == 1   # value_score == 0.0
    # mean_duration_s: only first two have duration_s => (2.0 + 4.0) / 2 = 3.0
    assert s["mean_duration_s"] == 3.0
    # mean_value_score: (1.0 + 0.0 + 0.8) / 3
    assert abs(s["mean_value_score"] - 0.6) < 0.01
    assert s["error_classes_json"] == {"timeout": 1}


def test_push_respects_last_push_timestamp(tmp_path):
    """Only measurements after last_push are included."""
    from app.services.federation_push_service import compute_summaries

    now = datetime.now(timezone.utc)
    old_measurement = {
        "slot_id": "model-a",
        "value_score": 1.0,
        "resource_cost": 1.0,
        "timestamp": (now - timedelta(hours=5)).isoformat(),
    }
    new_measurement = {
        "slot_id": "model-a",
        "value_score": 0.5,
        "resource_cost": 1.0,
        "timestamp": (now - timedelta(minutes=10)).isoformat(),
        "duration_s": 1.5,
    }
    store_dir = tmp_path / "slot_measurements"
    store_dir.mkdir()
    (store_dir / "dp.json").write_text(json.dumps([old_measurement, new_measurement]))

    # Set last_push to 1 hour ago -- only new_measurement should be included
    last_push = (now - timedelta(hours=1)).isoformat()
    result = compute_summaries(store_dir, last_push, node_id="n")
    assert len(result) == 1
    assert result[0]["sample_count"] == 1
    assert result[0]["mean_value_score"] == 0.5


def test_push_updates_last_push_on_success(tmp_path):
    """last_push.json updated after successful push."""
    from app.services.federation_push_service import (
        load_last_push,
        save_last_push,
        push_to_hub,
    )

    lp_path = tmp_path / "last_push.json"
    assert load_last_push(lp_path) is None

    # Simulate successful push
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"stored": 1, "node_id": "n"}
    with patch("app.services.federation_push_service.httpx.post", return_value=mock_resp):
        ok = push_to_hub("http://hub:8000", "n", [{"fake": "summary"}])
    assert ok is True

    # Now save last_push (caller is responsible for saving after success)
    ts = datetime.now(timezone.utc).isoformat()
    save_last_push(ts, lp_path)
    assert load_last_push(lp_path) == ts


def test_push_no_update_on_failure(tmp_path):
    """last_push.json unchanged when hub returns error."""
    from app.services.federation_push_service import push_to_hub, load_last_push, save_last_push

    lp_path = tmp_path / "last_push.json"
    original_ts = "2026-03-19T00:00:00Z"
    save_last_push(original_ts, lp_path)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    with patch("app.services.federation_push_service.httpx.post", return_value=mock_resp):
        ok = push_to_hub("http://hub:8000", "n", [{"fake": "summary"}])
    assert ok is False

    # last_push should be unchanged
    assert load_last_push(lp_path) == original_ts


def test_push_hub_unreachable_no_exception(tmp_path, caplog):
    """Connection error logged as warning, no exception raised."""
    from app.services.federation_push_service import push_to_hub

    import httpx as httpx_lib
    with patch(
        "app.services.federation_push_service.httpx.post",
        side_effect=httpx_lib.ConnectError("refused"),
    ):
        with caplog.at_level(logging.WARNING):
            ok = push_to_hub("http://unreachable:9999", "n", [{"fake": "summary"}])
    assert ok is False
    assert any("unreachable" in r.message.lower() for r in caplog.records)
