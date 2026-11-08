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


def test_cold_score_reads_the_idea_portfolio_once(monkeypatch):
    """Task completion and value realization share one portfolio read."""
    from app.services import coherence_signal_depth_service as svc
    import app.services.idea_service as idea_service

    svc.invalidate_cache()
    calls = {"n": 0}

    class _Portfolio:
        ideas: list = []

    def _list_ideas(**_kwargs):
        calls["n"] += 1
        return _Portfolio()

    monkeypatch.setattr(idea_service, "list_ideas", _list_ideas)
    svc.compute_coherence_score()
    assert calls["n"] == 1
    svc.invalidate_cache()


def test_expired_score_is_served_while_it_refreshes(monkeypatch):
    """A witness round receives the held score; the refresh does not block it."""
    from app.services import coherence_signal_depth_service as svc
    import app.services.idea_service as idea_service

    stale = {
        "score": 0.25,
        "signals": {},
        "signals_with_data": 0,
        "total_signals": 5,
        "computed_at": "stale-marker",
    }
    svc._CACHE["result"] = stale
    svc._CACHE["expires_at"] = 0.0
    svc._CACHE["refreshing"] = False

    class _Portfolio:
        ideas: list = []

    monkeypatch.setattr(idea_service, "list_ideas", lambda **_kwargs: _Portfolio())
    served = svc.compute_coherence_score()
    assert served["computed_at"] == "stale-marker"
    if svc._refresh_thread is not None:
        svc._refresh_thread.join(timeout=5)
    svc.invalidate_cache()


def test_signal_depth_service_returns_dict():
    """Unit-test the underlying service the router wraps."""
    from app.services import coherence_signal_depth_service
    result = coherence_signal_depth_service.compute_coherence_score()
    assert isinstance(result, dict)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
