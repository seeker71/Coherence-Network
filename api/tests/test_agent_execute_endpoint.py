from __future__ import annotations

import json
from uuid import uuid4

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


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_paid_provider_until_forced(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
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
            {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            {"elapsed_ms": 6, "provider_request_id": "req_paid", "response_id": "resp_paid"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess codex route",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/agent/tasks/{paid_task['id']}/execute")
        blocked = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert blocked.status_code == 200
        blocked_payload = blocked.json()
        assert blocked_payload["status"] == "failed"
        assert blocked_payload["output"] == (
            "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled."
        )

        forced = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        await client.post(
            f"/api/agent/tasks/{forced['id']}/execute?force_paid_providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{forced['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"

        events = await client.get("/api/runtime/events?limit=50")
        assert events.status_code == 200
        runtime_rows = events.json()
        tool_rows = [
            row
            for row in runtime_rows
            if str(row.get("metadata", {}).get("tracking_kind")).strip() == "agent_tool_call"
            and row.get("metadata", {}).get("task_id") == forced["id"]
        ]
        assert tool_rows, "Expected agent_tool_call runtime event"
        tool_metadata = tool_rows[0]["metadata"]
        assert tool_metadata["is_paid_provider"] is True
        assert int(tool_metadata["usage_prompt_tokens"]) == 3
        assert int(tool_metadata["usage_completion_tokens"]) == 2
        assert int(tool_metadata["usage_total_tokens"]) == 5


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_force_paid_query_numeric_and_alternate_keys(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
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
            {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            {"elapsed_ms": 4, "provider_request_id": "req_paid_num", "response_id": "resp_paid_num"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess codex route",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/agent/tasks/{paid_task['id']}/execute?force_paid_providers=1")
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"

        alt_task = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )
        await client.post(
            f"/api/agent/tasks/{alt_task['id']}/execute?force_allow_paid_providers=true"
        )
        alt_completed = await client.get(f"/api/agent/tasks/{alt_task['id']}")
        assert alt_completed.status_code == 200
        alt_completed_payload = alt_completed.json()
        assert alt_completed_payload["status"] == "completed"
        assert alt_completed_payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_hyphenated_force_paid_query_key(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
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
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            {"elapsed_ms": 7, "provider_request_id": "req_paid_dash", "response_id": "resp_paid_dash"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess hyphenated override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{paid_task['id']}/execute?force-paid-providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_paid_provider_when_usage_window_budget_exceeded(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("AGENT_ALLOW_PAID_PROVIDERS", "1")
    monkeypatch.setenv("PAID_TOOL_8H_LIMIT", "1")
    monkeypatch.setenv("PAID_TOOL_WINDOW_BUDGET_FRACTION", "0.333333")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seed = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 12.0,
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "is_paid_provider": True,
                    "runtime_cost_usd": 0.003,
                    "task_id": "seed_task",
                },
                "idea_id": "coherence-network-agent-pipeline",
            },
        )
        assert seed.status_code == 201

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route with budget cap",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        await client.post(f"/api/agent/tasks/{task['id']}/execute")
        blocked = await client.get(f"/api/agent/tasks/{task['id']}")
        assert blocked.status_code == 200
        blocked_payload = blocked.json()
        assert blocked_payload["status"] == "failed"
        assert blocked_payload["output"].startswith("Paid-provider usage blocked by window policy")

        friction = await client.get("/api/friction/events?status=open")
        assert friction.status_code == 200
        assert any(
            item.get("block_type") == "usage_window_budget_exceeded"
            and "Paid-provider usage blocked" in item.get("notes", "")
            for item in friction.json()
        )

        # The same task can also be re-executed with explicit override.
        forced = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route with budget override",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        monkeypatch.setattr(
            agent_execution_service,
            "chat_completion",
            lambda **_: (
                json.dumps({"confidence": 0.91, "estimated_value": 1.0}),
                {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                {"elapsed_ms": 4, "provider_request_id": "req_forced", "response_id": "resp_forced"},
            ),
        )

        forced_exec = await client.post(
            f"/api/agent/tasks/{forced['id']}/execute?force_paid_providers=true"
        )
        assert forced_exec.status_code == 200
        completed = await client.get(f"/api/agent/tasks/{forced['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"


@pytest.mark.asyncio
async def test_review_task_can_return_confidence_with_paid_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    expected_review_output = {
        "confidence": 0.93,
        "estimated_value": 15.0,
        "actual_value": 14.5,
    }
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps(expected_review_output),
            {"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20},
            {"elapsed_ms": 8, "provider_request_id": "req_review", "response_id": "resp_review"},
        ),
    )

    review_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Review the implementation and provide confidence + value estimates.",
            task_type=TaskType.REVIEW,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{review_task['id']}/execute?force_paid_providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{review_task['id']}")
        payload = completed.json()
        assert payload["status"] == "completed"
        parsed = json.loads(payload["output"])
        assert parsed["confidence"] == expected_review_output["confidence"]
        assert parsed["estimated_value"] == expected_review_output["estimated_value"]
        assert parsed["actual_value"] == expected_review_output["actual_value"]


@pytest.mark.asyncio
async def test_execute_task_fails_on_cost_limit_and_posts_friction(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("RUNTIME_COST_PER_SECOND", "1.0")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps({"confidence": 0.91, "estimated_value": 9.0, "actual_value": 7.0}),
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 6, "provider_request_id": "req_cost", "response_id": "resp_cost"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run quick task",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute?max_cost_usd=0.001")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        assert payload["status"] == "failed"
        assert "Execution budget exceeded" in payload["output"]

        friction = await client.get("/api/friction/events?status=open")
        assert friction.status_code == 200
        friction_rows = friction.json()
        assert any(
            row.get("block_type") == "cost_overrun" and row.get("notes", "").startswith("Execution budget exceeded")
            for row in friction_rows
        )


@pytest.mark.asyncio
async def test_execution_updates_cost_value_targets(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("RUNTIME_COST_PER_SECOND", "0.001")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'governance.db'}")
    monkeypatch.setenv("IDEA_REGISTRY_DATABASE_URL", f"sqlite:///{tmp_path / 'ideas.db'}")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    expected_idea_output = {
        "confidence": 0.85,
        "estimated_value": 42.0,
        "actual_value": 12.0,
        "estimated_cost": 3.0,
    }
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps(expected_idea_output),
            {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            {"elapsed_ms": 4, "provider_request_id": "req_val", "response_id": "resp_val"},
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas = await client.get("/api/ideas")
        assert ideas.status_code == 200
        idea_id = ideas.json()["ideas"][0]["id"]

        spec_payload = {
            "spec_id": f"spec-{uuid4().hex[:8]}",
            "title": "Execution attribution test spec",
            "summary": "Spec for validating execution attribution plumbing.",
            "potential_value": 30.0,
            "estimated_cost": 2.5,
            "actual_value": 0.0,
            "actual_cost": 0.0,
            "idea_id": idea_id,
        }
        created_spec = await client.post("/api/spec-registry", json=spec_payload)
        assert created_spec.status_code == 201
        spec_id = created_spec.json()["spec_id"]

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Update value records with metrics",
                task_type=TaskType.IMPL,
                context={
                    "executor": "openclaw",
                    "model_override": "openrouter/free",
                    "idea_id": idea_id,
                    "spec_id": spec_id,
                },
            )
        )

        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        completed = await client.get(f"/api/agent/tasks/{task['id']}")
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        parsed = json.loads(completed_payload["output"])
        assert parsed == expected_idea_output

        updated_idea = await client.get(f"/api/ideas/{idea_id}")
        assert updated_idea.status_code == 200
        idea_row = updated_idea.json()
        assert idea_row["actual_value"] == expected_idea_output["actual_value"]
        assert idea_row["confidence"] == expected_idea_output["confidence"]
        assert idea_row["potential_value"] == expected_idea_output["estimated_value"]
        assert idea_row["estimated_cost"] == expected_idea_output["estimated_cost"]

        updated_spec = await client.get(f"/api/spec-registry/{spec_id}")
        assert updated_spec.status_code == 200
        spec_row = updated_spec.json()
        assert spec_row["actual_value"] == expected_idea_output["actual_value"]
        assert spec_row["estimated_cost"] == expected_idea_output["estimated_cost"]
        assert spec_row["potential_value"] == expected_idea_output["estimated_value"]
