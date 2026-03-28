"""Acceptance tests for spec 114: collective coherence, resonance, flow, friction health.

Covers GET /api/agent/collective-health payload shape, score ranges, and graceful
degradation when operational data is sparse. Complements test_agent_collective_health_api.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service, metrics_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _iso_z_re() -> re.Pattern[str]:
    return re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


@pytest.mark.asyncio
async def test_114_collective_health_full_payload_shape_and_ranges(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))
    (tmp_path / "monitor_issues.json").write_text(
        json.dumps({"issues": [], "last_check": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()

    assert set(payload.keys()) >= {
        "generated_at",
        "window_days",
        "scores",
        "coherence",
        "resonance",
        "flow",
        "friction",
        "top_friction_queue",
        "top_opportunities",
    }
    assert _iso_z_re().match(payload["generated_at"])
    assert isinstance(payload["window_days"], int)
    assert 1 <= payload["window_days"] <= 30

    scores = payload["scores"]
    assert set(scores.keys()) == {
        "coherence",
        "resonance",
        "flow",
        "friction",
        "collective_value",
    }
    for key in scores:
        v = float(scores[key])
        assert 0.0 <= v <= 1.0

    expected_cv = round(
        float(scores["coherence"])
        * float(scores["resonance"])
        * float(scores["flow"])
        * (1.0 - float(scores["friction"])),
        4,
    )
    assert float(scores["collective_value"]) == pytest.approx(expected_cv, rel=1e-6)

    for block_name in ("coherence", "resonance", "flow"):
        block = payload[block_name]
        assert isinstance(block, dict)
        assert "score" in block
        assert 0.0 <= float(block["score"]) <= 1.0

    friction_block = payload["friction"]
    assert isinstance(friction_block, dict)
    assert "score" in friction_block
    assert "top_friction_queue" not in friction_block

    assert isinstance(payload["top_friction_queue"], list)
    for item in payload["top_friction_queue"]:
        assert set(item.keys()) >= {"key", "title", "severity", "signal"}
        assert isinstance(item["key"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["severity"], str)
        assert float(item["signal"]) >= 0.0

    assert isinstance(payload["top_opportunities"], list)
    for opp in payload["top_opportunities"]:
        assert set(opp.keys()) >= {"pillar", "signal", "impact_estimate"}
        assert isinstance(opp["pillar"], str)
        assert isinstance(opp["signal"], str)
        assert isinstance(opp["impact_estimate"], (int, float))
        assert 0.0 <= float(opp["impact_estimate"]) <= 1.0


@pytest.mark.asyncio
async def test_114_collective_health_sparse_data_still_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "missing_monitor.json"))

    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    p = response.json()
    for k in ("coherence", "resonance", "flow", "friction", "collective_value"):
        assert 0.0 <= float(p["scores"][k]) <= 1.0
    assert isinstance(p["top_friction_queue"], list)
    assert isinstance(p["top_opportunities"], list)


@pytest.mark.asyncio
async def test_114_collective_health_window_days_query(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))
    (tmp_path / "monitor_issues.json").write_text(
        json.dumps({"issues": [], "last_check": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r14 = await client.get("/api/agent/collective-health?window_days=14")
        r_bad = await client.get("/api/agent/collective-health?window_days=99")

    assert r14.status_code == 200
    assert r14.json()["window_days"] == 14

    assert r_bad.status_code == 422


@pytest.mark.asyncio
async def test_114_component_diagnostics_include_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))
    (tmp_path / "monitor_issues.json").write_text(
        json.dumps({"issues": [], "last_check": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    _reset_agent_store()

    metrics_service.record_task("m1", "impl", "worker-a", 10.0, "completed")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    p = response.json()
    assert "task_count" in p["coherence"]
    assert "task_count" in p["resonance"]
    assert "task_count" in p["flow"]
    assert "event_count" in p["friction"] or "open_events" in p["friction"]
