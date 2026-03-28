"""Acceptance tests for spec 039: GET /api/agent/pipeline-status returns 200 in empty state."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


def _assert_pipeline_status_contract(payload: dict) -> None:
    assert "running" in payload
    assert "pending" in payload
    assert "recent_completed" in payload
    assert "attention" in payload
    assert "running_by_phase" in payload
    assert isinstance(payload["running"], list)
    attention = payload["attention"]
    assert "stuck" in attention
    assert "repeated_failures" in attention
    assert "low_success_rate" in attention
    assert "flags" in attention
    rb = payload["running_by_phase"]
    for phase in ("spec", "impl", "test", "review"):
        assert phase in rb
        assert isinstance(rb[phase], int)


@pytest.mark.asyncio
async def test_pipeline_status_returns_200_when_store_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """No tasks at all: 200, full contract, running empty, phases zero."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract(payload)
    assert payload["running"] == []
    assert payload["running_by_phase"] == {"spec": 0, "impl": 0, "test": 0, "review": 0}


@pytest.mark.asyncio
async def test_pipeline_status_returns_200_when_no_running_only_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only terminal tasks (completed), none running or pending: 200, running empty, phases zero."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    long_output = "x" * 250

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Done task", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        assert (
            await client.patch(
                f"/api/agent/tasks/{task_id}",
                json={"status": "running", "worker_id": "manual-test"},
            )
        ).status_code == 200
        assert (
            await client.patch(
                f"/api/agent/tasks/{task_id}",
                json={"status": "completed", "output": long_output},
            )
        ).status_code == 200

        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract(payload)
    assert payload["running"] == []
    assert payload["running_by_phase"] == {"spec": 0, "impl": 0, "test": 0, "review": 0}


@pytest.mark.asyncio
async def test_pipeline_status_returns_200_when_no_running_pending_and_completed_mix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No running task but pending + completed: still 200; running list empty; contract keys present."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    long_output = "y" * 250

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pending = await client.post(
            "/api/agent/tasks",
            json={"direction": "Queued spec", "task_type": "spec"},
        )
        assert pending.status_code == 201

        done = await client.post(
            "/api/agent/tasks",
            json={"direction": "Finished impl", "task_type": "impl"},
        )
        assert done.status_code == 201
        done_id = done.json()["id"]
        assert (
            await client.patch(
                f"/api/agent/tasks/{done_id}",
                json={"status": "running", "worker_id": "manual-test"},
            )
        ).status_code == 200
        assert (
            await client.patch(
                f"/api/agent/tasks/{done_id}",
                json={"status": "completed", "output": long_output},
            )
        ).status_code == 200

        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract(payload)
    assert payload["running"] == []
    assert payload["pending"], "expected a pending task in store"
    assert payload["running_by_phase"]["spec"] >= 1
