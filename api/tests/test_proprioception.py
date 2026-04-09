"""Flow-centric integration tests for the Proprioception (auto-sensing) feature.

Tests the proprioception API as a user would: HTTP requests in, JSON out.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Test 1: GET /api/proprioception returns report with all sections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proprioception_returns_report_with_all_sections():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/proprioception")
        assert r.status_code == 200, r.text
        data = r.json()

        # All required top-level keys
        assert "timestamp" in data
        assert "workspace_id" in data
        assert "specs" in data
        assert "ideas" in data
        assert "endpoints" in data
        assert "health" in data

        # Specs section structure
        specs = data["specs"]
        assert "sensed" in specs
        assert "updated" in specs
        assert "with_source" in specs
        assert "missing_source" in specs

        # Ideas section structure
        ideas = data["ideas"]
        assert "sensed" in ideas
        assert "advanced" in ideas
        assert "suggestions" in ideas
        assert isinstance(ideas["suggestions"], list)

        # Endpoints section structure
        endpoints = data["endpoints"]
        assert "checked" in endpoints
        assert "alive" in endpoints

        # Health is one of the expected values
        assert data["health"] in ("strong", "growing", "needs_attention")


# ---------------------------------------------------------------------------
# Test 2: Report has specs.sensed > 0 (some specs are registered)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proprioception_specs_sensed_count():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Ensure at least one spec exists
        spec_id = _uid("spec")
        create_r = await c.post("/api/spec-registry", json={
            "spec_id": spec_id,
            "title": f"Test Spec {spec_id}",
            "summary": "A test spec for proprioception sensing",
            "potential_value": 10.0,
        }, headers=AUTH)
        assert create_r.status_code == 201, create_r.text

        r = await c.get("/api/proprioception")
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["specs"]["sensed"] > 0, "Expected at least one spec to be sensed"


# ---------------------------------------------------------------------------
# Test 3: Endpoints section shows alive count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proprioception_endpoints_alive():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/proprioception")
        assert r.status_code == 200, r.text
        data = r.json()

        endpoints = data["endpoints"]
        assert endpoints["checked"] > 0, "Expected at least one endpoint to be checked"
        assert endpoints["alive"] > 0, "Expected at least one endpoint to be alive"
        assert endpoints["alive"] <= endpoints["checked"]


# ---------------------------------------------------------------------------
# Test 4: POST /api/proprioception/apply requires API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proprioception_apply_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/proprioception/apply")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test 5: POST /api/proprioception/apply with auth returns results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proprioception_apply_with_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/proprioception/apply", headers=AUTH)
        assert r.status_code == 200, r.text
        data = r.json()

        assert "applied_specs" in data
        assert "applied_ideas" in data
        assert "report" in data
        assert isinstance(data["applied_specs"], int)
        assert isinstance(data["applied_ideas"], int)
