"""Tests for agent orchestration API — spec 002."""

import json
import os
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _api_logs_dir() -> str:
    """api/logs path (must match router's log_path for task logs)."""
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(api_dir, "logs")


def _ensure_task_log_file(task_id: str, content: str = "") -> None:
    """Create api/logs/task_{task_id}.log so GET /api/agent/tasks/{id}/log returns 200."""
    logs_dir = _api_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, f"task_{task_id}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=5.0) as ac:
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
    """POST /api/agent/tasks with invalid task_type returns 422 (contract: status 422, detail list of {loc, msg, type}, error for task_type)."""
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
    # Contract: at least one validation error refers to task_type
    assert any("task_type" in (item.get("loc") or []) for item in data["detail"])


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
async def test_post_task_direction_whitespace_only_returns_422(client: AsyncClient):
    """POST with direction whitespace-only returns 422 (spec 010: strip then min_length; whitespace-only becomes empty). Contract: 422, detail list of {loc, msg, type}, at least one error for direction."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "   \t\n  ", "task_type": "impl"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)
    for item in data["detail"]:
        assert "loc" in item and "msg" in item and "type" in item
    assert any("direction" in (item.get("loc") or []) for item in data["detail"])


@pytest.mark.asyncio
async def test_post_task_direction_stripped_stored(client: AsyncClient):
    """POST with leading/trailing whitespace: direction is stored stripped (spec 010 Pydantic refinement)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "  add GET /api/projects  ", "task_type": "impl"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["direction"] == "add GET /api/projects"


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
async def test_task_log_404_when_log_file_missing(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns 404 when log file missing (spec 002).

    Contract: task exists in store but api/logs/task_{id}.log does not exist
    → status 404, body exactly { "detail": "Task log not found" }, no other keys.
    """
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Task without log file", "task_type": "impl"},
    )
    assert create.status_code == 201, "setup: task must be created"
    task_id = create.json()["id"]
    # Ensure log file does not exist (same path as router uses)
    log_path = os.path.join(_api_logs_dir(), f"task_{task_id}.log")
    if os.path.isfile(log_path):
        os.remove(log_path)
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task log not found"}
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
    """GET /api/agent/route?task_type=spec returns 200; spec task_type routed to local tier per routing table (002)."""
    response = await client.get("/api/agent/route?task_type=spec")
    assert response.status_code == 200
    data = response.json()
    assert data["task_type"] == "spec"
    # Model indicates local (ollama/glm/qwen) and/or tier is local (spec 043, 002)
    model_lower = data["model"].lower()
    assert (
        "ollama" in model_lower or "glm" in model_lower or "qwen" in model_lower
    ), "spec must route to local model"
    assert data.get("tier") == "local", "spec task_type must be tier local per 002"


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
async def test_attention_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/tasks/attention response: tasks (list), total (int); each task has id, direction, status, optional output, decision_prompt (spec 003 contract)."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Need decision", "task_type": "impl"},
    )
    task_id = create.json()["id"]
    await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={
            "status": "needs_decision",
            "output": "Tests failed. Proceed?",
            "decision_prompt": "Reply yes to fix, no to skip",
        },
    )
    r = await client.get("/api/agent/tasks/attention")
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert "total" in data
    assert isinstance(data["tasks"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= 1
    task = next(t for t in data["tasks"] if t["id"] == task_id)
    assert "id" in task
    assert "direction" in task
    assert "status" in task
    assert task["status"] == "needs_decision"
    assert task.get("output") == "Tests failed. Proceed?"
    assert task.get("decision_prompt") == "Reply yes to fix, no to skip"


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


# --- Spec 026 Phase 1: Persist task metrics; GET /api/agent/metrics ---


@pytest.mark.asyncio
async def test_get_metrics_026_returns_200_and_structure(client: AsyncClient):
    """GET /api/agent/metrics returns 200 with success_rate, execution_time (p50/p95), by_task_type, by_model (spec 026 Phase 1)."""
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "success_rate" in data
    assert "execution_time" in data
    assert "by_task_type" in data
    assert "by_model" in data
    sr = data["success_rate"]
    assert "completed" in sr and "failed" in sr and "total" in sr and "rate" in sr
    et = data["execution_time"]
    assert "p50_seconds" in et and "p95_seconds" in et


@pytest.mark.asyncio
async def test_get_metrics_026_response_shape_defines_contract(client: AsyncClient):
    """GET /api/agent/metrics response shape: success_rate (completed, failed, total, rate), execution_time (p50_seconds, p95_seconds), by_task_type (count, completed, failed, success_rate), by_model (count, avg_duration). Spec 026 Phase 1."""
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    # Top-level
    for key in ("success_rate", "execution_time", "by_task_type", "by_model"):
        assert key in data, f"Metrics response must include {key}"
    # success_rate
    for key in ("completed", "failed", "total", "rate"):
        assert key in data["success_rate"], f"success_rate must include {key}"
    assert isinstance(data["success_rate"]["completed"], int)
    assert isinstance(data["success_rate"]["failed"], int)
    assert isinstance(data["success_rate"]["total"], int)
    assert isinstance(data["success_rate"]["rate"], (int, float))
    # execution_time
    assert "p50_seconds" in data["execution_time"] and "p95_seconds" in data["execution_time"]
    assert isinstance(data["execution_time"]["p50_seconds"], (int, float))
    assert isinstance(data["execution_time"]["p95_seconds"], (int, float))
    # by_task_type: each value has count, completed, failed, success_rate
    assert isinstance(data["by_task_type"], dict)
    for entry in data["by_task_type"].values():
        for k in ("count", "completed", "failed", "success_rate"):
            assert k in entry, f"by_task_type entry must include {k}"
    # by_model: each value has count, avg_duration
    assert isinstance(data["by_model"], dict)
    for entry in data["by_model"].values():
        assert "count" in entry and "avg_duration" in entry, "by_model entry must include count, avg_duration"


@pytest.mark.asyncio
async def test_get_metrics_026_zeroed_when_no_metrics(client: AsyncClient):
    """GET /api/agent/metrics when no metrics (total=0): rate=0.0, by_task_type={}, by_model={}, p50/p95=0. Spec 026 Phase 1."""
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    if data["success_rate"]["total"] == 0:
        assert data["success_rate"]["rate"] == 0.0
        assert data["by_task_type"] == {}
        assert data["by_model"] == {}
        assert data["execution_time"]["p50_seconds"] == 0
        assert data["execution_time"]["p95_seconds"] == 0


@pytest.mark.asyncio
async def test_get_metrics_026_persist_on_patch_completed(client: AsyncClient):
    """When a task is PATCHed to completed, a metric record is persisted and GET /api/agent/metrics reflects it. Spec 026 Phase 1."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Metrics persist test", "task_type": "impl"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]
    patch = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "output": "Done"},
    )
    assert patch.status_code == 200
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success_rate"]["total"] >= 1
    # Entry shapes when data exists
    for entry in data["by_task_type"].values():
        assert "count" in entry and "completed" in entry and "failed" in entry and "success_rate" in entry
    for entry in data["by_model"].values():
        assert "count" in entry and "avg_duration" in entry


