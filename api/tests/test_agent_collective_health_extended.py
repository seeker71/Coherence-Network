"""Extended tests for spec 114: Collective Coherence, Resonance, Flow, and Friction Health.

Covers additional acceptance criteria beyond the two baseline tests:
- window_days parameter: default, custom, clamping (low/high)
- Graceful degradation with empty data (neutral 0.5 scores)
- Pillar diagnostics have all required fields
- top_friction_queue is top-level only (not inside friction pillar)
- top_opportunities structure validation
- Score range contract [0.0, 1.0] for all scores
- collective_value formula: coherence * resonance * flow * (1 - friction)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service, friction_service, metrics_service


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


# ---------------------------------------------------------------------------
# Scenario 3 — window_days parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_window_days_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default window_days must be 7 when param is omitted."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    assert response.json()["window_days"] == 7


@pytest.mark.asyncio
async def test_collective_health_window_days_custom(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Custom window_days=14 must be reflected in the response."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health?window_days=14")

    assert response.status_code == 200
    assert response.json()["window_days"] == 14


@pytest.mark.asyncio
async def test_collective_health_window_days_boundary_min(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days=1 (minimum valid) must return HTTP 200 with window_days=1."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health?window_days=1")

    assert response.status_code == 200
    assert response.json()["window_days"] == 1


@pytest.mark.asyncio
async def test_collective_health_window_days_boundary_max(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days=30 (maximum valid) must return HTTP 200 with window_days=30."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health?window_days=30")

    assert response.status_code == 200
    assert response.json()["window_days"] == 30


# ---------------------------------------------------------------------------
# Graceful degradation — empty data neutral scores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_empty_data_graceful_degradation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Zero tasks and no friction events must return neutral scores (0.5) — no crash."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()

    scores = payload["scores"]
    # With zero tasks all pillar scores should be 0.5
    assert scores["coherence"] == pytest.approx(0.5)
    assert scores["resonance"] == pytest.approx(0.5)
    assert scores["flow"] == pytest.approx(0.5)
    # collective_value = 0.5 * 0.5 * 0.5 * (1 - friction_score)
    expected_cv = round(0.5 * 0.5 * 0.5 * (1.0 - float(scores["friction"])), 4)
    assert float(scores["collective_value"]) == pytest.approx(expected_cv, rel=1e-5)

    # Lists must be empty lists, not null
    assert isinstance(payload["top_friction_queue"], list)
    assert isinstance(payload["top_opportunities"], list)


# ---------------------------------------------------------------------------
# Score range contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_score_range_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """All scores in the `scores` object must be floats in [0.0, 1.0]."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    scores = response.json()["scores"]

    for key in ("coherence", "resonance", "flow", "friction", "collective_value"):
        assert key in scores, f"missing scores.{key}"
        value = float(scores[key])
        assert 0.0 <= value <= 1.0, f"scores.{key} = {value} out of [0,1]"


