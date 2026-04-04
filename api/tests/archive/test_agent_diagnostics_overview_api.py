from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import health as health_router
from app.models.agent import AgentRunnerHeartbeat, AgentTaskCreate
from app.models.friction import FrictionEvent
from app.services import persistence_contract_service
from app.models.runtime import RuntimeEventCreate
from app.services import (
    agent_runner_registry_service,
    agent_service,
    friction_service,
    runtime_service,
)


@pytest.mark.asyncio
async def test_agent_diagnostics_overview_returns_redacted_config_and_live_summaries(
    tmp_path,
    set_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs_dir = tmp_path / "task-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    set_config("database", "url", "postgresql://coherence:secret@db/coherence")
    set_config("auth", "api_key", "public-api-secret")
    set_config("auth", "admin_key", "admin-secret-value")
    set_config("agent_executor", "execute_token", "execute-secret")
    set_config("agent_executor", "execute_token_allow_unauth", False)
    set_config("agent_tasks", "task_log_dir", str(logs_dir))
    set_config("runtime", "events_path", str(tmp_path / "runtime-events.json"))
    set_config("friction", "events_path", str(tmp_path / "friction-events.json"))
    set_config("live_updates", "poll_ms", 45000)
    set_config("runtime_beacon", "sample_rate", 0.4)
    set_config("cli", "provider", "codex")
    set_config("cli", "active_task_id", "task_demo")
    monkeypatch.setattr(
        health_router,
        "health",
        lambda: health_router.HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp="2026-04-02T00:00:00Z",
            started_at="2026-04-02T00:00:00Z",
            uptime_seconds=60,
            uptime_human="1m 0s",
            deployed_sha="abc123",
            deployed_sha_source="config",
            integrity_compromised=False,
            schema_ok=True,
            opencode_enabled=True,
        ),
    )
    monkeypatch.setattr(
        persistence_contract_service,
        "evaluate",
        lambda _app: {"pass_contract": True, "failures": [], "required": True},
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="diagnostics smoke " * 120,
            task_type="impl",
            context={
                "files_allowed": [f"api/app/file_{idx}.py" for idx in range(15)],
                "commands": [f"pytest tests/test_{idx}.py" for idx in range(7)],
            },
        )
    )
    (logs_dir / f"task_{task['id']}.log").write_text("runner booted\nprocessing diagnostics", encoding="utf-8")

    agent_runner_registry_service.heartbeat_runner(
        runner_id="runner-test",
        status="running",
        lease_seconds=60,
        host="localhost",
        pid=123,
        version="1.0",
        active_task_id=task["id"],
        active_run_id="run-1",
        last_error="",
        capabilities={"executor": "codex"},
        metadata={"branch": "codex/test"},
    )
    runtime_service.record_event(
        RuntimeEventCreate(
            source="api",
            endpoint="/api/agent/diagnostics/overview",
            method="GET",
            status_code=200,
            runtime_ms=42.0,
        )
    )
    friction_service.append_event(
        FrictionEvent(
            id="friction_test",
            timestamp=datetime.now(timezone.utc),
            stage="diagnostics",
            block_type="visibility_gap",
            severity="medium",
            owner="api",
            unblock_condition="Add summary UI",
            energy_loss_estimate=1.2,
            cost_of_delay=0.5,
            status="open",
            notes="Diagnostics console not visible enough",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/agent/diagnostics/overview",
            headers={"X-Admin-Key": "admin-secret-value"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["database"]["backend"] == "postgresql"
    assert payload["config"]["database"]["url"] == "postgresql://coherence:***@db/coherence"
    assert payload["config"]["auth"]["api_key"]["configured"] is True
    assert payload["config"]["auth"]["api_key"]["preview"] != "public-api-secret"
    assert payload["config"]["web_controls"]["live_updates_poll_ms"] == 45000
    assert payload["config"]["web_controls"]["runtime_beacon_sample_rate"] == 0.4
    assert payload["config"]["cli_defaults"]["provider"] == "codex"
    assert payload["config"]["cli_defaults"]["active_task_id"] == "task_demo"
    assert payload["tasks"]["counts"]["total"] >= 1
    assert payload["tasks"]["context_budget"]["flagged_tasks"] >= 1
    assert any(item["id"] == "broad_file_scope" for item in payload["tasks"]["context_budget"]["top_flags"])
    assert payload["tasks"]["log_previews"][0]["source"] == "file"
    assert "processing diagnostics" in payload["tasks"]["log_previews"][0]["preview"]
    assert payload["tasks"]["anomalies"] == []
    assert payload["runners"]["total"] >= 1
    assert payload["runtime"]["recent_events"][0]["endpoint"] == "/api/agent/diagnostics/overview"
    assert payload["friction"]["summary"]["total_events"] >= 1


@pytest.mark.asyncio
async def test_agent_diagnostics_overview_flags_running_tasks_without_active_runners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import agent_diagnostics_routes

    monkeypatch.setattr(agent_diagnostics_routes.agent_service, "get_task_count", lambda: {"total": 4, "by_status": {"running": 2}})
    monkeypatch.setattr(
        agent_diagnostics_routes.agent_service,
        "list_tasks",
        lambda limit=8, offset=0: (
            [
                {"id": "task-running-1", "status": "running"},
                {"id": "task-running-2", "status": "running"},
            ],
            2,
            0,
        ),
    )
    monkeypatch.setattr(agent_diagnostics_routes.agent_runner_registry_service, "list_runners", lambda **_kwargs: [])
    monkeypatch.setattr(agent_diagnostics_routes.runtime_service, "list_events", lambda limit=12: [])
    monkeypatch.setattr(agent_diagnostics_routes.friction_service, "load_events", lambda: ([], 0))
    monkeypatch.setattr(
        agent_diagnostics_routes.friction_service,
        "summarize",
        lambda _events, window_days=7: {"total_events": 0},
    )
    monkeypatch.setattr(
        agent_diagnostics_routes.runtime_service,
        "summarize_endpoint_attention",
        lambda **_kwargs: type("Result", (), {"model_dump": lambda self, mode="json": []})(),
    )
    monkeypatch.setattr(
        agent_diagnostics_routes.agent_execution_hooks,
        "summarize_lifecycle_events",
        lambda **_kwargs: {"counts": {}, "events": []},
    )
    monkeypatch.setattr(
        agent_diagnostics_routes.health_router,
        "health",
        lambda: health_router.HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp="2026-04-02T00:00:00Z",
            started_at="2026-04-02T00:00:00Z",
            uptime_seconds=60,
            uptime_human="1m 0s",
            deployed_sha="abc123",
            deployed_sha_source="config",
            integrity_compromised=False,
            schema_ok=True,
            opencode_enabled=True,
        ),
    )
    monkeypatch.setattr(
        agent_diagnostics_routes.persistence_contract_service,
        "evaluate",
        lambda _app: {"pass_contract": True, "failures": [], "required": True},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/agent/diagnostics/overview",
            headers={"X-Admin-Key": "dev-admin"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tasks"]["anomalies"] == [
        {
            "type": "runner_gap",
            "open": True,
            "severity": "high",
            "summary": "2 running tasks but no active runners are registered.",
            "running_task_count": 2,
            "online_runner_count": 0,
            "active_runner_count": 0,
            "sampled_orphaned_task_ids": ["task-running-1", "task-running-2"],
        }
    ]
    assert payload["tasks"]["context_budget"]["task_count"] == 2
