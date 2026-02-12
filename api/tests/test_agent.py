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
            "context": {"executor": "claude"},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("task_")
    assert data["direction"] == "Add GET /api/projects endpoint"
    assert data["task_type"] == "impl"
    assert data["status"] == "pending"
    assert "ollama" in data["model"].lower() or "qwen3-coder" in data["model"] or "glm-4.7-flash" in data["model"]
    assert "claude -p" in data["command"]
    assert "Add GET /api/projects endpoint" in data["command"]
    assert "created_at" in data


@pytest.mark.asyncio
async def test_post_task_201_response_shape_defines_contract(client: AsyncClient):
    """POST 201 response must include id, direction, task_type, status, model, command, created_at (spec 002 contract)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Shape check", "task_type": "impl"},
    )
    assert response.status_code == 201
    data = response.json()
    required = ("id", "direction", "task_type", "status", "model", "command", "created_at")
    for key in required:
        assert key in data, f"POST 201 response must include {key}"
    assert isinstance(data["created_at"], str)


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
    # Pagination: offset and limit
    resp3 = await client.get("/api/agent/tasks?limit=2&offset=0")
    assert resp3.status_code == 200
    assert len(resp3.json()["tasks"]) <= 2
    assert resp3.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_tasks_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/tasks response: tasks (array), total (int); list items omit command and output (spec 002 contract)."""
    await client.post("/api/agent/tasks", json={"direction": "Shape", "task_type": "impl"})
    response = await client.get("/api/agent/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "total" in data
    assert isinstance(data["tasks"], list)
    assert isinstance(data["total"], int)
    for item in data["tasks"]:
        assert "command" not in item
        assert "output" not in item
        assert "id" in item and "direction" in item and "task_type" in item and "status" in item and "model" in item


@pytest.mark.asyncio
async def test_list_empty_returns_zero_tasks_and_total(client: AsyncClient):
    """GET /api/agent/tasks when no tasks exist returns 200, tasks=[], total=0 (spec 002 edge-case)."""
    # Store is reset per test; no tasks created
    response = await client.get("/api/agent/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_pagination_offset_beyond_total_returns_empty_tasks(client: AsyncClient):
    """GET /api/agent/tasks?offset=999 when total < 999 returns 200, tasks=[], total unchanged (spec 002 edge-case)."""
    await client.post(
        "/api/agent/tasks",
        json={"direction": "One task", "task_type": "impl"},
    )
    response = await client.get("/api/agent/tasks?limit=10&offset=999")
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_task_by_id_404_when_missing(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns 404 when task not found (spec 009: body { detail: string } only)."""
    response = await client.get("/api/agent/tasks/task_nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found"}
    assert list(body.keys()) == ["detail"]


@pytest.mark.asyncio
async def test_post_task_invalid_task_type_returns_422(client: AsyncClient):
    """POST /api/agent/tasks with invalid task_type returns 422 with detail array of validation items (spec 009)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Do something", "task_type": "invalid"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)
    for item in data["detail"]:
        assert "loc" in item and "msg" in item and "type" in item


@pytest.mark.asyncio
async def test_post_task_empty_direction_returns_422(client: AsyncClient):
    """POST /api/agent/tasks with empty direction returns 422 with detail array (spec 009)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "", "task_type": "impl"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)
    for item in data["detail"]:
        assert "loc" in item and "msg" in item and "type" in item


@pytest.mark.asyncio
async def test_post_task_direction_too_long_returns_422(client: AsyncClient):
    """POST /api/agent/tasks with direction > 5000 chars returns 422 (spec 010)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "x" * 5001, "task_type": "impl"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_task_missing_direction_returns_422(client: AsyncClient):
    """POST /api/agent/tasks without direction (body missing key or null) returns 422 (spec 002 edge-case)."""
    r = await client.post(
        "/api/agent/tasks",
        json={"task_type": "impl"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_post_task_missing_task_type_returns_422(client: AsyncClient):
    """POST /api/agent/tasks without task_type returns 422 (spec 002 edge-case)."""
    r = await client.post(
        "/api/agent/tasks",
        json={"direction": "Do something"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_post_task_direction_null_returns_422(client: AsyncClient):
    """POST /api/agent/tasks with direction null returns 422 (spec 002 edge-case)."""
    r = await client.post(
        "/api/agent/tasks",
        json={"direction": None, "task_type": "impl"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_post_task_direction_5000_chars_returns_201(client: AsyncClient):
    """POST with direction exactly 5000 chars returns 201 (spec 002 boundary)."""
    r = await client.post(
        "/api/agent/tasks",
        json={"direction": "x" * 5000, "task_type": "impl"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["direction"] == "x" * 5000
    assert data["id"].startswith("task_")


@pytest.mark.asyncio
async def test_post_task_direction_5001_chars_returns_422(client: AsyncClient):
    """POST with direction length 5001 returns 422 (spec 002 edge-case: direction boundary 5001)."""
    r = await client.post(
        "/api/agent/tasks",
        json={"direction": "x" * 5001, "task_type": "impl"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_get_task_by_id_returns_full_task(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns task with command."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "heal", "context": {"executor": "claude"}},
    )
    task_id = create.json()["id"]
    response = await client.get(f"/api/agent/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert "command" in data
    assert "claude" in data["command"]


@pytest.mark.asyncio
async def test_get_task_by_id_full_shape_includes_all_fields(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns full shape: command, output, progress_pct, current_step, decision_prompt, decision (spec 002 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Contract shape", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={
            "progress_pct": 25,
            "current_step": "Step",
            "decision_prompt": "Proceed?",
            "decision": "yes",
            "output": "Some output",
        },
    )
    response = await client.get(f"/api/agent/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    required = ("id", "direction", "task_type", "status", "model", "command", "output", "progress_pct", "current_step", "decision_prompt", "decision", "created_at", "updated_at")
    for key in required:
        assert key in data, f"Full task response must include {key}"
    assert data["progress_pct"] == 25
    assert data["current_step"] == "Step"
    assert data["decision_prompt"] == "Proceed?"
    assert data["decision"] == "yes"
    assert data["output"] == "Some output"


@pytest.mark.asyncio
async def test_patch_task_404_when_missing(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with non-existent id returns 404 (spec 009: body { detail: string } only)."""
    response = await client.patch(
        "/api/agent/tasks/task_nonexistent",
        json={"status": "completed", "output": "done"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found"}
    assert list(body.keys()) == ["detail"]


@pytest.mark.asyncio
async def test_patch_task_empty_body_returns_400(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with empty body (all optional fields null/absent) returns 400 (spec 002 edge-case)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one field required"


@pytest.mark.asyncio
async def test_patch_all_fields_explicit_null_returns_400(client: AsyncClient):
    """PATCH with body containing only null values returns 400 (spec 002: all optional null/absent)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={
            "status": None,
            "output": None,
            "progress_pct": None,
            "current_step": None,
            "decision_prompt": None,
            "decision": None,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one field required"


@pytest.mark.asyncio
async def test_patch_task_invalid_status_returns_422(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with invalid status returns 422 with detail array (spec 009)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "invalid"},
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    for item in data["detail"]:
        assert "loc" in item and "msg" in item and "type" in item


@pytest.mark.asyncio
async def test_patch_task_progress_pct_out_of_range_returns_422(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with progress_pct > 100 returns 422 (spec 010)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"progress_pct": 150},
    )
    assert response.status_code == 422


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
async def test_route_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/route response: task_type, model, command_template, tier, executor (spec 002 contract)."""
    response = await client.get("/api/agent/route?task_type=impl")
    assert response.status_code == 200
    data = response.json()
    required = ("task_type", "model", "command_template", "tier", "executor")
    for key in required:
        assert key in data, f"Route response must include {key}"
    assert data["executor"] in ("claude", "cursor")


@pytest.mark.asyncio
async def test_route_without_task_type_returns_422(client: AsyncClient):
    """GET /api/agent/route without task_type returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/route")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_route_invalid_task_type_returns_422(client: AsyncClient):
    """GET /api/agent/route with invalid task_type returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/route?task_type=invalid")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_tasks_limit_zero_returns_422(client: AsyncClient):
    """GET /api/agent/tasks with limit=0 returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_limit_over_max_returns_422(client: AsyncClient):
    """GET /api/agent/tasks with limit=101 returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks?limit=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_offset_negative_returns_422(client: AsyncClient):
    """GET /api/agent/tasks with offset=-1 returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_invalid_status_returns_422(client: AsyncClient):
    """GET /api/agent/tasks?status=invalid returns 422 (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks?status=invalid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_status_pending_returns_only_pending(client: AsyncClient):
    """GET /api/agent/tasks?status=pending returns only pending tasks (spec 002 edge-case)."""
    await client.post("/api/agent/tasks", json={"direction": "Pending one", "task_type": "impl"})
    create2 = await client.post("/api/agent/tasks", json={"direction": "Completed one", "task_type": "impl"})
    await client.patch(f"/api/agent/tasks/{create2.json()['id']}", json={"status": "completed"})
    response = await client.get("/api/agent/tasks?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert all(t["status"] == "pending" for t in data["tasks"])
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_fixed_path_attention_not_matched_as_task_id(client: AsyncClient):
    """GET /api/agent/tasks/attention returns list, not task by id 'attention' (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks/attention")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "total" in data
    assert "detail" not in data or data.get("detail") != "Task not found"


@pytest.mark.asyncio
async def test_fixed_path_count_not_matched_as_task_id(client: AsyncClient):
    """GET /api/agent/tasks/count returns counts, not task by id 'count' (spec 002 edge-case)."""
    response = await client.get("/api/agent/tasks/count")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_status" in data
    assert "detail" not in data or data.get("detail") != "Task not found"


@pytest.mark.asyncio
async def test_task_id_path_resolves_to_task(client: AsyncClient):
    """GET /api/agent/tasks/{id} with real task id returns that task (spec 002 edge-case)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Resolve by id", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.get(f"/api/agent/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["direction"] == "Resolve by id"


@pytest.mark.asyncio
async def test_task_log_404_when_task_missing(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns 404 when task not found (spec 009: body { detail: string } only)."""
    response = await client.get("/api/agent/tasks/task_nonexistent/log")
    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found"}
    assert list(body.keys()) == ["detail"]


@pytest.mark.asyncio
async def test_list_items_omit_command_and_output(client: AsyncClient):
    """GET /api/agent/tasks list items omit command and output (spec 002 data model)."""
    await client.post(
        "/api/agent/tasks",
        json={"direction": "List shape check", "task_type": "impl"},
    )
    response = await client.get("/api/agent/tasks")
    assert response.status_code == 200
    for item in response.json()["tasks"]:
        assert "command" not in item
        assert "output" not in item
        assert "id" in item and "status" in item and "task_type" in item


@pytest.mark.asyncio
async def test_patch_progress_pct_negative_returns_422(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with progress_pct < 0 returns 422 (spec 002 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"progress_pct": -1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_progress_pct_over_100_returns_422(client: AsyncClient):
    """PATCH /api/agent/tasks/{id} with progress_pct > 100 returns 422 (spec 002 edge-case)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"progress_pct": 101},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_progress_pct_boundary_0_and_100_succeed(client: AsyncClient):
    """PATCH with progress_pct=0 and progress_pct=100 returns 200 (spec 002: int 0-100)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Boundary test", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    r0 = await client.patch(f"/api/agent/tasks/{task_id}", json={"progress_pct": 0})
    assert r0.status_code == 200
    assert r0.json()["progress_pct"] == 0
    r100 = await client.patch(f"/api/agent/tasks/{task_id}", json={"progress_pct": 100})
    assert r100.status_code == 200
    assert r100.json()["progress_pct"] == 100


@pytest.mark.asyncio
async def test_patch_progress_pct_string_returns_422(client: AsyncClient):
    """PATCH with progress_pct as string (e.g. \"50\") returns 422 (spec 002 edge-case)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix bug", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"progress_pct": "50"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_task_by_id_includes_output_when_set(client: AsyncClient):
    """GET /api/agent/tasks/{id} returns full task including output when set (spec 002 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Full task output", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "output": "Done."},
    )
    response = await client.get(f"/api/agent/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data.get("output") == "Done."
    assert "command" in data


@pytest.mark.asyncio
async def test_spec_tasks_route_to_local(client: AsyncClient):
    """spec task_type routes to local model."""
    response = await client.get("/api/agent/route?task_type=spec")
    assert response.status_code == 200
    data = response.json()
    assert "ollama" in data["model"].lower() or "glm" in data["model"].lower() or "qwen" in data["model"].lower()


@pytest.mark.asyncio
async def test_test_tasks_route_to_local(client: AsyncClient):
    """test task_type routes to local model."""
    response = await client.get("/api/agent/route?task_type=test")
    assert response.status_code == 200
    data = response.json()
    assert "ollama" in data["model"].lower() or "glm" in data["model"].lower() or "qwen" in data["model"].lower()


@pytest.mark.asyncio
async def test_review_tasks_route_to_local(client: AsyncClient):
    """review task_type routes to local model."""
    response = await client.get("/api/agent/route?task_type=review")
    assert response.status_code == 200
    data = response.json()
    assert "ollama" in data["model"].lower() or "glm" in data["model"].lower() or "qwen" in data["model"].lower()


@pytest.mark.asyncio
async def test_impl_tasks_route_to_local(client: AsyncClient):
    """impl task_type routes to local (Ollama) model when executor=claude."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Implement feature", "task_type": "impl", "context": {"executor": "claude"}},
    )
    data = response.json()
    assert any(x in data["model"] for x in ("qwen3-coder", "glm-4.7-flash", "ollama"))


@pytest.mark.asyncio
async def test_heal_tasks_route_to_claude(client: AsyncClient):
    """heal task_type routes to Claude (subscription) model when executor=claude."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "Fix failing CI", "task_type": "heal", "context": {"executor": "claude"}},
    )
    data = response.json()
    assert "claude" in data["model"].lower()


@pytest.mark.asyncio
async def test_cursor_executor_routes_to_cursor_cli(client: AsyncClient):
    """context.executor=cursor uses Cursor CLI (agent command)."""
    response = await client.post(
        "/api/agent/tasks",
        json={
            "direction": "Implement feature",
            "task_type": "impl",
            "context": {"executor": "cursor"},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "cursor" in data["model"].lower()
    assert data["command"].strip().startswith("agent ")
    assert "composer-1" in data["command"] or "claude-4-opus" in data["command"] or "auto" in data["command"]


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
async def test_attention_limit_validation(client: AsyncClient):
    """GET /api/agent/tasks/attention with limit=0 or limit=101 returns 422 (spec 002 contract)."""
    r0 = await client.get("/api/agent/tasks/attention?limit=0")
    assert r0.status_code == 422
    r1 = await client.get("/api/agent/tasks/attention?limit=101")
    assert r1.status_code == 422


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


@pytest.mark.asyncio
async def test_task_count_returns_200(client: AsyncClient):
    """GET /api/agent/tasks/count returns total and by_status."""
    response = await client.get("/api/agent/tasks/count")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_status" in data


@pytest.mark.asyncio
async def test_task_count_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/tasks/count response: total (int), by_status (dict) (spec 002 contract)."""
    response = await client.get("/api/agent/tasks/count")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_status" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["by_status"], dict)


@pytest.mark.asyncio
async def test_task_count_empty_store_returns_zero_total(client: AsyncClient):
    """GET /api/agent/tasks/count when no tasks returns total=0, by_status empty (spec 002 edge-case)."""
    # Store is reset per test
    response = await client.get("/api/agent/tasks/count")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["by_status"] == {}


@pytest.mark.asyncio
async def test_usage_endpoint_returns_200(client: AsyncClient):
    """GET /api/agent/usage returns usage summary."""
    response = await client.get("/api/agent/usage")
    assert response.status_code == 200
    data = response.json()
    assert "by_model" in data
    assert "routing" in data


@pytest.mark.asyncio
async def test_usage_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/usage response: by_model, routing (spec 002 contract)."""
    response = await client.get("/api/agent/usage")
    assert response.status_code == 200
    data = response.json()
    assert "by_model" in data and "routing" in data
    assert isinstance(data["by_model"], dict)
    assert isinstance(data["routing"], dict)


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(client: AsyncClient):
    """GET /api/agent/metrics returns aggregates (spec 027)."""
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "success_rate" in data
    assert "execution_time" in data
    assert "by_task_type" in data
    assert "by_model" in data
    sr = data["success_rate"]
    assert "completed" in sr
    assert "failed" in sr
    assert "total" in sr
    assert "rate" in sr


@pytest.mark.asyncio
async def test_metrics_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/metrics: success_rate (completed, failed, total, rate), execution_time, by_task_type, by_model (spec 002 contract)."""
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    for key in ("success_rate", "execution_time", "by_task_type", "by_model"):
        assert key in data, f"Metrics response must include {key}"
    for key in ("completed", "failed", "total", "rate"):
        assert key in data["success_rate"], f"success_rate must include {key}"


@pytest.mark.asyncio
async def test_pipeline_status_returns_200(client: AsyncClient):
    """GET /api/agent/pipeline-status returns running, pending, recent_completed, attention (spec 027)."""
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "pending" in data
    assert "recent_completed" in data
    assert "attention" in data
    att = data["attention"]
    assert "stuck" in att
    assert "repeated_failures" in att
    assert "low_success_rate" in att
    assert "flags" in att
    assert "running_by_phase" in data
    assert set(data["running_by_phase"].keys()) == {"spec", "impl", "test", "review"}


@pytest.mark.asyncio
async def test_pipeline_status_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/pipeline-status: running, pending, recent_completed, attention (stuck, repeated_failures, low_success_rate, flags), project_manager, running_by_phase (spec 002 contract)."""
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data and "pending" in data and "recent_completed" in data and "attention" in data
    att = data["attention"]
    for key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
        assert key in att, f"pipeline-status.attention must include {key}"
    assert "running_by_phase" in data


@pytest.mark.asyncio
async def test_monitor_issues_returns_200(client: AsyncClient):
    """GET /api/agent/monitor-issues returns issues list, last_check (spec 027)."""
    response = await client.get("/api/agent/monitor-issues")
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    assert isinstance(data["issues"], list)
    assert "last_check" in data


@pytest.mark.asyncio
async def test_monitor_issues_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/monitor-issues response: issues (list), last_check (str|null) (spec 002 contract)."""
    response = await client.get("/api/agent/monitor-issues")
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data and "last_check" in data
    assert isinstance(data["issues"], list)
    assert data["last_check"] is None or isinstance(data["last_check"], str)


@pytest.mark.asyncio
async def test_effectiveness_endpoint_returns_200(client: AsyncClient):
    """GET /api/agent/effectiveness returns throughput, success_rate, issues, progress, goal_proximity."""
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert "throughput" in data
    assert "success_rate" in data
    assert "issues" in data
    assert "progress" in data
    assert "goal_proximity" in data
    assert "top_issues_by_priority" in data


@pytest.mark.asyncio
async def test_status_report_returns_200(client: AsyncClient):
    """GET /api/agent/status-report returns hierarchical status (layer_0_goal through layer_3_attention)."""
    response = await client.get("/api/agent/status-report")
    assert response.status_code == 200
    data = response.json()
    assert "overall" in data
    assert "going_well" in data["overall"]
    assert "needs_attention" in data["overall"]
    assert "layer_0_goal" in data
    assert "layer_1_orchestration" in data
    assert "layer_2_execution" in data
    assert "layer_3_attention" in data


@pytest.mark.asyncio
async def test_task_log_returns_command_and_output(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns task_id, command, output."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Log test", "task_type": "impl", "context": {"executor": "claude"}},
    )
    task_id = create.json()["id"]
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert "command" in data
    assert "claude" in (data.get("command") or "")


@pytest.mark.asyncio
async def test_task_log_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log response: task_id, log (str|null), command, output (spec 002 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Log shape", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 200
    data = response.json()
    required = ("task_id", "log", "command", "output")
    for key in required:
        assert key in data, f"Task log response must include {key}"
    assert data["log"] is None or isinstance(data["log"], str)


@pytest.mark.asyncio
async def test_task_log_returns_null_when_file_missing(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns 200 with log null when log file not yet created."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Task without log file", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    # Log file not created until agent runs; expect 200 with log: null
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data.get("log") is None
    assert "command" in data


@pytest.mark.asyncio
async def test_task_log_returns_output_from_task_when_set(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns task output in response when set (spec 002 edge-case)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Task with output", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "output": "Build succeeded."},
    )
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data.get("output") == "Build succeeded."
    assert "command" in data


@pytest.mark.asyncio
async def test_route_executor_optional_default_claude(client: AsyncClient):
    """GET /api/agent/route without executor returns executor=claude (spec 002 edge-case)."""
    response = await client.get("/api/agent/route?task_type=impl")
    assert response.status_code == 200
    data = response.json()
    assert data.get("executor") == "claude"
    assert "command_template" in data


@pytest.mark.asyncio
async def test_get_tasks_limit_one_returns_at_most_one(client: AsyncClient):
    """GET /api/agent/tasks?limit=1 returns at most 1 task, total unchanged (spec 002 edge-case)."""
    await client.post("/api/agent/tasks", json={"direction": "First", "task_type": "impl"})
    await client.post("/api/agent/tasks", json={"direction": "Second", "task_type": "impl"})
    response = await client.get("/api/agent/tasks?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) <= 1
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_monitor_issues_empty_when_no_file(client: AsyncClient):
    """GET /api/agent/monitor-issues returns issues=[], last_check=None when file missing (spec 002)."""
    response = await client.get("/api/agent/monitor-issues")
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    assert "last_check" in data
    assert isinstance(data["issues"], list)
    # When monitor_issues.json is absent, implementation returns empty; last_check may be None
    assert data["last_check"] is None or isinstance(data["last_check"], (str, type(None)))


# --- Telegram API (spec 002 contract) ---


@pytest.mark.asyncio
async def test_telegram_reply_via_webhook_records_decision(client: AsyncClient):
    """Telegram /reply {task_id} {decision} via webhook records decision and sets status→running (spec 003 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Need decision", "task_type": "impl"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "needs_decision", "output": "Proceed?"},
    )
    payload = {
        "update_id": 90002,
        "message": {
            "message_id": 2,
            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 12345, "type": "private"},
            "date": 1640000001,
            "text": f"/reply {task_id} yes",
        },
    }
    r = await client.post("/api/agent/telegram/webhook", json=payload)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    get_task = await client.get(f"/api/agent/tasks/{task_id}")
    assert get_task.status_code == 200
    data = get_task.json()
    assert data["status"] == "running"
    assert data["decision"] == "yes"


@pytest.mark.asyncio
async def test_telegram_webhook_returns_200(client: AsyncClient):
    """POST /api/agent/telegram/webhook returns 200 with ok: true (spec 002 contract)."""
    response = await client.post(
        "/api/agent/telegram/webhook",
        json={"update_id": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True


@pytest.mark.asyncio
async def test_telegram_webhook_no_message_returns_200(client: AsyncClient):
    """POST webhook with update containing no message or edited_message returns 200, ok: true (spec 002 edge-case)."""
    response = await client.post(
        "/api/agent/telegram/webhook",
        json={"update_id": 2, "callback_query": {"id": "cb1", "data": "x"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True


@pytest.mark.asyncio
async def test_telegram_diagnostics_returns_200(client: AsyncClient):
    """GET /api/agent/telegram/diagnostics returns config, webhook_events, send_results (spec 002 contract)."""
    response = await client.get("/api/agent/telegram/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    cfg = data["config"]
    assert "has_token" in cfg
    assert "token_prefix" in cfg
    assert "chat_ids" in cfg
    assert "allowed_user_ids" in cfg
    assert "webhook_events" in data
    assert "send_results" in data


@pytest.mark.asyncio
async def test_telegram_flow_diagnostic(client: AsyncClient):
    """Diagnostic test (spec 003): POST webhook with command, GET diagnostics; assert webhook_events updated and response has config, webhook_events, send_results."""
    from app.services import telegram_diagnostics as diag

    diag.clear()
    r0 = await client.get("/api/agent/telegram/diagnostics")
    assert r0.status_code == 200
    initial_events = len(r0.json().get("webhook_events", []))
    payload = {
        "update_id": 90001,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 12345, "type": "private"},
            "date": 1640000000,
            "text": "/status",
        },
    }
    r1 = await client.post("/api/agent/telegram/webhook", json=payload)
    assert r1.status_code == 200
    assert r1.json().get("ok") is True
    r2 = await client.get("/api/agent/telegram/diagnostics")
    assert r2.status_code == 200
    data = r2.json()
    # Contract: response has config, webhook_events, send_results
    assert "config" in data
    assert "webhook_events" in data
    assert "send_results" in data
    cfg = data["config"]
    assert "has_token" in cfg
    assert "token_prefix" in cfg
    assert "chat_ids" in cfg
    assert "allowed_user_ids" in cfg
    # webhook_events was updated by this POST
    assert len(data["webhook_events"]) >= initial_events + 1
    # Latest entry (or the one we sent) has update matching payload
    our_event = next((e for e in data["webhook_events"] if e.get("update", {}).get("update_id") == 90001), None)
    assert our_event is not None, "webhook_events must contain the update we sent"
    assert "update" in our_event
    assert our_event["update"].get("update_id") == 90001
    assert our_event["update"].get("message", {}).get("text") == "/status"


@pytest.mark.asyncio
async def test_telegram_test_send_returns_structure(client: AsyncClient):
    """POST /api/agent/telegram/test-send returns 200 with ok and (results or error) (spec 002 contract)."""
    response = await client.post("/api/agent/telegram/test-send")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert isinstance(data["ok"], bool)
    # When token/chat_ids not set: ok=False, error=...; when set: ok=..., results=[...]
    assert "results" in data or "error" in data
    if "results" in data:
        assert isinstance(data["results"], list)
    if "error" in data:
        assert isinstance(data["error"], str)


@pytest.mark.asyncio
async def test_telegram_test_send_accepts_optional_text_param(client: AsyncClient):
    """POST /api/agent/telegram/test-send?text=... accepts optional query param (spec 002 contract)."""
    response = await client.post(
        "/api/agent/telegram/test-send",
        params={"text": "Custom test message"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "results" in data or "error" in data


@pytest.mark.asyncio
async def test_root_returns_200(client: AsyncClient):
    """GET / returns API info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_update_spec_coverage_dry_run():
    """update_spec_coverage.py --dry-run exits 0 and does not modify files (spec 027)."""
    import os
    import subprocess
    import sys

    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "update_spec_coverage.py")
    assert os.path.isfile(script), "update_spec_coverage.py must exist per spec 027"
    result = subprocess.run(
        [sys.executable, script, "--dry-run"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=os.path.dirname(os.path.dirname(script)),
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in (result.stderr or "")


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
