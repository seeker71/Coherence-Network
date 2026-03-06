from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service
from app.services.agent_routing import routing_config as routing_config_module


def test_create_task_supports_codex_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement codex executor support",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    assert task["model"].startswith("codex/")
    assert task["tier"] == "codex"
    assert task["command"].startswith("codex exec ")
    assert "--json" in task["command"]


def test_create_task_supports_openrouter_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement openrouter executor support",
            task_type=TaskType.IMPL,
            context={"executor": "openrouter"},
        )
    )

    assert task["model"].startswith("openrouter/")
    assert task["tier"] == "openrouter"
    assert task["command"].startswith("openrouter-exec ")


def test_create_task_supports_gemini_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("GEMINI_CLI_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("GEMINI_COMMAND_TEMPLATE", 'gemini -p "{{direction}}" --model {{model}} --format json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement gemini executor support",
            task_type=TaskType.IMPL,
            context={"executor": "gemini"},
        )
    )

    assert task["model"].startswith("gemini/")
    assert task["tier"] == "gemini"
    assert task["command"].startswith("gemini -p ")
    context = task.get("context") or {}
    assert context.get("executor") == "gemini"


def test_create_task_codex_default_template_includes_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.delenv("CODEX_COMMAND_TEMPLATE", raising=False)
    monkeypatch.delenv("OPENCLAW_COMMAND_TEMPLATE", raising=False)
    # Patch the module command_templates uses (routing_config), not routing_service
    monkeypatch.setattr(
        routing_config_module,
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
            context={"executor": "codex"},
        )
    )

    assert task["model"] == "codex/gpt-5.3-codex-spark"
    assert task["command"].startswith("codex exec ")
    assert "--model gpt-5.3-codex-spark" in task["command"]
    assert "--model openrouter/free" not in task["command"]
    assert "--skip-git-repo-check" in task["command"]
    assert "--worktree" not in task["command"]
    assert "--reasoning-effort" not in task["command"]


def test_create_task_codex_default_template_avoids_unsupported_reasoning_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.delenv("CODEX_COMMAND_TEMPLATE", raising=False)
    monkeypatch.setattr(
        agent_service.routing_service,
        "OPENCLAW_MODEL_BY_TYPE",
        {task_type: "gpt-5-codex" for task_type in TaskType},
    )
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Validate codex command compatibility flags",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    assert task["command"].startswith("codex exec ")
    assert "--worktree" not in task["command"]
    assert "--skip-git-repo-check" in task["command"]
    assert "--reasoning-effort" not in task["command"]


def test_create_task_codex_model_override_adds_model_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.1-codex")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Force openrouter free model",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "openrouter/free"},
        )
    )

    assert "--model openrouter/free" in task["command"]
    assert task["model"] == "openrouter/free"
    assert task["command"].startswith("openrouter-exec ")
    assert (task.get("context") or {}).get("executor") == "openrouter"


def test_create_task_openrouter_override_forces_free_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Enforce openrouter free model policy",
            task_type=TaskType.IMPL,
            context={"executor": "openrouter", "model_override": "openrouter/anthropic/claude-sonnet-4"},
        )
    )

    assert task["model"] == "openrouter/free"
    assert "--model openrouter/free" in task["command"]
    policy = (task.get("context") or {}).get("model_override_policy") or {}
    assert policy.get("kind") == "openrouter_free_only"
    assert policy.get("applied_model_override") == "openrouter/free"


