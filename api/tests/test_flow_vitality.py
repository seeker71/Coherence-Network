"""Flow-centric tests for the Workspace Vitality API.

Tests the vitality endpoint as a user would experience it:
HTTP requests in, JSON out.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "ws") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_workspace(c: AsyncClient, ws_id: str | None = None) -> dict:
    """Create a workspace and return response JSON."""
    wid = ws_id or _uid()
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_idea(c: AsyncClient, idea_id: str, name: str, phase: str = "gas") -> dict:
    """Seed an idea."""
    r = await c.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": name,
            "description": f"Test idea: {name}",
            "potential_value": 100.0,
            "estimated_cost": 10.0,
        },
    )
    assert r.status_code in (200, 201, 409), r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: Vitality returns all signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitality_returns_all_signals():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        # Seed some data so vitality has something to measure
        await _seed_idea(c, f"vit-idea-{_uid()}", "Vitality Test Idea")

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["workspace_id"] == ws_id
        assert "vitality_score" in body
        assert "signals" in body
        assert "health_description" in body
        assert "generated_at" in body

        signals = body["signals"]
        assert "diversity_index" in signals
        assert "resonance_density" in signals
        assert "flow_rate" in signals
        assert "breath_rhythm" in signals
        assert "connection_strength" in signals
        assert "activity_pulse" in signals

        # Breath rhythm has sub-keys
        br = signals["breath_rhythm"]
        assert "gas" in br
        assert "water" in br
        assert "ice" in br


# ---------------------------------------------------------------------------
# Test 2: Vitality score is 0.0-1.0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitality_score_range():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        score = body["vitality_score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Test 3: Health description is non-empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_description_non_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        desc = body["health_description"]
        assert isinstance(desc, str)
        assert len(desc) > 0
