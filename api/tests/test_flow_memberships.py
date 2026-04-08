"""Flow-centric tests for workspace membership (team edges).

Covers:
  - Owner auto-membership on workspace creation
  - Direct member add
  - Invite flow (pending -> accept -> active)
  - List members / list workspaces for contributor
  - Remove member
  - Get member role
  - Error cases: non-existent workspace, non-pending invite
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


def _make_contributor_id() -> str:
    return _uid("contrib")


async def _create_contributor(c: AsyncClient, contributor_id: str, name: str = "Test User"):
    """Create a contributor node via the graph."""
    from app.services import graph_service
    graph_service.create_node(
        id=f"contributor:{contributor_id}",
        type="contributor",
        name=name,
        description=f"Test contributor {contributor_id}",
    )


async def _create_workspace(c: AsyncClient, ws_id: str, name: str = "Test WS"):
    r = await c.post("/api/workspaces", json={
        "id": ws_id,
        "name": name,
        "description": "A test workspace.",
        "pillars": ["alpha"],
        "visibility": "public",
    })
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Create workspace with owner -> owner appears in members list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workspace_with_owner_auto_membership():
    """When a workspace is created with owner_contributor_id, the owner
    appears in the members list with role=owner."""
    ws_id = _uid("ws")
    owner_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_contributor(c, owner_id, "Owner User")

        r = await c.post("/api/workspaces", json={
            "id": ws_id,
            "name": "Owned WS",
            "description": "Has an owner.",
            "pillars": ["alpha"],
            "visibility": "public",
            "owner_contributor_id": owner_id,
        })
        assert r.status_code == 201, r.text

        # Check membership
        r2 = await c.get(f"/api/workspaces/{ws_id}/members")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["workspace_id"] == ws_id
        members = body["members"]
        owner_members = [m for m in members if m["role"] == "owner"]
        assert len(owner_members) == 1
        assert owner_members[0]["contributor_id"] == owner_id
        assert owner_members[0]["status"] == "active"


# ---------------------------------------------------------------------------
# 2. Invite contributor -> appears with status=pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_contributor_pending():
    ws_id = _uid("ws")
    invitee_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        await _create_contributor(c, invitee_id, "Invitee")

        r = await c.post(
            f"/api/workspaces/{ws_id}/invite",
            json={"contributor_id": invitee_id, "role": "member"},
            headers=AUTH,
        )
        assert r.status_code == 201, r.text
        invite = r.json()
        assert invite["status"] == "pending"
        assert invite["contributor_id"] == invitee_id
        assert invite["workspace_id"] == ws_id
        assert invite["role"] == "member"
        assert "invite_id" in invite


# ---------------------------------------------------------------------------
# 3. Accept invite -> status becomes active, joined_at set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invite_becomes_active():
    ws_id = _uid("ws")
    invitee_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        await _create_contributor(c, invitee_id, "Invitee")

        # Invite
        r = await c.post(
            f"/api/workspaces/{ws_id}/invite",
            json={"contributor_id": invitee_id},
            headers=AUTH,
        )
        assert r.status_code == 201, r.text

        # Accept
        r2 = await c.post(
            f"/api/workspaces/{ws_id}/invite/{invitee_id}/accept",
            headers=AUTH,
        )
        assert r2.status_code == 200, r2.text
        member = r2.json()
        assert member["status"] == "active"
        assert member["joined_at"] is not None
        assert member["contributor_id"] == invitee_id


# ---------------------------------------------------------------------------
# 4. List members -> shows both owner and new member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_members_shows_owner_and_member():
    ws_id = _uid("ws")
    owner_id = _make_contributor_id()
    member_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_contributor(c, owner_id, "Owner")
        await _create_contributor(c, member_id, "Member")

        await c.post("/api/workspaces", json={
            "id": ws_id,
            "name": "Team WS",
            "pillars": ["alpha"],
            "owner_contributor_id": owner_id,
        })

        # Add member
        await c.post(
            f"/api/workspaces/{ws_id}/members",
            json={"contributor_id": member_id, "role": "member"},
            headers=AUTH,
        )

        r = await c.get(f"/api/workspaces/{ws_id}/members")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        ids = {m["contributor_id"] for m in body["members"]}
        assert owner_id in ids
        assert member_id in ids


# ---------------------------------------------------------------------------
# 5. Contributor lists their workspaces -> workspace appears
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contributor_lists_workspaces():
    ws_id = _uid("ws")
    contributor_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id, "My WS")
        await _create_contributor(c, contributor_id, "Some User")

        await c.post(
            f"/api/workspaces/{ws_id}/members",
            json={"contributor_id": contributor_id, "role": "admin"},
            headers=AUTH,
        )

        r = await c.get(f"/api/contributors/{contributor_id}/workspaces")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] >= 1
        ws_ids = {w["workspace_id"] for w in body["workspaces"]}
        assert ws_id in ws_ids
        # Check the role is preserved
        ws_entry = [w for w in body["workspaces"] if w["workspace_id"] == ws_id][0]
        assert ws_entry["role"] == "admin"


# ---------------------------------------------------------------------------
# 6. Remove member -> no longer in list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_member():
    ws_id = _uid("ws")
    member_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        await _create_contributor(c, member_id, "To Remove")

        await c.post(
            f"/api/workspaces/{ws_id}/members",
            json={"contributor_id": member_id},
            headers=AUTH,
        )

        # Verify member is present
        r = await c.get(f"/api/workspaces/{ws_id}/members")
        assert any(m["contributor_id"] == member_id for m in r.json()["members"])

        # Remove
        r2 = await c.delete(
            f"/api/workspaces/{ws_id}/members/{member_id}",
            headers=AUTH,
        )
        assert r2.status_code == 204, r2.text

        # Verify removed
        r3 = await c.get(f"/api/workspaces/{ws_id}/members")
        assert not any(m["contributor_id"] == member_id for m in r3.json()["members"])


# ---------------------------------------------------------------------------
# 7. Get member role -> returns correct role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_member_role():
    ws_id = _uid("ws")
    member_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        await _create_contributor(c, member_id, "Viewer")

        await c.post(
            f"/api/workspaces/{ws_id}/members",
            json={"contributor_id": member_id, "role": "viewer"},
            headers=AUTH,
        )

        r = await c.get(f"/api/workspaces/{ws_id}/members/{member_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "viewer"
        assert body["workspace_id"] == ws_id
        assert body["contributor_id"] == member_id


# ---------------------------------------------------------------------------
# 8. Invite to non-existent workspace -> 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_to_nonexistent_workspace_404():
    contributor_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_contributor(c, contributor_id, "Stray")

        r = await c.post(
            "/api/workspaces/does-not-exist/invite",
            json={"contributor_id": contributor_id},
            headers=AUTH,
        )
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 9. Accept non-pending invite -> 400 or 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_nonpending_invite_error():
    ws_id = _uid("ws")
    contributor_id = _make_contributor_id()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_workspace(c, ws_id)
        await _create_contributor(c, contributor_id, "Nobody")

        # No invite exists — accept should fail
        r = await c.post(
            f"/api/workspaces/{ws_id}/invite/{contributor_id}/accept",
            headers=AUTH,
        )
        assert r.status_code in (400, 404), r.text
