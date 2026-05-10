"""Tests for the attention-heuristics-pipeline-status spec
(specs/attention-heuristics-pipeline-status.md).

GET /api/agent/pipeline-status must always return 200 with a fixed
shape — running/pending/recent_completed lists, an attention object
with stuck/repeated_failures/low_success_rate booleans plus a flags
list, and a running_by_phase counter for the four phases. The
empty-state shape is contractual (per spec 039 and the agent_status
router's empty-state guarantee).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_pipeline_status_returns_200(client):
    response = client.get("/api/agent/pipeline-status")
    assert response.status_code == 200


def test_pipeline_status_carries_required_top_level_keys(client):
    body = client.get("/api/agent/pipeline-status").json()
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase"):
        assert key in body, f"missing top-level key {key!r}"


def test_pipeline_status_lists_are_arrays(client):
    body = client.get("/api/agent/pipeline-status").json()
    for key in ("running", "pending", "recent_completed"):
        assert isinstance(body[key], list), f"{key} should be a list"


def test_pipeline_status_attention_has_required_flags(client):
    body = client.get("/api/agent/pipeline-status").json()
    attention = body["attention"]
    assert isinstance(attention, dict)
    # Booleans the spec requires
    for flag in ("stuck", "repeated_failures", "low_success_rate"):
        assert flag in attention
        assert isinstance(attention[flag], bool)
    # The flags array
    assert "flags" in attention
    assert isinstance(attention["flags"], list)


def test_pipeline_status_running_by_phase_has_four_phases(client):
    body = client.get("/api/agent/pipeline-status").json()
    by_phase = body["running_by_phase"]
    assert isinstance(by_phase, dict)
    for phase in ("spec", "impl", "test", "review"):
        assert phase in by_phase
        assert isinstance(by_phase[phase], int)


def test_pipeline_status_empty_state_returns_200_not_404(client):
    """Per spec 039: even with no running task, this endpoint returns
    200 with the empty-state shape — never a 404."""
    response = client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    body = response.json()
    # Empty state: lists may be empty, but keys are present
    assert all(k in body for k in ("running", "pending", "attention"))
