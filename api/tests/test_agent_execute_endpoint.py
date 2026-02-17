from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_execute_endpoint_requires_token_when_configured(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTE_TOKEN", "secret")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Return ok",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_test", "response_id": "resp_test"},
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 403

        res2 = await client.post(
            f"/api/agent/tasks/{task['id']}/execute",
            headers={"X-Agent-Execute-Token": "secret"},
        )
        assert res2.status_code == 200


@pytest.mark.asyncio
async def test_execute_endpoint_completes_task_when_openrouter_is_stubbed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_test", "response_id": "resp_test"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Return ok",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        assert payload["status"] == "completed"
        assert payload["output"] == "ok"
