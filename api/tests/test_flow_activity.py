"""Flow-centric tests for workspace activity feeds.

Tests the activity API as a user would experience it: HTTP requests in, JSON out.
No internal service imports beyond what's needed for setup.
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
    """Helper: create a workspace and return response JSON."""
    wid = ws_id or _uid()
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _record_event(workspace_id: str, event_type: str = "idea_created", **kwargs) -> dict | None:
    """Helper: record an activity event via the service layer."""
    from app.services import activity_service

    return activity_service.record_event(
        workspace_id=workspace_id,
        event_type=event_type,
        summary=kwargs.get("summary", f"Test event {uuid4().hex[:6]}"),
        actor_contributor_id=kwargs.get("actor_contributor_id"),
        subject_type=kwargs.get("subject_type"),
        subject_id=kwargs.get("subject_id"),
        subject_name=kwargs.get("subject_name"),
    )


# ---------------------------------------------------------------------------
# Test 1: Record activity event -> appears in workspace feed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_event_appears_in_feed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        await _record_event(ws_id, "idea_created", summary="Created idea X")

        r = await c.get(f"/api/workspaces/{ws_id}/activity")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["workspace_id"] == ws_id
        assert body["total"] >= 1
        assert len(body["events"]) >= 1

        event = body["events"][0]
        assert event["event_type"] == "idea_created"
        assert "Created idea X" in event["summary"]
        assert event["workspace_id"] == ws_id


# ---------------------------------------------------------------------------
# Test 2: Activity feed respects workspace isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws_a = await _create_workspace(c)
        ws_b = await _create_workspace(c)

        await _record_event(ws_a["id"], "idea_created", summary="Event in A")
        await _record_event(ws_b["id"], "spec_created", summary="Event in B")

        r_a = await c.get(f"/api/workspaces/{ws_a['id']}/activity")
        assert r_a.status_code == 200
        body_a = r_a.json()
        event_types_a = [e["event_type"] for e in body_a["events"]]
        assert "idea_created" in event_types_a
        assert "spec_created" not in event_types_a

        r_b = await c.get(f"/api/workspaces/{ws_b['id']}/activity")
        assert r_b.status_code == 200
        body_b = r_b.json()
        event_types_b = [e["event_type"] for e in body_b["events"]]
        assert "spec_created" in event_types_b
        assert "idea_created" not in event_types_b


# ---------------------------------------------------------------------------
# Test 3: Event type filter works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_type_filter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        await _record_event(ws_id, "idea_created", summary="Idea event")
        await _record_event(ws_id, "task_completed", summary="Task event")
        await _record_event(ws_id, "member_joined", summary="Member event")

        # Filter by task_completed
        r = await c.get(
            f"/api/workspaces/{ws_id}/activity",
            params={"event_type": "task_completed"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert all(e["event_type"] == "task_completed" for e in body["events"])

        # Filter by idea_created
        r2 = await c.get(
            f"/api/workspaces/{ws_id}/activity",
            params={"event_type": "idea_created"},
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["total"] == 1
        assert body2["events"][0]["event_type"] == "idea_created"


# ---------------------------------------------------------------------------
# Test 4: Summary counts events correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_counts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        await _record_event(ws_id, "idea_created", summary="Idea 1")
        await _record_event(ws_id, "idea_created", summary="Idea 2")
        await _record_event(ws_id, "task_completed", summary="Task 1")

        r = await c.get(f"/api/workspaces/{ws_id}/activity/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["workspace_id"] == ws_id
        assert body["period_days"] == 7
        counts = body["event_counts"]
        assert counts.get("idea_created", 0) == 2
        assert counts.get("task_completed", 0) == 1


# ---------------------------------------------------------------------------
# Test 5: Pagination works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        # Record 5 events
        for i in range(5):
            await _record_event(ws_id, "idea_created", summary=f"Idea {i}")

        # Page 1: limit=2, offset=0
        r1 = await c.get(
            f"/api/workspaces/{ws_id}/activity",
            params={"limit": 2, "offset": 0},
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert len(body1["events"]) == 2
        assert body1["total"] == 5
        assert body1["has_more"] is True

        # Page 2: limit=2, offset=2
        r2 = await c.get(
            f"/api/workspaces/{ws_id}/activity",
            params={"limit": 2, "offset": 2},
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert len(body2["events"]) == 2
        assert body2["has_more"] is True

        # Page 3: limit=2, offset=4
        r3 = await c.get(
            f"/api/workspaces/{ws_id}/activity",
            params={"limit": 2, "offset": 4},
        )
        assert r3.status_code == 200
        body3 = r3.json()
        assert len(body3["events"]) == 1
        assert body3["has_more"] is False

        # Verify no duplicate IDs across pages
        all_ids = (
            [e["id"] for e in body1["events"]]
            + [e["id"] for e in body2["events"]]
            + [e["id"] for e in body3["events"]]
        )
        assert len(all_ids) == len(set(all_ids)), "Duplicate event IDs across pages"
