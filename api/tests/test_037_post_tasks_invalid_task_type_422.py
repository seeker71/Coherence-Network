"""Tests for spec 037: POST /api/agent/tasks — Invalid task_type Returns 422.

Covers all acceptance criteria from specs/037-post-tasks-invalid-task-type-422.md:
- R1: Invalid task_type returns HTTP 422
- R2: Response has detail list with loc/msg/type fields
- R3: No task created when 422 is returned
- R4: Valid task_type returns 201
- Scenarios: string invalid, uppercase, numeric, null, missing field
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_422_on_invalid_task_type_string():
    """Scenario 1: Invalid string task_type returns 422 with structured detail (R1, R2)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "INVALID_TYPE", "direction": "test direction"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert len(body["detail"]) > 0
    for item in body["detail"]:
        assert "loc" in item
        assert "msg" in item
        assert "type" in item


@pytest.mark.asyncio
async def test_422_detail_references_task_type_field():
    """R2: At least one detail item must reference task_type in its loc array."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "notreal", "direction": "test direction"},
        )
    assert resp.status_code == 422
    body = resp.json()
    locs = [item.get("loc", []) for item in body["detail"]]
    assert any("task_type" in loc for loc in locs), (
        f"Expected 'task_type' in at least one loc, got: {locs}"
    )


@pytest.mark.asyncio
async def test_422_on_uppercase_task_type():
    """Edge case: 'SPEC' (uppercase) is invalid — enum is case-sensitive."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "SPEC", "direction": "test direction"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_422_on_numeric_task_type():
    """Scenario 4: Numeric task_type returns 422 (not 500)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": 42, "direction": "numeric task_type"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)


@pytest.mark.asyncio
async def test_422_on_null_task_type():
    """Known gap: null task_type should also return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": None, "direction": "null task_type"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)


@pytest.mark.asyncio
async def test_422_on_missing_task_type():
    """Scenario 5: Missing task_type field returns 422 with task_type in loc."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"direction": "missing task_type field"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    locs = [item.get("loc", []) for item in body["detail"]]
    assert any("task_type" in loc for loc in locs), (
        f"Expected 'task_type' in at least one loc, got: {locs}"
    )


@pytest.mark.asyncio
async def test_valid_task_type_returns_201():
    """R4: Valid task_type 'impl' with valid direction returns 201."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "impl", "direction": "Implement the feature described in spec 037."},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["task_type"] == "impl"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_no_task_created_on_422():
    """R3: Task count unchanged after a 422 rejection."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get baseline count
        count_resp = await client.get("/api/agent/tasks")
        assert count_resp.status_code == 200
        before_count = len(count_resp.json())

        # Send invalid request
        invalid_resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "notreal", "direction": "should not persist"},
        )
        assert invalid_resp.status_code == 422

        # Count should be unchanged
        count_resp2 = await client.get("/api/agent/tasks")
        assert count_resp2.status_code == 200
        after_count = len(count_resp2.json())

    assert before_count == after_count, (
        f"Task count changed after 422: before={before_count}, after={after_count}"
    )


@pytest.mark.asyncio
async def test_422_detail_is_list_not_string():
    """R2: detail must be a list, not a plain string."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "foo", "direction": "test direction"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list), (
        f"Expected detail to be a list, got: {type(body['detail'])}"
    )


@pytest.mark.asyncio
async def test_all_valid_task_types_succeed():
    """R4: Every valid TaskType value must return 201 (regression guard for enum completeness)."""
    valid_types = ["spec", "test", "impl", "review", "heal", "code-review",
                   "merge", "deploy", "verify", "reflect"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for task_type in valid_types:
            resp = await client.post(
                "/api/agent/tasks",
                json={"task_type": task_type, "direction": f"Regression test for task_type={task_type}"},
            )
            assert resp.status_code == 201, (
                f"Expected 201 for task_type={task_type!r}, got {resp.status_code}: {resp.text}"
            )
