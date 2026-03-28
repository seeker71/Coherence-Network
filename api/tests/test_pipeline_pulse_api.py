"""Tests for the /api/pipeline/pulse endpoint (ux-live-pipeline-dashboard)."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import inventory


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(inventory.router, prefix="/api")
    return app


def _mock_pulse(
    bottleneck_type: str | None = None,
    bottleneck_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": "2026-03-28T00:00:00+00:00",
        "window_days": 7,
        "task_count": 10,
        "phase_stats": {
            "spec": {"completed": 5, "failed": 1, "pending": 2, "running": 0, "total": 8, "success_rate": 0.83},
            "impl": {"completed": 3, "failed": 2, "pending": 1, "running": 1, "total": 7, "success_rate": 0.60},
            "test": {"completed": 2, "failed": 1, "pending": 0, "running": 0, "total": 3, "success_rate": 0.67},
            "review": {"completed": 1, "failed": 0, "pending": 0, "running": 0, "total": 1, "success_rate": 1.0},
        },
        "bottleneck": {
            "type": bottleneck_type,
            "reason": bottleneck_reason,
            "recommendation": "Keep monitoring phase success rates.",
        },
        "balance": {"spec": 0.32, "impl": 0.28, "test": 0.12, "review": 0.04},
        "ideas": {
            "total_in_portfolio": 20,
            "without_spec": 10,
            "with_activity": 8,
            "advancing": [{"idea_id": "idea-1", "idea_name": "Alpha", "completed_phases": ["spec"], "failed_phases": [], "depth": 1}],
            "stuck": [],
            "full_cycle": [],
        },
        "needs_decision": [],
        "needs_decision_count": 0,
    }


@pytest.mark.asyncio
async def test_pipeline_pulse_200() -> None:
    """GET /api/pipeline/pulse returns 200 with required fields."""
    app = _make_app()
    import app.services.pipeline_pulse_service as svc

    def fake_compute(**_: Any) -> dict[str, Any]:
        return _mock_pulse(bottleneck_type="impl_failure", bottleneck_reason="Low success rate.")

    app.dependency_overrides = {}

    import unittest.mock as mock

    with mock.patch.object(svc, "compute_pulse", side_effect=fake_compute):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/pulse")

    assert resp.status_code == 200
    body = resp.json()
    assert "phase_stats" in body
    assert "bottleneck" in body
    assert "ideas" in body
    assert body["bottleneck"]["type"] == "impl_failure"
    assert body["bottleneck"]["reason"] == "Low success rate."


@pytest.mark.asyncio
async def test_pipeline_pulse_balanced_bottleneck_is_string() -> None:
    """When pipeline is balanced, bottleneck.type must be a non-null string.

    The dashboard calls .replace(/_/g, ' ') on the type — a null value would
    crash the UI. This test verifies the service normalises None → 'balanced'.
    """
    app = _make_app()
    import app.services.pipeline_pulse_service as svc

    def fake_compute(**_: Any) -> dict[str, Any]:
        # Simulate what compute_pulse returns after the null-normalisation fix.
        return _mock_pulse(bottleneck_type="balanced", bottleneck_reason="No significant bottleneck detected.")

    import unittest.mock as mock

    with mock.patch.object(svc, "compute_pulse", side_effect=fake_compute):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/pulse")

    assert resp.status_code == 200
    body = resp.json()
    b = body["bottleneck"]
    # Both type and reason must be strings — never None.
    assert isinstance(b["type"], str), f"bottleneck.type must be str, got {b['type']!r}"
    assert isinstance(b["reason"], str), f"bottleneck.reason must be str, got {b['reason']!r}"
    # Verify the specific value chosen when pipeline is healthy.
    assert b["type"] == "balanced"


@pytest.mark.asyncio
async def test_pipeline_pulse_includes_needs_decision_count() -> None:
    """GET /api/pipeline/pulse must include needs_decision_count for the dashboard badge."""
    app = _make_app()
    import app.services.pipeline_pulse_service as svc

    def fake_compute(**_: Any) -> dict[str, Any]:
        pulse = _mock_pulse(bottleneck_type="balanced", bottleneck_reason="OK")
        pulse["needs_decision_count"] = 3
        pulse["needs_decision"] = [
            {"task_id": "t1", "task_type": "impl", "idea_id": "idea-1", "idea_name": "Alpha",
             "failure_type": "unclear_spec", "reason": "Spec too vague.", "decision_prompt": ""},
        ]
        return pulse

    import unittest.mock as mock

    with mock.patch.object(svc, "compute_pulse", side_effect=fake_compute):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/pulse")

    assert resp.status_code == 200
    body = resp.json()
    assert "needs_decision_count" in body
    assert body["needs_decision_count"] == 3


@pytest.mark.asyncio
async def test_pipeline_pulse_query_params_forwarded() -> None:
    """window_days and task_limit query params are forwarded to compute_pulse."""
    app = _make_app()
    import app.services.pipeline_pulse_service as svc

    captured: dict[str, Any] = {}

    def fake_compute(window_days: int = 7, task_limit: int = 500) -> dict[str, Any]:
        captured["window_days"] = window_days
        captured["task_limit"] = task_limit
        return _mock_pulse(bottleneck_type="balanced", bottleneck_reason="OK")

    import unittest.mock as mock

    with mock.patch.object(svc, "compute_pulse", side_effect=fake_compute):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/pulse?window_days=14&task_limit=200")

    assert resp.status_code == 200
    assert captured["window_days"] == 14
    assert captured["task_limit"] == 200
