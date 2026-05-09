"""Tests for the coherence-algorithm-spec (specs/coherence-algorithm-spec.md).

Exercises the live coherence-score endpoint and the underlying signal
depth service. The score is a 0.0-1.0 float computed from actual system
data; the contract is that the response shape is stable, the score is
in range, and the supporting signal counts are non-negative.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_coherence_score_endpoint_returns_200(client):
    response = client.get("/api/coherence/score")
    assert response.status_code == 200


def test_coherence_score_response_shape(client):
    body = client.get("/api/coherence/score").json()
    for key in ("score", "signals", "signals_with_data", "total_signals", "computed_at"):
        assert key in body, f"missing key {key!r}"


def test_coherence_score_value_is_in_unit_range(client):
    body = client.get("/api/coherence/score").json()
    score = body["score"]
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 1.0


def test_coherence_score_signal_counts_are_consistent(client):
    body = client.get("/api/coherence/score").json()
    assert body["signals_with_data"] >= 0
    assert body["total_signals"] >= 0
    assert body["signals_with_data"] <= body["total_signals"]


def test_coherence_score_computed_at_is_iso(client):
    body = client.get("/api/coherence/score").json()
    assert isinstance(body["computed_at"], str)
    assert "T" in body["computed_at"]


def test_signal_depth_service_returns_dict():
    """Unit-test the underlying service the router wraps."""
    from app.services import coherence_signal_depth_service
    result = coherence_signal_depth_service.compute_coherence_score()
    assert isinstance(result, dict)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