def test_create_task_codex_uses_model_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.delenv("CODEX_COMMAND_TEMPLATE", raising=False)
    monkeypatch.delenv("OPENCLAW_COMMAND_TEMPLATE", raising=False)
    # Mutate the shared dict so codex uses a specific model id (no aliasing; id used as-is)
    saved = {t: routing_config_module.OPENCLAW_MODEL_BY_TYPE[t] for t in TaskType}
    try:
        for task_type in TaskType:
            routing_config_module.OPENCLAW_MODEL_BY_TYPE[task_type] = "gpt-5.3-codex-spark"
        agent_service._store.clear()
        agent_service._store_loaded = False
        agent_service._store_loaded_path = None

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Codex uses model from config",
                task_type=TaskType.IMPL,
                context={"executor": "codex"},
            )
        )

        assert task["model"] == "codex/gpt-5.3-codex-spark"
        assert "--model gpt-5.3-codex-spark" in task["command"]
    finally:
        for task_type in TaskType:
            routing_config_module.OPENCLAW_MODEL_BY_TYPE[task_type] = saved[task_type]


def test_create_task_codex_model_override_used_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Model override used as-is (no aliasing)",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex"},
        )
    )

    assert "--model gpt-5.3-codex" in task["command"]
    assert task["model"] == "codex/gpt-5.3-codex"


def test_create_task_codex_model_override_another_id_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Model override used as-is",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.1-codex"},
        )
    )

    assert "--model gpt-5.1-codex" in task["command"]
    assert task["model"] == "codex/gpt-5.1-codex"


def test_create_task_codex_model_override_openai_prefix_normalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5-codex")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize OpenAI-prefixed model for codex",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "openai/gpt-4o-mini"},
        )
    )

    assert "--model gpt-4o-mini" in task["command"]
    assert "--model openai/gpt-4o-mini" not in task["command"]
    assert task["model"] == "codex/gpt-4o-mini"


def test_create_task_codex_defaults_runner_codex_auth_mode_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5-codex")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.delenv("AGENT_TASK_DEFAULT_RUNNER_CODEX_AUTH_MODE", raising=False)
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Default to oauth runner auth mode",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    assert task["context"]["runner_codex_auth_mode"] == "oauth"


def test_create_task_cursor_defaults_runner_cursor_auth_mode_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_DEFAULT", "cursor")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Default cursor auth mode",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    assert task["context"]["runner_cursor_auth_mode"] == "oauth"


def test_create_task_codex_forces_oauth_runner_codex_auth_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5-codex")
    monkeypatch.setenv("CODEX_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    monkeypatch.setenv("AGENT_TASK_DEFAULT_RUNNER_CODEX_AUTH_MODE", "api_key")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Force oauth runner auth mode",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "runner_codex_auth_mode": "api_key"},
        )
    )

    assert task["context"]["runner_codex_auth_mode"] == "oauth"


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_codex_executor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "codex"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "codex"
        assert payload["tier"] == "codex"
        assert str(payload["model"]).startswith("codex/")
        assert payload["provider"] in {"openrouter", "openai-codex"}
        assert isinstance(payload["is_paid_provider"], bool)
        template = str(payload["command_template"])
        assert "{{direction}}" in template
        assert template.startswith("codex exec ")


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_openrouter_executor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "openrouter"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "openrouter"
        assert payload["tier"] == "openrouter"
        assert str(payload["model"]).startswith("openrouter/")
        assert payload["provider"] == "openrouter"
        assert isinstance(payload["is_paid_provider"], bool)
        template = str(payload["command_template"])
        assert "{{direction}}" in template
        assert template.startswith("openrouter-exec ")


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_gemini_executor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "gemini"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "gemini"
        assert payload["tier"] == "gemini"
        assert str(payload["model"]).startswith("gemini/")
        assert payload["provider"] == "gemini"
        assert isinstance(payload["is_paid_provider"], bool)
        template = str(payload["command_template"])
        assert "{{direction}}" in template
        assert template.startswith("gemini ")
        assert "--sandbox=false" in template


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_cursor_executor_and_disables_sandbox() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "cursor"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "cursor"
        assert payload["tier"] == "cursor"
        assert str(payload["model"]).startswith("cursor/")
        assert payload["provider"] == "cursor"
        assert isinstance(payload["is_paid_provider"], bool)
        template = str(payload["command_template"])
        assert "{{direction}}" in template
        assert template.startswith("agent ")
        assert "--sandbox disabled" in template
