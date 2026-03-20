"""Tests for release gates and public validation gates API.

Referenced by: spec 051-release-gates, spec 113-public-validation-gates-api
Validates: gate check endpoints return expected shapes.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_main_head_gate_returns_200():
    """GET /api/gates/main-head returns repo/branch/sha structure."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gates/main-head")
        assert resp.status_code == 200
        body = resp.json()
        assert "sha" in body
        assert isinstance(body["sha"], str)


@pytest.mark.asyncio
async def test_pr_to_public_gate_requires_branch():
    """GET /api/gates/pr-to-public without branch param returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gates/pr-to-public")
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body
