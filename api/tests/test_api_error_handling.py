"""Tests for API error handling — spec 009.

These tests define the contract for 422 validation, 404 consistency, and error schema.
Do not modify tests to make implementation pass; fix the implementation instead.

Contract (spec 009):
- 422: FastAPI default; detail is array of { loc, msg, type }.
- 404: Single top-level key "detail" (string); no extra keys; message resource-specific.
- 400/500: Same as 404 — { "detail": "string" } only.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Client with raise_app_exceptions=False so 4xx/5xx return response body."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- 422 validation (spec 009) ---


@pytest.mark.asyncio
async def test_spec_009_422_response_has_detail_array(client: AsyncClient):
    """422 validation responses have top-level detail as array (spec 009)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "x", "task_type": "invalid_enum"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list), "422 detail must be array (FastAPI default)"


@pytest.mark.asyncio
async def test_spec_009_422_each_item_has_loc_msg_type(client: AsyncClient):
    """422 detail array items have at least loc, msg, type (spec 009)."""
    response = await client.post(
        "/api/agent/tasks",
        json={"direction": "", "task_type": "impl"},
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) >= 1
    for item in data["detail"]:
        assert "loc" in item, "422 detail item must have loc"
        assert "msg" in item, "422 detail item must have msg"
        assert "type" in item, "422 detail item must have type"
        assert isinstance(item["loc"], list)
        assert isinstance(item["msg"], str)
        assert isinstance(item["type"], str)


# --- 404 consistency (spec 009) ---


@pytest.mark.asyncio
async def test_spec_009_404_response_has_only_detail_key(client: AsyncClient):
    """404 responses have exactly one top-level key 'detail' (spec 009)."""
    # Projects
    r_projects = await client.get("/api/projects/npm/nonexistent")
    assert r_projects.status_code == 404
    body_p = r_projects.json()
    assert list(body_p.keys()) == ["detail"], "404 must have no extra keys"
    assert isinstance(body_p["detail"], str)

    # Agent
    r_agent = await client.get("/api/agent/tasks/task_nonexistent")
    assert r_agent.status_code == 404
    body_a = r_agent.json()
    assert list(body_a.keys()) == ["detail"], "404 must have no extra keys"
    assert isinstance(body_a["detail"], str)


@pytest.mark.asyncio
async def test_spec_009_404_projects_message(client: AsyncClient):
    """404 for missing project returns detail 'Project not found' (spec 009)."""
    response = await client.get("/api/projects/npm/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_spec_009_404_agent_message(client: AsyncClient):
    """404 for missing task returns detail 'Task not found' (spec 009)."""
    response = await client.get("/api/agent/tasks/task_nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


# --- Error schema 400/404/500: detail string only (spec 009) ---


@pytest.mark.asyncio
async def test_spec_009_500_response_has_only_detail_string(client: AsyncClient):
    """500 responses have only 'detail' (string); no stack trace (spec 009)."""
    response = await client.get("/api/_test_500")
    assert response.status_code == 500
    body = response.json()
    assert list(body.keys()) == ["detail"], "500 must have no extra keys"
    assert body["detail"] == "Internal server error"
    assert isinstance(body["detail"], str)
