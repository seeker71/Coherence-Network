"""Flow-centric integration tests for Cross-Domain Bridge Notifications.

Tests the bridge notification API as a user would: HTTP requests in, JSON out.
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


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    """Helper: create an idea and return the response JSON."""
    iid = idea_id or _uid("idea")
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Description for {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _create_workspace(c: AsyncClient, ws_id: str | None = None) -> dict:
    """Helper: create a workspace and return response JSON."""
    wid = ws_id or _uid("ws")
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: POST /api/discover/notify-bridges returns count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_bridges_returns_count():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create diverse ideas to trigger cross-domain resonance
        await _create_idea(c, tags=["biology", "symbiosis", "evolution"])
        await _create_idea(c, tags=["software", "microservice", "api"])
        await _create_idea(c, tags=["physics", "quantum", "energy"])

        r = await c.post(
            "/api/discover/notify-bridges",
            headers=AUTH,
            params={"min_coherence": 0.08},
        )
        assert r.status_code == 200, r.text
        data = r.json()

        assert "new_bridges_notified" in data
        assert isinstance(data["new_bridges_notified"], int)
        assert data["new_bridges_notified"] >= 0
        assert "workspace_id" in data


# ---------------------------------------------------------------------------
# Test 2: Activity feed shows bridge events after notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_events_appear_in_activity():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        # Create diverse ideas
        await _create_idea(c, tags=["biology", "symbiosis", "evolution", "cell"])
        await _create_idea(c, tags=["software", "microservice", "api", "architecture"])
        await _create_idea(c, tags=["physics", "quantum", "wave", "frequency"])

        # Trigger bridge notifications for this workspace
        r = await c.post(
            "/api/discover/notify-bridges",
            headers=AUTH,
            params={"workspace_id": ws_id, "min_coherence": 0.08},
        )
        assert r.status_code == 200, r.text
        bridge_data = r.json()
        count = bridge_data["new_bridges_notified"]

        # If bridges were found, check they appear in the activity feed
        if count > 0:
            r2 = await c.get(f"/api/workspaces/{ws_id}/activity")
            assert r2.status_code == 200, r2.text
            body = r2.json()

            bridge_events = [
                e for e in body.get("events", [])
                if e.get("event_type") == "cross_domain_bridge"
            ]
            assert len(bridge_events) >= 1, "Expected at least one bridge event in activity feed"
            # Verify the event has the right structure
            evt = bridge_events[0]
            assert evt.get("subject_type") == "resonance_pair"
            assert "<>" in evt.get("summary", ""), "Bridge summary should contain <> pair notation"


# ---------------------------------------------------------------------------
# Test 3: Notify bridges requires API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_bridges_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/discover/notify-bridges")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test 4: Duplicate bridge notifications are suppressed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_bridges_deduplicates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        await _create_idea(c, tags=["biology", "symbiosis", "organism"])
        await _create_idea(c, tags=["software", "microservice", "system"])

        # First call — may or may not find bridges
        r1 = await c.post(
            "/api/discover/notify-bridges",
            headers=AUTH,
            params={"workspace_id": ws_id, "min_coherence": 0.08},
        )
        assert r1.status_code == 200
        count1 = r1.json()["new_bridges_notified"]

        # Second call — should find zero new bridges (all already notified)
        r2 = await c.post(
            "/api/discover/notify-bridges",
            headers=AUTH,
            params={"workspace_id": ws_id, "min_coherence": 0.08},
        )
        assert r2.status_code == 200
        count2 = r2.json()["new_bridges_notified"]

        assert count2 == 0, f"Second call should find 0 new bridges, got {count2}"
