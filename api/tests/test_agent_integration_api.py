"""Tests for the agent-orchestration-api spec
(specs/agent-orchestration-api.md).

Covers the public agent task endpoints — POST /api/agent/tasks
(submit), GET /api/agent/tasks (list with pagination + filters),
DELETE /api/agent/tasks (queue clear with confirmation), and the
attention/count endpoints. Tasks are created as pending and picked
up by federation node runners; no server-side auto-execution.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_task_returns_201(client):
    payload = {
        "task_type": "spec",
        "direction": "Write a spec for testing the orchestration API",
    }
    response = client.post("/api/agent/tasks", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["task_type"] == "spec"


def test_create_task_rejects_empty_direction(client):
    payload = {"task_type": "spec", "direction": ""}
    response = client.post("/api/agent/tasks", json=payload)
    assert response.status_code == 422


def test_create_task_rejects_invalid_task_type(client):
    payload = {"task_type": "not-a-real-type", "direction": "test"}
    response = client.post("/api/agent/tasks", json=payload)
    assert response.status_code == 422


def test_list_tasks_returns_paginated_shape(client):
    response = client.get("/api/agent/tasks", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert "tasks" in body
    assert "total" in body
    assert isinstance(body["tasks"], list)


def test_list_tasks_supports_status_filter(client):
    response = client.get("/api/agent/tasks", params={"status": "pending"})
    assert response.status_code == 200


def test_list_tasks_rejects_invalid_status(client):
    response = client.get("/api/agent/tasks", params={"status": "not-a-status"})
    assert response.status_code == 422


def test_list_tasks_rejects_oversize_limit(client):
    response = client.get("/api/agent/tasks", params={"limit": 9999})
    assert response.status_code == 422


def test_clear_tasks_requires_confirm(client):
    """DELETE /api/agent/tasks requires ?confirm=clear to avoid accidental wipe."""
    response = client.delete("/api/agent/tasks")
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "confirm" in detail.lower()


def test_tasks_count_endpoint_returns_200(client):
    response = client.get("/api/agent/tasks/count")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)


def test_tasks_attention_endpoint_returns_list_shape(client):
    response = client.get("/api/agent/tasks/attention")
    assert response.status_code == 200
    body = response.json()
    # Attention list contract: returns task list with output/decision context
    assert isinstance(body, (list, dict))
