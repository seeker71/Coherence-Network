"""Acceptance tests for spec 114: Collective Coherence-Resonance-Flow-Friction Health.

Covers the five named acceptance tests required by the spec:
  - test_collective_health_returns_200
  - test_collective_health_score_fields_present
  - test_collective_health_window_days_param
  - test_collective_health_collective_value_formula
  - test_collective_health_window_days_clamped
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))


# R1 — endpoint returns HTTP 200
@pytest.mark.asyncio
async def test_collective_health_returns_200(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /api/agent/collective-health returns HTTP 200 (R1)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200


# R1, R7 — response body contains required score fields and generated_at
@pytest.mark.asyncio
async def test_collective_health_score_fields_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Response includes all score fields, generated_at (ISO 8601 Z), and array fields (R1, R7)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    body = response.json()

    # scores object contains all five keys
    scores = body["scores"]
    for key in ("coherence", "resonance", "flow", "friction", "collective_value"):
        assert key in scores, f"scores missing key: {key}"
        assert isinstance(scores[key], (int, float)), f"scores.{key} is not numeric"
        assert 0.0 <= float(scores[key]) <= 1.0, f"scores.{key} out of [0,1]: {scores[key]}"

    # pillar detail objects present
    for pillar in ("coherence", "resonance", "flow", "friction"):
        assert pillar in body, f"response missing pillar detail: {pillar}"
        assert isinstance(body[pillar], dict)

    # generated_at ends in Z (ISO 8601 UTC)
    assert "generated_at" in body
    assert str(body["generated_at"]).endswith("Z"), (
        f"generated_at must end in Z: {body['generated_at']}"
    )

    # array fields are lists, not null
    assert isinstance(body["top_opportunities"], list)
    assert isinstance(body["top_friction_queue"], list)

    # arrays bounded at 5
    assert len(body["top_opportunities"]) <= 5
    assert len(body["top_friction_queue"]) <= 5


# R2 — window_days accepted and echoed
@pytest.mark.asyncio
async def test_collective_health_window_days_param(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days query param is accepted and echoed in response (R2)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # default should be 7
        r_default = await client.get("/api/agent/collective-health")
        assert r_default.status_code == 200
        assert r_default.json()["window_days"] == 7

        # explicit window_days=14 echoed back
        r14 = await client.get("/api/agent/collective-health?window_days=14")
        assert r14.status_code == 200
        assert r14.json()["window_days"] == 14

        # explicit window_days=1 echoed back
        r1 = await client.get("/api/agent/collective-health?window_days=1")
        assert r1.status_code == 200
        assert r1.json()["window_days"] == 1

        # explicit window_days=30 echoed back
        r30 = await client.get("/api/agent/collective-health?window_days=30")
        assert r30.status_code == 200
        assert r30.json()["window_days"] == 30


# R3, R9 — collective_value = coherence * resonance * flow * (1 - friction)
@pytest.mark.asyncio
async def test_collective_health_collective_value_formula(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """collective_value equals coherence * resonance * flow * (1 - friction) to 4dp (R3, R9)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    s = response.json()["scores"]

    coherence = float(s["coherence"])
    resonance = float(s["resonance"])
    flow = float(s["flow"])
    friction = float(s["friction"])
    collective_value = float(s["collective_value"])

    expected = round(coherence * resonance * flow * (1.0 - friction), 4)
    assert abs(collective_value - expected) < 0.0002, (
        f"Formula mismatch: {coherence} * {resonance} * {flow} * (1 - {friction}) "
        f"= {expected}, got {collective_value}"
    )

    # friction=1.0 absorber edge: collective_value = 0
    # Verify asymmetry: friction represents badness (R9)
    # When friction is 1.0, (1 - friction) = 0.0 → collective_value = 0
    if friction == 1.0:
        assert collective_value == pytest.approx(0.0)


# R10 — window_days clamped silently, no HTTP 422
@pytest.mark.asyncio
async def test_collective_health_window_days_clamped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days outside [1, 30] clamped server-side, no HTTP 422 (R10)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 0 → clamped to 1
        r_low = await client.get("/api/agent/collective-health?window_days=0")
        assert r_low.status_code == 200, f"Expected 200, got {r_low.status_code}"
        assert r_low.json()["window_days"] == 1, (
            f"window_days=0 should clamp to 1, got {r_low.json()['window_days']}"
        )

        # 99 → clamped to 30
        r_high = await client.get("/api/agent/collective-health?window_days=99")
        assert r_high.status_code == 200, f"Expected 200, got {r_high.status_code}"
        assert r_high.json()["window_days"] == 30, (
            f"window_days=99 should clamp to 30, got {r_high.json()['window_days']}"
        )

        # -5 → clamped to 1
        r_neg = await client.get("/api/agent/collective-health?window_days=-5")
        assert r_neg.status_code == 200
        assert r_neg.json()["window_days"] == 1
