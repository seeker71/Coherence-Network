from __future__ import annotations

from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app
from app.services import runtime_exerciser_service


@pytest.mark.asyncio
async def test_auto_heal_stats_route_handles_list_tasks_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import agent_auto_heal_routes

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        agent_auto_heal_routes,
        "list_tasks",
        lambda: (
            [
                {"id": "task_failed", "status": "failed", "output": "boom"},
                {"id": "task_running", "status": "running", "output": ""},
                {"id": "task_ok", "status": "completed", "output": ""},
            ],
            3,
            0,
        ),
    )
    monkeypatch.setattr(agent_auto_heal_routes.agent_service, "get_task_count", lambda: {"total": 3, "by_status": {"running": 1, "failed": 1}})
    monkeypatch.setattr(agent_auto_heal_routes.agent_runner_registry_service, "list_runners", lambda **_kwargs: [])

    def _fake_stats(
        failed: list[dict],
        *,
        task_counts: dict | None = None,
        runner_rows: list[dict] | None = None,
        running_tasks: list[dict] | None = None,
    ) -> dict:
        captured["failed"] = failed
        captured["task_counts"] = task_counts
        captured["runner_rows"] = runner_rows
        captured["running_tasks"] = running_tasks
        return {"failed_count": len(failed)}

    monkeypatch.setattr(agent_auto_heal_routes.auto_heal_service, "compute_auto_heal_stats", _fake_stats)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/auto-heal/stats")

    assert response.status_code == 200
    assert response.json() == {"failed_count": 1}
    assert captured["failed"] == [{"id": "task_failed", "status": "failed", "output": "boom"}]
    assert captured["task_counts"] == {"total": 3, "by_status": {"running": 1, "failed": 1}}
    assert captured["runner_rows"] == []
    assert captured["running_tasks"] == [{"id": "task_running", "status": "running", "output": ""}]


@pytest.mark.asyncio
async def test_diagnostics_completeness_route_handles_list_tasks_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import agent_diagnostics_routes

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        agent_diagnostics_routes,
        "list_tasks",
        lambda: (
            [
                {"id": "task_failed", "status": "failed", "error_summary": "boom", "error_category": "unknown"},
                {"id": "task_ok", "status": "completed"},
            ],
            2,
            0,
        ),
    )

    def _fake_completeness(tasks: list[dict]) -> dict:
        captured["tasks"] = tasks
        return {"total_failed": 1, "with_diagnostics": 1, "missing_pct": 0.0, "by_category": {"unknown": 1}}

    monkeypatch.setattr(
        agent_diagnostics_routes.failed_task_diagnostics_service,
        "compute_diagnostics_completeness",
        _fake_completeness,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/diagnostics-completeness")

    assert response.status_code == 200
    assert response.json()["total_failed"] == 1
    assert captured["tasks"] == [
        {"id": "task_failed", "status": "failed", "error_summary": "boom", "error_category": "unknown"},
        {"id": "task_ok", "status": "completed"},
    ]


def test_materialize_run_state_path_skips_when_no_real_run_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_run_state_service, agent_service

    monkeypatch.setattr(
        agent_service,
        "list_tasks",
        lambda limit=1: ([{"id": "task_missing"}], 1, 0),
    )
    monkeypatch.setattr(agent_run_state_service, "get_run_state", lambda task_id: None)

    assert runtime_exerciser_service._materialize_route_path("/api/agent/run-state/{task_id}") is None


def test_materialize_run_state_path_uses_real_run_state_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_run_state_service, agent_service

    monkeypatch.setattr(
        agent_service,
        "list_tasks",
        lambda limit=1: ([{"id": "task_with_state"}, {"id": "task_missing"}], 2, 0),
    )
    monkeypatch.setattr(
        agent_run_state_service,
        "get_run_state",
        lambda task_id: {"task_id": task_id, "status": "running"} if task_id == "task_with_state" else None,
    )

    assert (
        runtime_exerciser_service._materialize_route_path("/api/agent/run-state/{task_id}")
        == "/api/agent/run-state/task_with_state"
    )
