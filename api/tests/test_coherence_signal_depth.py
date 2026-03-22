"""Tests for GET /api/coherence/score — real-time coherence signal depth."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.fixture(autouse=True)
def _clear_signal_cache():
    from app.services import coherence_signal_depth_service
    coherence_signal_depth_service.invalidate_cache()
    yield
    coherence_signal_depth_service.invalidate_cache()


@pytest.mark.asyncio
async def test_coherence_score_returns_200():
    """Endpoint returns 200 with valid coherence score structure."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coherence/score", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert 0.0 <= body["score"] <= 1.0
    assert "signals" in body
    assert "signals_with_data" in body
    assert "total_signals" in body
    assert body["total_signals"] == 5
    assert "computed_at" in body


@pytest.mark.asyncio
async def test_coherence_score_signal_structure():
    """Each signal has score, weight, and details."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coherence/score", headers=AUTH_HEADERS)

    body = resp.json()
    expected_signals = [
        "task_completion",
        "spec_coverage",
        "contribution_activity",
        "runtime_health",
        "value_realization",
    ]
    for signal_name in expected_signals:
        assert signal_name in body["signals"], f"Missing signal: {signal_name}"
        signal = body["signals"][signal_name]
        assert "score" in signal
        assert "weight" in signal
        assert "details" in signal
        assert 0.0 <= signal["score"] <= 1.0
        assert 0.0 <= signal["weight"] <= 1.0


@pytest.mark.asyncio
async def test_coherence_score_weights_sum_to_one():
    """Signal weights should sum to approximately 1.0."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coherence/score", headers=AUTH_HEADERS)

    body = resp.json()
    total_weight = sum(s["weight"] for s in body["signals"].values())
    assert abs(total_weight - 1.0) < 0.01


@pytest.mark.asyncio
async def test_coherence_score_with_ideas(tmp_path):
    """Score reflects real idea data when ideas exist."""
    import os
    os.environ["IDEA_PORTFOLIO_PATH"] = str(tmp_path / "ideas.json")

    from app.services import unified_db, idea_service, coherence_signal_depth_service
    unified_db.reset_engine()
    coherence_signal_depth_service.invalidate_cache()
    idea_service._TRACKED_IDEA_CACHE["expires_at"] = 0.0
    idea_service._TRACKED_IDEA_CACHE["idea_ids"] = []
    idea_service._TRACKED_IDEA_CACHE["cache_key"] = ""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create an idea
        await client.post(
            "/api/ideas",
            json={
                "id": "test-depth-1",
                "name": "Test Idea",
                "description": "A test idea for coherence depth",
                "potential_value": 100.0,
                "estimated_cost": 10.0,
            },
            headers=AUTH_HEADERS,
        )

        # Mark it validated
        await client.patch(
            "/api/ideas/test-depth-1",
            json={"manifestation_status": "validated", "actual_value": 80.0},
            headers=AUTH_HEADERS,
        )

        coherence_signal_depth_service.invalidate_cache()
        resp = await client.get("/api/coherence/score", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    body = resp.json()

    # Task completion should be 1.0 (1 validated / 1 total)
    tc = body["signals"]["task_completion"]
    assert tc["score"] == 1.0
    assert tc["details"]["validated"] == 1

    # Value realization should reflect actual/potential
    vr = body["signals"]["value_realization"]
    assert vr["score"] == 0.8  # 80/100
    assert vr["details"]["realization_ratio"] == 0.8

    os.environ.pop("IDEA_PORTFOLIO_PATH", None)


@pytest.mark.asyncio
async def test_coherence_score_empty_state():
    """With no data, signals fall back to 0.5 (neutral) and are marked as no-data."""
    import os
    os.environ["IDEA_PORTFOLIO_PATH"] = str("/tmp/test_empty_coherence.json")

    from app.services import unified_db, idea_service, coherence_signal_depth_service
    unified_db.reset_engine()
    coherence_signal_depth_service.invalidate_cache()
    idea_service._TRACKED_IDEA_CACHE["expires_at"] = 0.0
    idea_service._TRACKED_IDEA_CACHE["idea_ids"] = []
    idea_service._TRACKED_IDEA_CACHE["cache_key"] = ""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coherence/score", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    body = resp.json()

    # With no data, signals_with_data should be low
    assert body["signals_with_data"] <= body["total_signals"]
    # Score should be around 0.5 (neutral) when no data
    assert 0.0 <= body["score"] <= 1.0

    os.environ.pop("IDEA_PORTFOLIO_PATH", None)


def test_service_compute_directly():
    """Service function returns valid dict structure."""
    from app.services.coherence_signal_depth_service import compute_coherence_score

    result = compute_coherence_score()
    assert isinstance(result, dict)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    assert "signals" in result
    assert len(result["signals"]) == 5
    assert "signals_with_data" in result
    assert "computed_at" in result


def test_cache_invalidation():
    """Cache invalidation works correctly."""
    from app.services.coherence_signal_depth_service import (
        compute_coherence_score,
        invalidate_cache,
        _CACHE,
    )

    # First call populates cache
    result1 = compute_coherence_score()
    assert _CACHE["result"] is not None

    # Invalidate
    invalidate_cache()
    assert _CACHE["result"] is None
    assert _CACHE["expires_at"] == 0.0

    # Second call recomputes
    result2 = compute_coherence_score()
    assert result2["score"] == result1["score"]  # same data, same score
