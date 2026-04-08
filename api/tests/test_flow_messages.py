"""Flow-centric tests for contributor messaging (Phase 3).

Covers:
  1. Send direct message -> appears in recipient inbox
  2. Send workspace message -> appears in workspace messages
  3. Mark read -> no longer in unread inbox
  4. Thread shows messages in both directions chronologically
  5. Message to non-existent contributor -> still created (graph is flexible)
  6. Inbox empty -> returns empty list with unread_count=0
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


# ---------------------------------------------------------------------------
# 1. Send direct message -> appears in recipient inbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_direct_message_appears_in_inbox():
    sender = _uid("contrib")
    recipient = _uid("contrib")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": sender,
            "to_contributor_id": recipient,
            "subject": "Hello",
            "body": "First direct message",
        })
        assert r.status_code == 201, r.text
        msg = r.json()
        assert msg["id"].startswith("msg-")
        assert msg["from_contributor_id"] == sender
        assert msg["to_contributor_id"] == recipient
        assert msg["body"] == "First direct message"
        assert msg["read"] is False

        # Check recipient inbox
        r2 = await c.get(f"/api/messages/inbox/{recipient}")
        assert r2.status_code == 200, r2.text
        inbox = r2.json()
        assert inbox["contributor_id"] == recipient
        assert inbox["total"] >= 1
        assert inbox["unread_count"] >= 1
        msg_ids = [m["id"] for m in inbox["messages"]]
        assert msg["id"] in msg_ids


# ---------------------------------------------------------------------------
# 2. Send workspace message -> appears in workspace messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_workspace_message_appears_in_workspace():
    sender = _uid("contrib")
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": sender,
            "to_workspace_id": ws_id,
            "subject": "Announcement",
            "body": "Workspace broadcast message",
        })
        assert r.status_code == 201, r.text
        msg = r.json()
        assert msg["to_workspace_id"] == ws_id
        assert msg["to_contributor_id"] is None

        # Check workspace messages
        r2 = await c.get(f"/api/workspaces/{ws_id}/messages")
        assert r2.status_code == 200, r2.text
        ws_msgs = r2.json()
        assert len(ws_msgs) >= 1
        msg_ids = [m["id"] for m in ws_msgs]
        assert msg["id"] in msg_ids


# ---------------------------------------------------------------------------
# 3. Mark read -> no longer in unread inbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_read_removes_from_unread():
    sender = _uid("contrib")
    recipient = _uid("contrib")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Send a message
        r = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": sender,
            "to_contributor_id": recipient,
            "body": "Read me",
        })
        assert r.status_code == 201, r.text
        msg_id = r.json()["id"]

        # Inbox unread count should be 1
        r2 = await c.get(f"/api/messages/inbox/{recipient}?unread_only=true")
        assert r2.status_code == 200, r2.text
        assert r2.json()["unread_count"] == 1

        # Mark as read
        r3 = await c.patch(f"/api/messages/{msg_id}/read", headers=AUTH, json={
            "contributor_id": recipient,
        })
        assert r3.status_code == 200, r3.text
        assert r3.json()["read"] is True

        # Unread inbox should now be empty
        r4 = await c.get(f"/api/messages/inbox/{recipient}?unread_only=true")
        assert r4.status_code == 200, r4.text
        assert r4.json()["unread_count"] == 0
        assert len(r4.json()["messages"]) == 0


# ---------------------------------------------------------------------------
# 4. Thread shows messages in both directions chronologically
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_shows_both_directions():
    alice = _uid("alice")
    bob = _uid("bob")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Alice sends to Bob
        r1 = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": alice,
            "to_contributor_id": bob,
            "body": "Hi Bob",
        })
        assert r1.status_code == 201, r1.text
        msg1_id = r1.json()["id"]

        # Bob replies to Alice
        r2 = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": bob,
            "to_contributor_id": alice,
            "body": "Hi Alice",
        })
        assert r2.status_code == 201, r2.text
        msg2_id = r2.json()["id"]

        # Get thread
        r3 = await c.get(f"/api/messages/thread/{alice}/{bob}")
        assert r3.status_code == 200, r3.text
        thread = r3.json()
        assert len(thread) == 2
        thread_ids = [m["id"] for m in thread]
        assert msg1_id in thread_ids
        assert msg2_id in thread_ids

        # Thread is sorted by created_at ascending (oldest first)
        timestamps = [m["created_at"] for m in thread]
        assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# 5. Message to non-existent contributor -> still created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_to_nonexistent_contributor_still_created():
    sender = _uid("contrib")
    ghost = _uid("ghost")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": sender,
            "to_contributor_id": ghost,
            "body": "Message to someone who does not exist yet",
        })
        assert r.status_code == 201, r.text
        msg = r.json()
        assert msg["to_contributor_id"] == ghost


# ---------------------------------------------------------------------------
# 6. Inbox empty -> returns empty list with unread_count=0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_inbox_returns_zero_unread():
    nobody = _uid("nobody")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(f"/api/messages/inbox/{nobody}")
        assert r.status_code == 200, r.text
        inbox = r.json()
        assert inbox["contributor_id"] == nobody
        assert inbox["messages"] == []
        assert inbox["total"] == 0
        assert inbox["unread_count"] == 0
