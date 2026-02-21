from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service


def test_create_task_supports_openclaw_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "openclaw/test-model")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'openclaw run "{{direction}}" --model {{model}} --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement openclaw executor support",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )

    assert task["model"].startswith("openclaw/")
    assert task["tier"] == "openclaw"
    assert task["command"].startswith("openclaw run ")
    assert "--json" in task["command"]


def test_create_task_supports_clawwork_executor_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "openclaw/test-model")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'openclaw run "{{direction}}" --model {{model}} --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement clawwork alias support",
            task_type=TaskType.IMPL,
            context={"executor": "clawwork"},
        )
    )

    assert task["model"].startswith("openclaw/")
    assert task["tier"] == "openclaw"
    assert "--json" in task["command"]
    context = task.get("context") or {}
    assert context.get("executor") == "openclaw"


def test_create_task_supports_codex_executor_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "openclaw/test-model")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --model {{model}} --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement codex alias support",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    assert task["model"].startswith("openclaw/")
    assert task["tier"] == "openclaw"
    assert task["command"].startswith("codex exec ")
    context = task.get("context") or {}
    assert context.get("executor") == "openclaw"


def test_create_task_openclaw_default_template_includes_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.delenv("OPENCLAW_COMMAND_TEMPLATE", raising=False)
    monkeypatch.setattr(
        agent_service.routing_service,
        "OPENCLAW_MODEL_BY_TYPE",
        {task_type: "openrouter/free" for task_type in TaskType},
    )
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Validate free-model command wiring",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )

    assert task["model"] == "openclaw/openrouter/free"
    assert "--model openrouter/free" in task["command"]


def test_create_task_openclaw_model_override_adds_model_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "gpt-5.1-codex")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Force openrouter free model",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    assert "--model openrouter/free" in task["command"]
    assert task["model"] == "openclaw/openrouter/free"


def test_create_task_openclaw_default_model_normalizes_legacy_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.delenv("OPENCLAW_COMMAND_TEMPLATE", raising=False)
    monkeypatch.setattr(
        agent_service.routing_service,
        "OPENCLAW_MODEL_BY_TYPE",
        {task_type: "gtp-5.3-codex" for task_type in TaskType},
    )
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize legacy model alias",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )

    assert task["model"] == "openclaw/gpt-5.3-codex"
    assert "--model gpt-5.3-codex" in task["command"]


def test_create_task_openclaw_model_override_normalizes_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "gpt-5-codex")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize model override typo alias",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gtp-5.3-codex"},
        )
    )

    assert "--model gpt-5.3-codex" in task["command"]
    assert task["model"] == "openclaw/gpt-5.3-codex"


def test_create_task_openclaw_model_override_normalizes_alias_with_partial_env_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_MODEL_ALIAS_MAP", "gpt-5.3-codex:gpt-5-codex")
    monkeypatch.setenv("OPENCLAW_MODEL", "gpt-5-codex")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize typo alias even when env map is partial",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gtp-5.3-codex"},
        )
    )

    assert "--model gpt-5.3-codex" in task["command"]
    assert "--model gtp-5.3-codex" not in task["command"]
    assert task["model"] == "openclaw/gpt-5.3-codex"


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_openclaw_executor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "openclaw"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "openclaw"
        assert payload["tier"] == "openclaw"
        assert str(payload["model"]).startswith("openclaw/")
        assert payload["provider"] in {"openrouter", "openclaw", "openai-codex"}
        assert isinstance(payload["is_paid_provider"], bool)
        template = str(payload["command_template"])
        assert "{{direction}}" in template
        assert template.startswith("openclaw ") or template.startswith("codex exec ")


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_clawwork_executor_alias() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "clawwork"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "openclaw"
        assert payload["tier"] == "openclaw"
        assert str(payload["model"]).startswith("openclaw/")
