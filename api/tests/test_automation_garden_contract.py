"""
Contract tests for the /automation garden page data sources (idea idea-c3731991380b).

The web page at GET /automation (Next) consumes these API shapes; this module locks
the minimum fields the garden visualization expects.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_automation_usage_contract_for_garden():
    """GET /api/automation/usage returns generated_at and providers[] for the garden."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/automation/usage", params={"force_refresh": "true"})
    assert res.status_code == 200
    body = res.json()
    assert "generated_at" in body
    assert isinstance(body.get("generated_at"), str)
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert "tracked_providers" in body


@pytest.mark.asyncio
async def test_automation_readiness_and_validation_contract():
    """Readiness and validation endpoints return boolean gates used by the proof strip."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/api/automation/usage/readiness", params={"force_refresh": "true"})
        r2 = await client.get(
            "/api/automation/usage/provider-validation",
            params={"runtime_window_seconds": 86400, "min_execution_events": 1, "force_refresh": "true"},
        )
    assert r1.status_code == 200
    b1 = r1.json()
    assert "all_required_ready" in b1
    assert isinstance(b1["all_required_ready"], bool)
    assert r2.status_code == 200
    b2 = r2.json()
    assert "all_required_validated" in b2
    assert isinstance(b2["all_required_validated"], bool)


@pytest.mark.asyncio
async def test_providers_stats_optional_contract():
    """GET /api/providers/stats returns providers map when available (garden gauges)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/providers/stats")
    assert res.status_code == 200
    body = res.json()
    assert "providers" in body or "summary" in body


@pytest.mark.asyncio
async def test_automation_alerts_invalid_threshold_not_500():
    """Bad threshold must not explode server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/automation/usage/alerts", params={"threshold_ratio": 2.0})
    assert res.status_code != 500
