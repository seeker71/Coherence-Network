"""Tests for the coherence-network-agent-pipeline spec
(specs/coherence-network-agent-pipeline.md) — router-level surface.

Sister file to test_agent_pipeline.py (state-machine tests). This
covers the GET /api/pipeline/pulse endpoint that wraps
pipeline_pulse_service and the GET /api/agent/pipeline-status
contract that tooling depends on.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_pipeline_pulse_returns_200(client):
    response = client.get("/api/pipeline/pulse")
    assert response.status_code == 200


def test_pipeline_pulse_returns_dict(client):
    body = client.get("/api/pipeline/pulse").json()
    assert isinstance(body, dict)


def test_pipeline_pulse_accepts_window_days(client):
    """Pulse computation accepts a configurable window."""
    response = client.get("/api/pipeline/pulse", params={"window_days": 30})
    assert response.status_code == 200


def test_pipeline_pulse_rejects_window_outside_bounds(client):
    """window_days has Query(ge=1, le=90); out-of-range → 422."""
    assert client.get("/api/pipeline/pulse", params={"window_days": 0}).status_code == 422
    assert client.get("/api/pipeline/pulse", params={"window_days": 100}).status_code == 422


def test_pipeline_pulse_accepts_task_limit(client):
    """task_limit is also bounded."""
    response = client.get("/api/pipeline/pulse", params={"task_limit": 100})
    assert response.status_code == 200


def test_pipeline_status_endpoint_returns_200(client):
    """The /api/agent/pipeline-status contract — tested in
    test_agent_pipeline_status_diagnostics_api.py for shape; here we
    just confirm it's reachable from the pipeline-router perspective."""
    response = client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
