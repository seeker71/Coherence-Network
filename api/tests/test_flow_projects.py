"""Flow-centric tests for Workspace Projects (Phase 4: Project Grouping).

Covers:
  1. Create project in workspace -> appears in list
  2. Add idea to project -> idea appears in project detail
  3. Remove idea from project -> no longer in project
  4. Cross-workspace idea rejected -> 400
  5. Delete project -> gone, ideas unaffected
  6. Idea belongs to multiple projects -> both shown
  7. List projects for idea -> correct list
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_workspace(c: AsyncClient, ws_id: str) -> dict:
    r = await c.post("/api/workspaces", json={"id": ws_id, "name": f"WS {ws_id}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_idea(c: AsyncClient, idea_id: str, workspace_id: str) -> dict:
    r = await c.post("/api/ideas", json={
        "id": idea_id,
        "name": f"Idea {idea_id}",
        "description": "Test idea.",
        "potential_value": 10.0,
        "estimated_cost": 1.0,
        "confidence": 0.5,
        "workspace_id": workspace_id,
    })
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Create project in workspace -> appears in list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_project_and_list():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)

        r = await c.post(
            f"/api/workspaces/{ws_id}/projects",
            json={"name": "Alpha", "description": "First project", "workspace_id": ws_id},
            headers=AUTH,
        )
        assert r.status_code == 201, r.text
        proj = r.json()
        assert proj["name"] == "Alpha"
        assert proj["workspace_id"] == ws_id
        assert proj["idea_count"] == 0

        r2 = await c.get(f"/api/workspaces/{ws_id}/projects")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["total"] >= 1
        ids = {p["id"] for p in body["projects"]}
        assert proj["id"] in ids


# ---------------------------------------------------------------------------
# 2. Add idea to project -> idea appears in project detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_idea_to_project():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_id)

        r = await c.post(
            f"/api/workspaces/{ws_id}/projects",
            json={"name": "Beta", "workspace_id": ws_id},
            headers=AUTH,
        )
        assert r.status_code == 201, r.text
        proj_id = r.json()["id"]

        r2 = await c.post(
            f"/api/projects/{proj_id}/ideas",
            json={"idea_id": idea_id},
            headers=AUTH,
        )
        assert r2.status_code == 201, r2.text

        r3 = await c.get(f"/api/projects/{proj_id}")
        assert r3.status_code == 200, r3.text
        detail = r3.json()
        assert detail["idea_count"] == 1
        idea_ids = {i["id"] for i in detail["ideas"]}
        assert idea_id in idea_ids


# ---------------------------------------------------------------------------
# 3. Remove idea from project -> no longer in project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_idea_from_project():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_id)

        r = await c.post(
            f"/api/workspaces/{ws_id}/projects",
            json={"name": "Gamma", "workspace_id": ws_id},
            headers=AUTH,
        )
        proj_id = r.json()["id"]

        await c.post(
            f"/api/projects/{proj_id}/ideas",
            json={"idea_id": idea_id},
            headers=AUTH,
        )

        r2 = await c.delete(
            f"/api/projects/{proj_id}/ideas/{idea_id}",
            headers=AUTH,
        )
        assert r2.status_code == 204, r2.text

        r3 = await c.get(f"/api/projects/{proj_id}")
        assert r3.status_code == 200, r3.text
        assert r3.json()["idea_count"] == 0
        assert len(r3.json()["ideas"]) == 0


# ---------------------------------------------------------------------------
# 4. Cross-workspace idea rejected -> 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_workspace_idea_rejected():
    ws_a = _uid("ws")
    ws_b = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_a)
        await _create_workspace(c, ws_b)

        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_b)

        r = await c.post(
            f"/api/workspaces/{ws_a}/projects",
            json={"name": "Cross", "workspace_id": ws_a},
            headers=AUTH,
        )
        proj_id = r.json()["id"]

        r2 = await c.post(
            f"/api/projects/{proj_id}/ideas",
            json={"idea_id": idea_id},
            headers=AUTH,
        )
        assert r2.status_code == 400, r2.text
        assert "cross-workspace" in r2.json()["detail"].lower() or "Cross-workspace" in r2.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Delete project -> gone, ideas unaffected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_project_ideas_unaffected():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_id)

        r = await c.post(
            f"/api/workspaces/{ws_id}/projects",
            json={"name": "Ephemeral", "workspace_id": ws_id},
            headers=AUTH,
        )
        proj_id = r.json()["id"]

        await c.post(
            f"/api/projects/{proj_id}/ideas",
            json={"idea_id": idea_id},
            headers=AUTH,
        )

        r2 = await c.delete(f"/api/projects/{proj_id}", headers=AUTH)
        assert r2.status_code == 204, r2.text

        # Project is gone
        r3 = await c.get(f"/api/projects/{proj_id}")
        assert r3.status_code == 404, r3.text

        # Idea still exists
        r4 = await c.get(f"/api/ideas/{idea_id}")
        assert r4.status_code == 200, r4.text


# ---------------------------------------------------------------------------
# 6. Idea belongs to multiple projects -> both shown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_in_multiple_projects():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_id)

        proj_ids = []
        for name in ("Multi-A", "Multi-B"):
            r = await c.post(
                f"/api/workspaces/{ws_id}/projects",
                json={"name": name, "workspace_id": ws_id},
                headers=AUTH,
            )
            assert r.status_code == 201, r.text
            proj_ids.append(r.json()["id"])

        for pid in proj_ids:
            r = await c.post(
                f"/api/projects/{pid}/ideas",
                json={"idea_id": idea_id},
                headers=AUTH,
            )
            assert r.status_code == 201, r.text

        # Both projects show the idea
        for pid in proj_ids:
            r = await c.get(f"/api/projects/{pid}")
            assert r.status_code == 200, r.text
            idea_ids = {i["id"] for i in r.json()["ideas"]}
            assert idea_id in idea_ids


# ---------------------------------------------------------------------------
# 7. List projects for idea -> correct list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects_for_idea():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        idea_id = _uid("idea")
        await _create_idea(c, idea_id, ws_id)

        proj_ids = []
        for name in ("For-Idea-A", "For-Idea-B"):
            r = await c.post(
                f"/api/workspaces/{ws_id}/projects",
                json={"name": name, "workspace_id": ws_id},
                headers=AUTH,
            )
            assert r.status_code == 201, r.text
            proj_ids.append(r.json()["id"])

        for pid in proj_ids:
            await c.post(
                f"/api/projects/{pid}/ideas",
                json={"idea_id": idea_id},
                headers=AUTH,
            )

        r2 = await c.get(f"/api/ideas/{idea_id}/projects")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["total"] == 2
        returned_ids = {p["id"] for p in body["projects"]}
        assert set(proj_ids) == returned_ids