# ---------------------------------------------------------------------------
# collective_value formula
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_collective_value_formula(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """collective_value must equal coherence * resonance * flow * (1 - friction) to 4dp."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    s = response.json()["scores"]
    expected = round(
        float(s["coherence"]) * float(s["resonance"]) * float(s["flow"]) * (1.0 - float(s["friction"])),
        4,
    )
    actual = round(float(s["collective_value"]), 4)
    assert abs(expected - actual) < 1e-5, f"Formula mismatch: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Scenario 5 — pillar diagnostics fully populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_coherence_diagnostics_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """coherence pillar must contain all required diagnostic fields."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    coherence = response.json()["coherence"]
    for field in ("score", "task_count", "target_state_coverage", "task_card_coverage", "task_card_quality", "evidence_coverage"):
        assert field in coherence, f"missing coherence.{field}"


@pytest.mark.asyncio
async def test_collective_health_resonance_diagnostics_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """resonance pillar must contain all required diagnostic fields."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    resonance = response.json()["resonance"]
    for field in (
        "score",
        "task_count",
        "tracked_reference_total",
        "reused_reference_count",
        "reference_reuse_ratio",
        "completion_event_count",
        "traceable_completion_ratio",
        "learning_capture_ratio",
    ):
        assert field in resonance, f"missing resonance.{field}"


@pytest.mark.asyncio
async def test_collective_health_flow_diagnostics_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """flow pillar must contain all required diagnostic fields including status_counts."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    flow = response.json()["flow"]
    for field in (
        "score",
        "task_count",
        "completion_ratio",
        "active_flow_ratio",
        "throughput_factor",
        "latency_factor",
        "status_counts",
    ):
        assert field in flow, f"missing flow.{field}"
    assert isinstance(flow["status_counts"], dict)


@pytest.mark.asyncio
async def test_collective_health_friction_diagnostics_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """friction pillar must contain all required diagnostic fields."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    friction = response.json()["friction"]
    for field in ("score", "event_count", "open_events", "open_density", "energy_loss", "issue_count"):
        assert field in friction, f"missing friction.{field}"


# ---------------------------------------------------------------------------
# top_friction_queue is top-level only (not inside friction pillar)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_friction_queue_is_top_level_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """top_friction_queue must be a top-level field, NOT inside the friction pillar."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    # Add a friction event so the queue is non-trivially populated
    friction_service.append_event(
        __import__("app.models.friction", fromlist=["FrictionEvent"]).FrictionEvent(
            id="fric-ext-toplevel-1",
            timestamp=datetime.now(timezone.utc),
            stage="execution",
            block_type="timeout",
            severity="medium",
            owner="runner",
            unblock_condition="retry",
            energy_loss_estimate=3.0,
            cost_of_delay=1.5,
            status="open",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()

    # top_friction_queue must be at top level
    assert "top_friction_queue" in payload
    assert isinstance(payload["top_friction_queue"], list)

    # Must NOT be inside the friction pillar object
    assert "top_friction_queue" not in payload["friction"], (
        "top_friction_queue must not appear inside the friction pillar"
    )


# ---------------------------------------------------------------------------
# top_opportunities structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_top_opportunities_structure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each entry in top_opportunities must have pillar, signal, action, impact_estimate."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    opportunities = response.json()["top_opportunities"]
    assert isinstance(opportunities, list)
    assert len(opportunities) <= 5

    for opp in opportunities:
        for field in ("pillar", "signal", "action", "impact_estimate"):
            assert field in opp, f"missing top_opportunities[].{field}"
        assert opp["pillar"] in ("coherence", "resonance", "flow", "friction")
        assert 0.0 <= float(opp["impact_estimate"]) <= 1.0


# ---------------------------------------------------------------------------
# generated_at is ISO 8601 UTC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_generated_at_is_iso8601(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """generated_at must be a valid ISO 8601 UTC timestamp string."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    generated_at = response.json()["generated_at"]
    assert isinstance(generated_at, str)
    # Must be parseable as datetime and end with Z (UTC)
    assert generated_at.endswith("Z"), f"generated_at must end with Z, got: {generated_at}"
    datetime.fromisoformat(generated_at.replace("Z", "+00:00"))  # raises if invalid


# ---------------------------------------------------------------------------
# Friction queue entry shape when populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_friction_queue_entry_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each friction queue entry must have key, title, severity, signal, recommended_action."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    from app.models.friction import FrictionEvent

    friction_service.append_event(
        FrictionEvent(
            id="fric-ext-shape-1",
            timestamp=datetime.now(timezone.utc),
            stage="deploy",
            block_type="checks_failed",
            severity="high",
            owner="ci",
            unblock_condition="fix checks",
            energy_loss_estimate=5.0,
            cost_of_delay=2.5,
            status="open",
        )
    )

    (tmp_path / "monitor_issues.json").write_text(
        json.dumps({"issues": [], "last_check": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    queue = response.json()["top_friction_queue"]
    assert len(queue) >= 1

    entry = queue[0]
    for field in ("key", "title", "severity", "signal", "recommended_action"):
        assert field in entry, f"missing top_friction_queue[0].{field}"
    assert float(entry["signal"]) >= 0.0
    assert entry["severity"] in ("info", "low", "medium", "high", "critical")
