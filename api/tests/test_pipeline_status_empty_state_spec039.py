"""Spec 039: GET /api/agent/pipeline-status returns 200 with full contract in empty state."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


def _assert_pipeline_status_contract_200(payload: dict) -> None:
    assert "running" in payload
    assert "pending" in payload
    assert "recent_completed" in payload
    assert "attention" in payload
    assert "running_by_phase" in payload
    assert isinstance(payload["running"], list)
    assert isinstance(payload["pending"], list)
    assert isinstance(payload["recent_completed"], list)
    att = payload["attention"]
    assert isinstance(att, dict)
    assert "stuck" in att
    assert "repeated_failures" in att
    assert "low_success_rate" in att
    assert "flags" in att
    assert isinstance(att["flags"], list)
    rbp = payload["running_by_phase"]
    assert isinstance(rbp, dict)
    for phase in ("spec", "impl", "test", "review"):
        assert phase in rbp
        assert isinstance(rbp[phase], int)
        assert rbp[phase] >= 0


@pytest.mark.asyncio
async def test_pipeline_status_no_tasks_returns_200_empty_running_and_zero_phases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty store: 200, full contract, running=[], running_by_phase all zero."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract_200(payload)
    assert payload["running"] == []
    assert payload["running_by_phase"] == {"spec": 0, "impl": 0, "test": 0, "review": 0}


@pytest.mark.asyncio
async def test_pipeline_status_only_pending_tasks_no_running_returns_200_empty_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No running task (only pending): 200, running empty, contract keys present."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Queued work", "task_type": "impl"},
        )
        assert created.status_code == 201
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract_200(payload)
    assert payload["running"] == []
    assert len(payload["pending"]) >= 1


@pytest.mark.asyncio
async def test_pipeline_status_only_completed_tasks_returns_200_empty_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No running task (only completed): 200, running empty, phases zero."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        t = await client.post(
            "/api/agent/tasks",
            json={"direction": "Done", "task_type": "spec"},
        )
        assert t.status_code == 201
        tid = t.json()["id"]
        assert (
            await client.patch(
                f"/api/agent/tasks/{tid}",
                json={"status": "completed", "output": "x" * 100},
            )
        ).status_code == 200
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200
    payload = response.json()
    _assert_pipeline_status_contract_200(payload)
    assert payload["running"] == []
    assert payload["running_by_phase"] == {"spec": 0, "impl": 0, "test": 0, "review": 0}
