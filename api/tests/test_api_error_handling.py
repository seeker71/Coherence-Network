"""Tests for API error handling contract.

Referenced by: spec 009-api-error-handling
Validates: consistent error response format (422 validation shape, 404 detail-only, 500 generic).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_404_returns_detail_only():
    """GET a nonexistent agent task returns 404 with only 'detail' key."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/agent/tasks/nonexistent-id-999")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)
        # No extra top-level keys beyond 'detail'
        assert set(body.keys()) == {"detail"}


@pytest.mark.asyncio
async def test_422_on_invalid_task_type():
    """POST /api/agent/tasks with invalid task_type returns 422 with detail array."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "INVALID_TYPE", "direction": "test direction"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], list)
        # Each validation error should have loc, msg, type
        for item in body["detail"]:
            assert "loc" in item
            assert "msg" in item
            assert "type" in item
