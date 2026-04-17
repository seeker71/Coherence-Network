"""Flow tests for soft notifications — who spoke back to you.

The endpoint is pure read across reactions/voices. Each test sets up a
small scenario and checks that the right events are surfaced.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_reply_to_me_shows_up():
    """A reply to a reaction authored by me surfaces as reply_to_me."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        my_id = "notify-listener"
        # My root comment
        r = await c.post(
            "/api/reactions/concept/lc-notify",
            json={
                "author_name": "Listener",
                "comment": "hello from me",
                "author_id": my_id,
            },
        )
        parent_id = r.json()["reaction"]["id"]
        # Another voice replies
        await c.post(
            "/api/reactions/concept/lc-notify",
            json={
                "author_name": "Friend",
                "comment": "hello back",
                "parent_reaction_id": parent_id,
            },
        )
        r = await c.get(f"/api/notifications?contributor_id={my_id}")
        assert r.status_code == 200
        events = r.json()["events"]
        assert any(
            e["kind"] == "reply_to_me" and e["actor_name"] == "Friend"
            for e in events
        )


@pytest.mark.asyncio
async def test_reaction_to_my_voice_shows_up():
    """A reaction on a concept where I offered a voice surfaces."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        my_id = "voice-giver"
        cid = "lc-voice-notify"
        await c.post(
            "/api/graph/nodes",
            json={
                "id": cid, "type": "concept", "name": "Voice notify",
                "description": "T", "properties": {"domains": ["living-collective"]},
            },
        )
        # I offer a voice
        await c.post(
            f"/api/concepts/{cid}/voices",
            json={"author_name": "VoiceGiver", "body": "we live this", "author_id": my_id},
        )
        # Someone else reacts to the concept
        await c.post(
            f"/api/reactions/concept/{cid}",
            json={"author_name": "Witness", "emoji": "💛"},
        )
        r = await c.get(f"/api/notifications?contributor_id={my_id}")
        events = r.json()["events"]
        assert any(e["kind"] == "reaction_to_my_voice" for e in events)


@pytest.mark.asyncio
async def test_mention_by_name_shows_up():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Someone mentions me
        await c.post(
            "/api/reactions/concept/lc-mention",
            json={
                "author_name": "Mentioner",
                "comment": "I was reading what @Ana said and agree.",
            },
        )
        r = await c.get("/api/notifications?author_name=Ana")
        events = r.json()["events"]
        assert any(e["kind"] == "mention" for e in events)


@pytest.mark.asyncio
async def test_since_filter_excludes_older_events():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        me = "time-traveler"
        root = await c.post(
            "/api/reactions/concept/lc-time",
            json={"author_name": "Time", "comment": "root", "author_id": me},
        )
        parent_id = root.json()["reaction"]["id"]
        r0 = await c.post(
            "/api/reactions/concept/lc-time",
            json={
                "author_name": "Other",
                "comment": "reply",
                "parent_reaction_id": parent_id,
            },
        )
        assert r0.status_code == 201
        # Pass a future `since` — nothing should remain.
        # Use Z suffix so the `+` in tz offset doesn't URL-decode to space.
        from datetime import datetime, timedelta, timezone
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        r = await c.get(
            "/api/notifications",
            params={"contributor_id": me, "since": future},
        )
        assert r.json()["count"] == 0


@pytest.mark.asyncio
async def test_no_identity_returns_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/notifications")
        assert r.status_code == 200
        assert r.json()["count"] == 0
