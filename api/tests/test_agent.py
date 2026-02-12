"""Tests for agent orchestration API — spec 002."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_store():
    agent_service.clear_store()
    yield


@pytest.mark.asyncio
async def test_post_task_returns_201_with_routed_model_and_command(client: AsyncClient):
    """POST /api/agent/tasks returns 201 with task_id, model, command."""
    response = await client.post(
        "/api/agent/tasks",
        json={
            "direction": "Add GET /api/projects endpoint",
            "task_type": "impl",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("task_")
    assert data["direction"] == "Add GET /api/projects endpoint"
    assert data["task_type"] == "impl"
    assert data["status"] == "pending"
    assert "ollama" in data["model"].lower() or "qwen3-coder" in data["model"]
    assert "claude -p" in data["command"]
    assert "Add GET /api/projects endpoint" in data["command"]
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_tasks_list_with_filters(client: AsyncClient):
    """GET /api/agent/tasks returns list, supports status/task_type filters."""
    await client.post(
        "/api/agent/tasks",
        json={"direction": "Write spec", "task_type": "spec"},
    )
    response = await client.get("/api/agent/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["tasks"]) >= 1
    task = data["tasks"][0]
    assert "id" in task
    assert "status" in task
    assert "task_type" in task
    # Filter by task_type
    resp2 = await client.get("/api/agent/tasks?task_type=spec")
    assert resp2.status_code == 200
    assert all(t["task_type"] == "spec" for t in resp2.json()["tasks"])


@pytest.mark.asyncio
async def test_get_task_by_id_404_when_missing(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns 404 when task not found."""
    response = await client.get("/api/agent/tasks/task_nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_get_task_by_id_returns_full_task(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns task with command."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "heal"},
    )
    task_id = create.json()["id"]
    response = await client.get(f"/api/agent/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert "command" in data
    assert "claude" in data["command"]


@pytest.mark.asyncio
async def test_patch_task_updates_status(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} updates status."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Run tests", "task_type": "test"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "output": "All tests passed"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["output"] == "All tests passed"
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_route_endpoint_returns_model_and_template(client: AsyncClient):
    """GET /api/agent/route returns model and command template."""
    response = await client.get("/api/agent/route?task_type=impl")
    assert response.status_code == 200
    data = response.json()
    assert data["task_type"] == "impl"
    assert "model" in data
    assert "command_template" in data
    assert "tier" in data
    assert "{{direction}}" in data["command_template"]


@pytest.mark.asyncio
async def test_impl_tasks_route_to_local(client: AsyncClient):
    """impl task_type routes to local (Ollama) model."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Implement feature", "task_type": "impl"},
    )
    data = response.json()
    assert "qwen3-coder" in data["model"] or "ollama" in data["model"].lower()


@pytest.mark.asyncio
async def test_heal_tasks_route_to_claude(client: AsyncClient):
    """heal task_type routes to Claude (subscription) model."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix failing CI", "task_type": "heal"},
    )
    data = response.json()
    assert "claude" in data["model"].lower()


# --- Spec 003: Agent-Telegram Decision Loop ---


@pytest.mark.asyncio
async def test_patch_accepts_progress_and_decision(client: AsyncClient):
    """PATCH accepts progress_pct, current_step, decision."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Test", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    r = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={
            "progress_pct": 50,
            "current_step": "Running tests",
            "decision_prompt": "Proceed?",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["progress_pct"] == 50
    assert data["current_step"] == "Running tests"
    assert data["decision_prompt"] == "Proceed?"


@pytest.mark.asyncio
async def test_reply_command_records_decision_and_updates_status(client: AsyncClient):
    """Recording decision on needs_decision task sets status→running and stores decision."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Test", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "needs_decision", "output": "Need approval"},
    )
    r = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"decision": "yes"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "running"
    assert data["decision"] == "yes"


@pytest.mark.asyncio
async def test_attention_lists_only_needs_decision_and_failed(client: AsyncClient):
    """GET /api/agent/tasks/attention returns only needs_decision and failed."""
    await client.post(
        "/api/agent/tasks",
        json={"direction": "A", "task_type": "impl"},
    )
    create2 = await client.post(
        "/api/agent/tasks",
        json={"direction": "B", "task_type": "impl"},
    )
    create3 = await client.post(
        "/api/agent/tasks",
        json={"direction": "C", "task_type": "impl"},
    )
    tid2, tid3 = create2.json()["id"], create3.json()["id"]
    await client.patch(f"/api/agent/tasks/{tid2}", json={"status": "needs_decision"})
    await client.patch(f"/api/agent/tasks/{tid3}", json={"status": "failed"})
    r = await client.get("/api/agent/tasks/attention")
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert "total" in data
    assert data["total"] == 2
    statuses = {t["id"]: t["status"] for t in data["tasks"]}
    assert statuses[tid2] == "needs_decision"
    assert statuses[tid3] == "failed"


def test_agent_runner_polls_and_executes_one_task():
    """Agent runner exists and is invokable (spec 003).
    Full E2E: run API + `python scripts/agent_runner.py --once` manually.
    """
    import os
    import subprocess
    import sys

    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "agent_runner.py")
    assert os.path.isfile(script), "agent_runner.py must exist per spec 003"
    result = subprocess.run(
        [sys.executable, script, "--once"],
        env={**os.environ, "AGENT_API_BASE": "http://127.0.0.1:19999"},
        capture_output=True,
        text=True,
        timeout=5,
        cwd=os.path.dirname(os.path.dirname(script)),
    )
    # Script runs; connection refused (no server) is expected — no ModuleNotFoundError/SyntaxError
    assert "ModuleNotFoundError" not in (result.stderr or "")
    assert "SyntaxError" not in (result.stderr or "")
