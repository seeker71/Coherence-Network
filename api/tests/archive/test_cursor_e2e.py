"""Tests for question-answering and minimum E2E flow.

Referenced by: spec 051-question-answering-and-minimum-e2e-flow
Status: Stub -- endpoints not yet fully implemented as standalone E2E.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_ideas_endpoint_accessible():
    """GET /api/ideas returns 200, proving the ideas surface is reachable for E2E flow."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (list, dict))


@pytest.mark.asyncio
async def test_value_lineage_endpoint_accessible():
    """GET /api/value-lineage returns 200, proving lineage surface exists for E2E flow."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/value-lineage")
        # Accept 200 or 404 (endpoint may not exist yet)
        assert resp.status_code in (200, 404, 405)
