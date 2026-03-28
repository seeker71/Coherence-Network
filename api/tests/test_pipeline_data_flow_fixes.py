"""Tests for Pipeline Data Flow Fixes (idea slug: pipeline-data-flow-fixes).

Acceptance criteria exercised here (aligned with specs/161-node-task-visibility.md
and the live `/pipeline` dashboard data sources):

- `GET /api/agent/tasks/active` and `GET /api/agent/tasks/activity` return JSON
  arrays (never a wrapped object), so clients can iterate without defensive
  object branches.
- Active-task events missing `idea_id` in the activity payload are enriched from
  the agent task store (`context.idea_id`), so the pipeline UI can show idea
  context without broken data flow from runner → API → web.
- `GET /api/pipeline/summary` stays available (HTTP 200) when the runner loop
  reports `running: false`, while `GET /api/pipeline/status` correctly surfaces
  idle as 503 — summary must not inherit the status endpoint's error semantics.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import task_activity_service as tas


@pytest.fixture(autouse=True)
def _clear_task_activity_buffers() -> None:
    """Isolate tests that touch the in-memory activity ring buffer."""
    tas._ACTIVITY_LOG.clear()
    tas._TASK_STREAMS.clear()
    tas._ACTIVE_TASKS.clear()
    yield
    tas._ACTIVITY_LOG.clear()
    tas._TASK_STREAMS.clear()
    tas._ACTIVE_TASKS.clear()


def test_get_active_tasks_enriches_missing_idea_id_from_task_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runner events without idea_id still expose idea_id after store lookup."""
    from app.services import agent_service

    task_id = "task-pipeline-flow-1"
    tas.log_activity(
        task_id,
        "executing",
        {
            "node_id": "node-a",
            "node_name": "worker-1",
            "provider": "claude",
        },
    )

    def _fake_get_task(tid: str):
        if tid != task_id:
            return None
        return {"id": tid, "context": {"idea_id": "idea-from-store"}}

    monkeypatch.setattr(agent_service, "get_task", _fake_get_task)

    active = tas.get_active_tasks()
    assert len(active) == 1
    assert active[0]["data"]["idea_id"] == "idea-from-store"


def test_get_active_tasks_preserves_idea_id_when_already_on_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the activity payload already carries idea_id, enrichment does not overwrite."""
    from app.services import agent_service

    task_id = "task-pipeline-flow-2"
    tas.log_activity(
        task_id,
        "executing",
        {
            "node_id": "node-a",
            "node_name": "worker-1",
            "provider": "claude",
            "idea_id": "idea-on-event",
        },
    )

    def _fake_get_task(tid: str):
        if tid != task_id:
            return None
        return {"id": tid, "context": {"idea_id": "should-not-win"}}

    monkeypatch.setattr(agent_service, "get_task", _fake_get_task)

    active = tas.get_active_tasks()
    assert active[0]["data"]["idea_id"] == "idea-on-event"


@pytest.mark.asyncio
async def test_agent_tasks_active_returns_json_array() -> None:
    """Pipeline clients expect a top-level JSON array from /api/agent/tasks/active."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/tasks/active")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_agent_tasks_activity_returns_json_array() -> None:
    """Activity feed must deserialize as a list for the dashboard stream."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/tasks/activity", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_pipeline_summary_200_while_pipeline_status_503_when_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summary stays warm for dashboards; status remains strict about runner idle."""
    monkeypatch.setattr(
        "app.services.pipeline_service.get_status",
        lambda: {
            "running": False,
            "uptime_seconds": 0,
            "current_idea_id": None,
            "cycle_count": 0,
            "ideas_advanced": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_cycle_at": None,
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status_resp = await client.get("/api/pipeline/status")
        summary_resp = await client.get("/api/pipeline/summary")

    assert status_resp.status_code == 503
    assert summary_resp.status_code == 200
    assert summary_resp.json()["running"] is False
