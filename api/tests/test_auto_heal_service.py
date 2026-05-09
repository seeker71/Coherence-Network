"""Tests for the auto-heal-from-diagnostics spec
(specs/auto-heal-from-diagnostics.md).

The auto-heal service watches failed tasks and creates heal-tasks
when patterns indicate the failure is automatically addressable.
The /api/auto-heal/stats endpoint exposes counts and per-category
rates. compute_auto_heal_stats is the load-bearing pure function.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auto_heal_stats_endpoint_returns_200(client):
    response = client.get("/api/agent/auto-heal/stats")
    assert response.status_code == 200


def test_auto_heal_stats_returns_dict_shape(client):
    body = client.get("/api/agent/auto-heal/stats").json()
    assert isinstance(body, dict)


def test_compute_auto_heal_stats_with_no_failures():
    """Empty state — no failed tasks, no runners, no running tasks."""
    from app.services import auto_heal_service
    stats = auto_heal_service.compute_auto_heal_stats(
        [], task_counts={}, runner_rows=[], running_tasks=[]
    )
    assert isinstance(stats, dict)


def test_compute_auto_heal_stats_with_failed_tasks():
    """When there are failed tasks, the stats dict still parses cleanly."""
    from app.services import auto_heal_service
    failed = [
        {"id": "task-1", "status": "failed", "error": "timeout"},
        {"id": "task-2", "status": "failed", "error": "network"},
    ]
    stats = auto_heal_service.compute_auto_heal_stats(
        failed, task_counts={"failed": 2}, runner_rows=[], running_tasks=[]
    )
    assert isinstance(stats, dict)


def test_summarize_runner_gap_returns_dict():
    """summarize_runner_gap is a pure function called from compute_auto_heal_stats."""
    from app.services import auto_heal_service
    result = auto_heal_service.summarize_runner_gap(
        task_counts={}, runner_rows=[], running_tasks=[]
    )
    assert isinstance(result, dict)
    assert result["type"] == "runner_gap"


def test_summarize_runner_gap_detects_open_gap():
    """Running tasks present but no active runners → gap is open with high severity."""
    from app.services import auto_heal_service
    result = auto_heal_service.summarize_runner_gap(
        task_counts={"running": 3},
        runner_rows=[],
        running_tasks=[{"id": "t-1", "status": "running"}],
    )
    assert result["open"] is True
    assert result["severity"] == "high"
    assert result["running_task_count"] == 3