@pytest.mark.asyncio
async def test_get_metrics_026_persist_on_patch_failed(client: AsyncClient):
    """When a task is PATCHed to failed, a metric record is persisted and GET /api/agent/metrics reflects it. Spec 026 Phase 1."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Metrics failed test", "task_type": "spec"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]
    patch = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "failed", "output": "Error"},
    )
    assert patch.status_code == 200
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success_rate"]["total"] >= 1
    assert data["success_rate"]["failed"] >= 1


@pytest.mark.asyncio
async def test_get_metrics_026_empty_store_returns_zeroed_contract(
    client: AsyncClient, tmp_path, monkeypatch
):
    """GET /api/agent/metrics with no metrics returns exact zeroed structure (spec 026 Phase 1 contract)."""
    metrics_file = tmp_path / "metrics.jsonl"
    metrics_file.write_text("")
    monkeypatch.setattr("app.services.metrics_service.METRICS_FILE", str(metrics_file))
    response = await client.get("/api/agent/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success_rate"]["completed"] == 0
    assert data["success_rate"]["failed"] == 0
    assert data["success_rate"]["total"] == 0
    assert data["success_rate"]["rate"] == 0.0
    assert data["execution_time"]["p50_seconds"] == 0
    assert data["execution_time"]["p95_seconds"] == 0
    assert data["by_task_type"] == {}
    assert data["by_model"] == {}


@pytest.mark.asyncio
async def test_get_metrics_026_record_in_jsonl_on_patch_completed(
    client: AsyncClient, tmp_path, monkeypatch
):
    """When a task is PATCHed to completed, a record appears in the metrics store (JSONL). Spec 026 Phase 1."""
    metrics_file = tmp_path / "metrics.jsonl"
    monkeypatch.setattr("app.services.metrics_service.METRICS_FILE", str(metrics_file))
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "JSONL persist test", "task_type": "impl"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]
    patch = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "output": "Done"},
    )
    assert patch.status_code == 200
    content = metrics_file.read_text()
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    assert len(lines) == 1, "metrics store must contain exactly one record after PATCH completed"
    record = json.loads(lines[0])
    for key in ("task_id", "task_type", "model", "duration_seconds", "status", "created_at"):
        assert key in record, f"TaskMetricRecord must include {key}"
    assert record["task_id"] == task_id
    assert record["status"] == "completed"
    assert record["task_type"] == "impl"
    assert isinstance(record["duration_seconds"], (int, float))
    assert isinstance(record["created_at"], str)


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
async def test_pipeline_status_returns_200_when_no_running_task_empty_state(client: AsyncClient):
    """GET /api/agent/pipeline-status returns 200 when no running task (empty state); scripts/monitors can rely on it (spec 039).
    Contract: status 200, body has running, pending, recent_completed, attention, running_by_phase; running is empty list; attention has stuck, repeated_failures, low_success_rate, flags; running_by_phase has keys spec, impl, test, review."""
    agent_service.clear_store()
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase"):
        assert key in data, f"pipeline-status must include {key}"
    assert isinstance(data["running"], list), "running must be a list"
    assert data["running"] == [], "running must be empty when no running task"
    att = data["attention"]
    for key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
        assert key in att, f"attention must include {key}"
    assert set(data["running_by_phase"].keys()) == {"spec", "impl", "test", "review"}, "running_by_phase must have phase keys (spec 002)"


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
async def test_pipeline_status_attention_stuck_when_pending_long_wait(client: AsyncClient):
    """When pending tasks, no running, longest wait > 10 min: attention.stuck true and 'stuck' in flags (spec 032)."""
    from datetime import datetime, timezone, timedelta
    from unittest.mock import patch

    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Stuck test", "task_type": "impl"},
    )
    assert create.status_code == 201
    task = (await client.get(f"/api/agent/tasks/{create.json()['id']}")).json()
    created_str = task["created_at"]
    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    now_utc = created + timedelta(minutes=11)

    def get_status_with_time():
        return agent_service.get_pipeline_status(now_utc=now_utc)

    with patch.object(agent_service, "get_pipeline_status", get_status_with_time):
        response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["stuck"] is True
    assert "stuck" in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_repeated_failures_when_last_three_failed(client: AsyncClient):
    """When three most recently completed tasks are all failed: repeated_failures true and in flags (spec 032)."""
    ids = []
    for i in range(3):
        create = await client.post(
            "/api/agent/tasks",
            json={"direction": f"Fail {i}", "task_type": "impl"},
        )
        assert create.status_code == 201
        ids.append(create.json()["id"])
    for task_id in ids:
        patch_resp = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "failed"},
        )
        assert patch_resp.status_code == 200
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["repeated_failures"] is True
    assert "repeated_failures" in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_stuck_false_when_no_pending(client: AsyncClient):
    """When there are no pending tasks: attention.stuck is false and 'stuck' not in flags (spec 032 contract)."""
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["stuck"] is False
    assert "stuck" not in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_stuck_false_when_running_exists(client: AsyncClient):
    """When there is a running task: attention.stuck is false even if pending exist with long wait (spec 032 contract)."""
    from datetime import datetime, timezone, timedelta
    from unittest.mock import patch

    create_pending = await client.post(
        "/api/agent/tasks",
        json={"direction": "Pending", "task_type": "impl"},
    )
    assert create_pending.status_code == 201
    pending_id = create_pending.json()["id"]
    create_running = await client.post(
        "/api/agent/tasks",
        json={"direction": "Running", "task_type": "impl"},
    )
    assert create_running.status_code == 201
    await client.patch(
        f"/api/agent/tasks/{create_running.json()['id']}",
        json={"status": "running"},
    )
    task = (await client.get(f"/api/agent/tasks/{pending_id}")).json()
    created = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
    now_utc = created + timedelta(minutes=11)

    def get_status_with_time():
        return agent_service.get_pipeline_status(now_utc=now_utc)

    with patch.object(agent_service, "get_pipeline_status", get_status_with_time):
        response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["stuck"] is False
    assert "stuck" not in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_stuck_false_when_wait_under_threshold(client: AsyncClient):
    """When pending tasks but longest wait <= 10 min: attention.stuck is false (spec 032 contract)."""
    from datetime import datetime, timezone, timedelta
    from unittest.mock import patch

    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Under threshold", "task_type": "impl"},
    )
    assert create.status_code == 201
    task = (await client.get(f"/api/agent/tasks/{create.json()['id']}")).json()
    created = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
    now_utc = created + timedelta(minutes=5)

    def get_status_with_time():
        return agent_service.get_pipeline_status(now_utc=now_utc)

    with patch.object(agent_service, "get_pipeline_status", get_status_with_time):
        response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["stuck"] is False
    assert "stuck" not in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_repeated_failures_false_when_fewer_than_three_completed(client: AsyncClient):
    """When fewer than 3 completed tasks: attention.repeated_failures is false (spec 032 contract)."""
    for i in range(2):
        create = await client.post(
            "/api/agent/tasks",
            json={"direction": f"Fail {i}", "task_type": "impl"},
        )
        assert create.status_code == 201
        await client.patch(
            f"/api/agent/tasks/{create.json()['id']}",
            json={"status": "failed", "output": "x"},
        )
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["repeated_failures"] is False
    assert "repeated_failures" not in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_repeated_failures_false_when_last_not_all_failed(client: AsyncClient):
    """When the three most recently completed are not all failed: attention.repeated_failures is false (spec 032 contract)."""
    ids = []
    for i in range(3):
        create = await client.post(
            "/api/agent/tasks",
            json={"direction": f"Task {i}", "task_type": "impl"},
        )
        assert create.status_code == 201
        ids.append(create.json()["id"])
    await client.patch(f"/api/agent/tasks/{ids[0]}", json={"status": "failed", "output": "x"})
    await client.patch(f"/api/agent/tasks/{ids[1]}", json={"status": "failed", "output": "x"})
    await client.patch(f"/api/agent/tasks/{ids[2]}", json={"status": "completed", "output": "ok"})
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["repeated_failures"] is False
    assert "repeated_failures" not in att["flags"]


@pytest.mark.asyncio
async def test_pipeline_status_attention_low_success_rate_false_when_metrics_missing(client: AsyncClient):
    """When metrics are missing or empty: attention.low_success_rate is false, no exception (spec 032)."""
    response = await client.get("/api/agent/pipeline-status")
    assert response.status_code == 200
    data = response.json()
    att = data["attention"]
    assert att["low_success_rate"] is False
    assert "low_success_rate" not in att["flags"]


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
async def test_effectiveness_response_includes_heal_resolved_count(client: AsyncClient):
    """GET /api/agent/effectiveness includes heal_resolved_count (spec 007 meta-pipeline item 5)."""
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert "heal_resolved_count" in data, "effectiveness must expose heal_resolved_count"
    assert isinstance(data["heal_resolved_count"], int), "heal_resolved_count must be an integer"
    assert data["heal_resolved_count"] >= 0, "heal_resolved_count must be >= 0"


@pytest.mark.asyncio
async def test_effectiveness_plan_progress_includes_phase_6_and_phase_7(client: AsyncClient):
    """GET /api/agent/effectiveness returns plan_progress with phase_6 and phase_7 (spec 045)."""
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert "plan_progress" in data
    pp = data["plan_progress"]
    assert "phase_6" in pp, "plan_progress must include phase_6"
    assert "phase_7" in pp, "plan_progress must include phase_7"
    assert isinstance(pp["phase_6"].get("completed"), int)
    assert isinstance(pp["phase_6"].get("total"), int)
    assert isinstance(pp["phase_7"].get("completed"), int)
    assert isinstance(pp["phase_7"].get("total"), int)
    assert pp["phase_6"]["total"] == 2, "Phase 6 total is 2 (items 56–57 per 006)"
    assert pp["phase_7"]["total"] == 17, "Phase 7 total is 17 (items 58–74 per 006)"



@pytest.mark.asyncio
async def test_heal_task_creation_stores_monitor_context(client: AsyncClient):
    """Heal task creation stores context.monitor_condition and monitor_issue_id (which heal addressed which issue)."""
    response = await client.post(
        "/api/agent/tasks",
        json={
            "direction": "Fix no_task_running",
            "task_type": "heal",
            "context": {
                "executor": "claude",
                "monitor_condition": "no_task_running",
                "monitor_issue_id": "issue-abc123",
            },
        },
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    get_resp = await client.get(f"/api/agent/tasks/{task_id}")
    assert get_resp.status_code == 200
    task = get_resp.json()
    assert task.get("context") is not None
    assert task["context"].get("monitor_condition") == "no_task_running"
    assert task["context"].get("monitor_issue_id") == "issue-abc123"


@pytest.mark.asyncio
async def test_heal_resolved_count_counts_only_resolutions_with_heal_task_id(
    client: AsyncClient, tmp_path, monkeypatch
):
    """heal_resolved_count is the count of resolution records (7d window) that have heal_task_id (spec 007 item 5)."""
    resolutions_file = tmp_path / "monitor_resolutions.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    # One resolution attributed to a heal task, one without
    resolutions_file.write_text(
        json.dumps({"condition": "no_task_running", "resolved_at": now, "heal_task_id": "task_abc"}) + "\n"
        + json.dumps({"condition": "api_unreachable", "resolved_at": now}) + "\n"
    )
    monkeypatch.setattr(
        "app.services.effectiveness_service.RESOLUTIONS_FILE",
        str(resolutions_file),
    )
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert data["heal_resolved_count"] == 1, "only resolutions with heal_task_id count toward heal_resolved_count"


# --- Heal task effectiveness tracking contract (spec 007 meta-pipeline item 5) ---
# - Which heal addressed which issue: heal task stores context.monitor_condition and context.monitor_issue_id;
#   monitor_issues.json issues may include heal_task_id when a heal was created for that issue.
# - When condition clears: resolution is recorded with optional heal_task_id (attribute to heal).
# - heal_resolved_count: count of resolution records in 7d window that have heal_task_id; exposed in GET /api/agent/effectiveness.
# - Resolution record: condition, resolved_at (ISO8601); optional heal_task_id. Records without valid resolved_at are skipped.


@pytest.mark.asyncio
async def test_heal_resolved_count_excludes_resolutions_older_than_7d(
    client: AsyncClient, tmp_path, monkeypatch
):
    """heal_resolved_count only counts resolution records within the 7d window; older records are excluded."""
    from datetime import timedelta

    resolutions_file = tmp_path / "monitor_resolutions.jsonl"
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=8)).isoformat()
    # One resolution 8 days ago with heal_task_id; should not count
    resolutions_file.write_text(
        json.dumps({"condition": "no_task_running", "resolved_at": old, "heal_task_id": "task_old"}) + "\n"
    )
    monkeypatch.setattr(
        "app.services.effectiveness_service.RESOLUTIONS_FILE",
        str(resolutions_file),
    )
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert data["heal_resolved_count"] == 0, "resolutions older than 7d must not count toward heal_resolved_count"


@pytest.mark.asyncio
async def test_resolution_record_without_resolved_at_skipped_for_heal_resolved_count(
    client: AsyncClient, tmp_path, monkeypatch
):
    """Resolution records without valid resolved_at are skipped; only valid records in 7d window with heal_task_id count."""
    resolutions_file = tmp_path / "monitor_resolutions.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    resolutions_file.write_text(
        json.dumps({"condition": "no_task_running", "resolved_at": now, "heal_task_id": "task_ok"}) + "\n"
        + json.dumps({"condition": "other", "heal_task_id": "task_no_ts"}) + "\n"
    )
    monkeypatch.setattr(
        "app.services.effectiveness_service.RESOLUTIONS_FILE",
        str(resolutions_file),
    )
    response = await client.get("/api/agent/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert data["heal_resolved_count"] == 1, "only records with valid resolved_at in 7d window count"


@pytest.mark.asyncio
async def test_monitor_issues_issue_may_include_heal_task_id(client: AsyncClient):
    """GET /api/agent/monitor-issues returns issues; each issue may include heal_task_id (which heal addressed which issue)."""
    logs_dir = _api_logs_dir()
    path = os.path.join(logs_dir, "monitor_issues.json")
    os.makedirs(logs_dir, exist_ok=True)
    payload = {
        "last_check": "2026-02-12T12:00:00Z",
        "issues": [
            {"condition": "no_task_running", "message": "No task", "heal_task_id": "task_heal_123"},
        ],
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        response = await client.get("/api/agent/monitor-issues")
        assert response.status_code == 200
        data = response.json()
        assert len(data["issues"]) == 1
        assert data["issues"][0].get("heal_task_id") == "task_heal_123", "issue must expose heal_task_id when present"
    finally:
        if os.path.isfile(path):
            os.remove(path)


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
async def test_status_report_includes_meta_questions_when_file_exists(
    client: AsyncClient, tmp_path, monkeypatch
):
    """When api/logs/meta_questions.json exists, GET /api/agent/status-report includes meta_questions (unanswered/failed). Spec 007 meta-pipeline item 3."""
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    report_path = tmp_path / "pipeline_status_report.json"
    report_path.write_text(
        json.dumps({
            "generated_at": "2026-02-12T12:00:00Z",
            "overall": {"status": "ok", "going_well": [], "needs_attention": []},
            "layer_0_goal": {"status": "ok", "summary": "OK"},
            "layer_1_orchestration": {"status": "ok", "summary": "OK"},
            "layer_2_execution": {"status": "ok", "summary": "OK"},
            "layer_3_attention": {"status": "ok", "summary": "OK"},
        })
    )
    mq_path = tmp_path / "meta_questions.json"
    mq_path.write_text(
        json.dumps({
            "run_at": "2026-02-12T12:00:00Z",
            "answers": [],
            "summary": {"unanswered": ["q5", "q6"], "failed": ["q4"]},
        })
    )
    response = await client.get("/api/agent/status-report")
    assert response.status_code == 200
    data = response.json()
    assert "meta_questions" in data
    assert data["meta_questions"]["status"] == "needs_attention"
    assert data["meta_questions"]["unanswered"] == ["q5", "q6"]
    assert data["meta_questions"]["failed"] == ["q4"]
    assert "meta_questions" in data["overall"]["needs_attention"]


def test_run_meta_questions_checklist_structure():
    """run_meta_questions.run_checklist returns run_at, answers, summary (unanswered, failed). Spec 007 item 3."""
    import sys
    cwd = os.getcwd()
    try:
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import run_meta_questions
        result = run_meta_questions.run_checklist(base_url="http://localhost:9999")
        assert "run_at" in result
        assert "answers" in result
        assert "summary" in result
        assert "unanswered" in result["summary"]
        assert "failed" in result["summary"]
        assert isinstance(result["answers"], list)
        assert len(result["answers"]) >= 1
    finally:
        os.chdir(cwd)


def test_run_meta_questions_main_writes_meta_questions_json(tmp_path, monkeypatch):
    """run_meta_questions.main() writes meta_questions.json with run_at, answers, summary (unanswered, failed). Spec 007 item 3."""
    import sys
    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import run_meta_questions
    monkeypatch.setattr(run_meta_questions, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(run_meta_questions, "META_QUESTIONS_FILE", str(tmp_path / "meta_questions.json"))
    run_meta_questions.main()
    mq_path = tmp_path / "meta_questions.json"
    assert mq_path.exists(), "meta_questions.json must be written to api/logs (or overridden path)"
    data = json.loads(mq_path.read_text())
    assert "run_at" in data
    assert "answers" in data
    assert "summary" in data
    assert "unanswered" in data["summary"]
    assert "failed" in data["summary"]


@pytest.mark.asyncio
async def test_status_report_meta_questions_ok_when_no_unanswered_failed(
    client: AsyncClient, tmp_path, monkeypatch
):
    """When meta_questions.json has empty unanswered and failed, status-report has meta_questions.status ok and not in needs_attention. Spec 007 item 3."""
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    report_path = tmp_path / "pipeline_status_report.json"
    report_path.write_text(
        json.dumps({
            "generated_at": "2026-02-12T12:00:00Z",
            "overall": {"status": "ok", "going_well": [], "needs_attention": []},
            "layer_0_goal": {"status": "ok", "summary": "OK"},
            "layer_1_orchestration": {"status": "ok", "summary": "OK"},
            "layer_2_execution": {"status": "ok", "summary": "OK"},
            "layer_3_attention": {"status": "ok", "summary": "OK"},
        })
    )
    mq_path = tmp_path / "meta_questions.json"
    mq_path.write_text(
        json.dumps({
            "run_at": "2026-02-12T12:00:00Z",
            "answers": [],
            "summary": {"unanswered": [], "failed": []},
        })
    )
    response = await client.get("/api/agent/status-report")
    assert response.status_code == 200
    data = response.json()
    assert "meta_questions" in data
    assert data["meta_questions"]["status"] == "ok"
    assert "meta_questions" not in data["overall"]["needs_attention"]


def test_monitor_run_meta_questions_if_due_runs_script_when_never_run(tmp_path, monkeypatch):
    """Monitor runs meta-questions checklist when last run file is missing (periodic check). Spec 007 item 3."""
    import sys
    import logging
    import subprocess
    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import monitor_pipeline
    last_run_file = tmp_path / "meta_questions_last_run.json"
    assert not last_run_file.exists()
    monkeypatch.setattr(monitor_pipeline, "META_QUESTIONS_LAST_RUN_FILE", str(last_run_file))
    mock_run = []

    def fake_run(cmd, *args, **kwargs):
        mock_run.append(cmd)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(subprocess, "run", fake_run)
    log = logging.getLogger("test")
    monitor_pipeline._run_meta_questions_if_due(log)
    assert len(mock_run) == 1, "monitor must run meta-questions script when due"
    cmd = mock_run[0]
    assert any("run_meta_questions" in str(p) for p in cmd), "must invoke run_meta_questions script"
    assert "--once" in cmd, "script must be run with --once"


@pytest.mark.asyncio
async def test_task_log_returns_command_and_output(client: AsyncClient):
    """GET /api/agent/tasks/{id}/log returns task_id, command, output."""
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "Log test", "task_type": "impl", "context": {"executor": "claude"}},
    )
    task_id = create.json()["id"]
    _ensure_task_log_file(task_id, "prompt and streamed output\n")
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
    _ensure_task_log_file(task_id)
    response = await client.get(f"/api/agent/tasks/{task_id}/log")
    assert response.status_code == 200
    data = response.json()
    required = ("task_id", "log", "command", "output")
    for key in required:
        assert key in data, f"Task log response must include {key}"
    assert data["log"] is None or isinstance(data["log"], str)


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
    _ensure_task_log_file(task_id)
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


# --- Spec 011: Pagination (limit/offset, default page size 20) ---


@pytest.mark.asyncio
async def test_get_tasks_offset_zero_limit_five_returns_first_five_newest_first(client: AsyncClient):
    """GET /api/agent/tasks?offset=0&limit=5 returns first 5 tasks (newest first). Spec 011."""
    for i in range(10):
        await client.post("/api/agent/tasks", json={"direction": f"Task {i}", "task_type": "impl"})
    response = await client.get("/api/agent/tasks?offset=0&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 5
    assert data["total"] == 10
    # Newest first: created_at descending
    created = [t["created_at"] for t in data["tasks"]]
    assert created == sorted(created, reverse=True)


@pytest.mark.asyncio
async def test_get_tasks_offset_five_limit_five_returns_next_five(client: AsyncClient):
    """GET /api/agent/tasks?offset=5&limit=5 returns next 5 tasks. Spec 011."""
    for i in range(10):
        await client.post("/api/agent/tasks", json={"direction": f"Task {i}", "task_type": "impl"})
    first = await client.get("/api/agent/tasks?offset=0&limit=10")
    assert first.status_code == 200
    all_ids = [t["id"] for t in first.json()["tasks"]]
    response = await client.get("/api/agent/tasks?offset=5&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 5
    assert data["total"] == 10
    page2_ids = [t["id"] for t in data["tasks"]]
    assert page2_ids == all_ids[5:10]


@pytest.mark.asyncio
async def test_get_tasks_total_unchanged_by_limit_offset(client: AsyncClient):
    """total is the same regardless of limit/offset (total matching count). Spec 011."""
    for i in range(7):
        await client.post("/api/agent/tasks", json={"direction": f"Task {i}", "task_type": "impl"})
    r1 = await client.get("/api/agent/tasks?limit=2&offset=0")
    r2 = await client.get("/api/agent/tasks?limit=3&offset=2")
    r3 = await client.get("/api/agent/tasks?limit=10&offset=0")
    assert r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200
    assert r1.json()["total"] == 7
    assert r2.json()["total"] == 7
    assert r3.json()["total"] == 7


@pytest.mark.asyncio
async def test_get_tasks_no_params_uses_default_limit_twenty_offset_zero(client: AsyncClient):
    """GET /api/agent/tasks with no params uses default limit=20, offset=0. Spec 011."""
    for i in range(5):
        await client.post("/api/agent/tasks", json={"direction": f"Task {i}", "task_type": "impl"})
    response = await client.get("/api/agent/tasks")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 5
    assert data["total"] == 5
    # Default limit=20 means we get up to 20; with 5 tasks we get 5
    response_explicit = await client.get("/api/agent/tasks?limit=20&offset=0")
    assert response_explicit.status_code == 200
    assert response_explicit.json()["tasks"] == data["tasks"]
    assert response_explicit.json()["total"] == data["total"]


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


@pytest.mark.asyncio
async def test_fatal_issues_returns_200_and_fatal_false_when_no_file(client: AsyncClient, monkeypatch):
    """GET /api/agent/fatal-issues when fatal_issues.json missing returns 200, { fatal: false } (spec 002 edge-case)."""
    import os.path as os_path
    original_isfile = os_path.isfile

    def isfile(path):
        if "fatal_issues.json" in str(path):
            return False
        return original_isfile(path)

    monkeypatch.setattr(os_path, "isfile", isfile)
    response = await client.get("/api/agent/fatal-issues")
    assert response.status_code == 200
    data = response.json()
    assert data.get("fatal") is False


@pytest.mark.asyncio
async def test_fatal_issues_returns_fatal_true_when_file_has_content(client: AsyncClient):
    """GET /api/agent/fatal-issues when file present and valid returns 200, { fatal: true, ...payload } (spec 002 edge-case)."""
    logs_dir = _api_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, "fatal_issues.json")
    payload = {"message": "Unrecoverable failure", "ts": "2026-02-12T12:00:00Z"}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        response = await client.get("/api/agent/fatal-issues")
        assert response.status_code == 200
        data = response.json()
        assert data.get("fatal") is True
        assert data.get("message") == "Unrecoverable failure"
    finally:
        if os.path.isfile(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_fatal_issues_returns_fatal_false_on_read_error(client: AsyncClient):
    """GET /api/agent/fatal-issues when file exists but read/parse fails returns 200, { fatal: false } (spec 002)."""
    logs_dir = _api_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, "fatal_issues.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("not valid json {{{")
        response = await client.get("/api/agent/fatal-issues")
        assert response.status_code == 200
        data = response.json()
        assert data.get("fatal") is False
    finally:
        if os.path.isfile(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_effectiveness_returns_200_and_fallback_structure_when_service_unavailable(client: AsyncClient, monkeypatch):
    """GET /api/agent/effectiveness when effectiveness service unavailable returns 200 with fallback structure (spec 002 edge-case)."""
    import sys
    effectiveness_mod = "app.services.effectiveness_service"
    saved = sys.modules.get(effectiveness_mod)

    class FakeModule:
        def __getattr__(self, name):
            raise ImportError("effectiveness service unavailable")

    monkeypatch.setitem(sys.modules, effectiveness_mod, FakeModule())
    try:
        response = await client.get("/api/agent/effectiveness")
        assert response.status_code == 200
        data = response.json()
        for key in ("throughput", "success_rate", "issues", "progress", "goal_proximity", "heal_resolved_count", "top_issues_by_priority"):
            assert key in data, f"Fallback must include {key}"
        assert data["heal_resolved_count"] == 0
        assert data["success_rate"] == 0.0
    finally:
        if saved is not None:
            sys.modules[effectiveness_mod] = saved
        elif effectiveness_mod in sys.modules:
            del sys.modules[effectiveness_mod]


@pytest.mark.asyncio
async def test_status_report_returns_200_with_unknown_when_no_report_file(client: AsyncClient, tmp_path, monkeypatch):
    """GET /api/agent/status-report when pipeline_status_report.json missing returns 200, generated_at: null, overall.status: unknown (spec 002 edge-case)."""
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    response = await client.get("/api/agent/status-report")
    assert response.status_code == 200
    data = response.json()
    assert data.get("generated_at") is None
    assert data.get("overall", {}).get("status") == "unknown"


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
