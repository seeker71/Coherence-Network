"""Flow tests for reactions — emoji + comment across any entity.

Single flow file per memory: "extend existing when possible; new file only
when the surface is genuinely new." Reactions is a new surface spanning
multiple entity types, so it earns its own file. Kept compact.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_add_emoji_only_reaction_on_concept():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/reactions/concept/lc-breath",
            json={"author_name": "Mira", "emoji": "🌱"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["reaction"]["emoji"] == "🌱"
        assert data["reaction"]["comment"] is None
        assert data["summary"]["total"] >= 1


@pytest.mark.asyncio
async def test_add_comment_only_reaction_on_idea():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/reactions/idea/agent-pipeline",
            json={"author_name": "Juan", "comment": "This changed how I see tasks."},
        )
        assert r.status_code == 201
        assert r.json()["reaction"]["comment"].startswith("This changed")


@pytest.mark.asyncio
async def test_reaction_needs_emoji_or_comment():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/reactions/concept/lc-pulse",
            json={"author_name": "Anon"},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_reactions_are_listable_with_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for emoji in ("💛", "💛", "🙏"):
            await c.post(
                "/api/reactions/spec/multilingual-web",
                json={"author_name": "Ana", "emoji": emoji},
            )
        r = await c.get("/api/reactions/spec/multilingual-web")
        assert r.status_code == 200
        body = r.json()
        emojis = {e["emoji"]: e["count"] for e in body["summary"]["emojis"]}
        assert emojis.get("💛", 0) >= 2
        assert emojis.get("🙏", 0) >= 1


@pytest.mark.asyncio
async def test_reactions_unsupported_entity_type_localized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/reactions/lobster/soup",
            json={"author_name": "Anon", "emoji": "🦞"},
            headers={"accept-language": "de"},
        )
        assert r.status_code == 400
        assert "nicht unterstützt" in r.json()["detail"]


@pytest.mark.asyncio
async def test_recent_reactions_stream():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post(
            "/api/reactions/contributor/alice",
            json={"author_name": "Friend", "emoji": "👀"},
        )
        r = await c.get("/api/reactions/recent?limit=10")
        assert r.status_code == 200
        rs = r.json()["reactions"]
        assert any(rx["entity_type"] == "contributor" and rx["emoji"] == "👀" for rx in rs)


@pytest.mark.asyncio
async def test_threaded_reply_groups_under_parent():
    """A reply carries parent_reaction_id; the /threads view nests it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Seed a comment-rooted reaction
        r = await c.post(
            "/api/reactions/concept/lc-threaded",
            json={"author_name": "Seed", "comment": "The first word."},
        )
        assert r.status_code == 201
        parent_id = r.json()["reaction"]["id"]

        # Reply to that root
        r = await c.post(
            "/api/reactions/concept/lc-threaded",
            json={
                "author_name": "Echo",
                "comment": "And the second.",
                "parent_reaction_id": parent_id,
            },
        )
        assert r.status_code == 201
        reply = r.json()["reaction"]
        assert reply["parent_reaction_id"] == parent_id

        # Fetch threads — one root, one reply
        r = await c.get("/api/reactions/concept/lc-threaded/threads")
        assert r.status_code == 200
        threads = r.json()["threads"]
        root = next((t for t in threads if t["id"] == parent_id), None)
        assert root is not None
        assert root["comment"] == "The first word."
        assert any(rp["id"] == reply["id"] for rp in root["replies"])


@pytest.mark.asyncio
async def test_reply_cannot_cross_entities():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/reactions/concept/lc-home",
            json={"author_name": "A", "comment": "home"},
        )
        home_id = r.json()["reaction"]["id"]
        # Try to use that reaction as a parent on a different entity
        r = await c.post(
            "/api/reactions/idea/somewhere-else",
            json={
                "author_name": "B",
                "comment": "crosswire",
                "parent_reaction_id": home_id,
            },
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_threads_skip_pure_emoji_roots():
    """Top-level emoji-only reactions stay in the summary, not the thread."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post(
            "/api/reactions/concept/lc-threads-quiet",
            json={"author_name": "A", "emoji": "💛"},
        )
        await c.post(
            "/api/reactions/concept/lc-threads-quiet",
            json={"author_name": "B", "comment": "rooted"},
        )
        r = await c.get("/api/reactions/concept/lc-threads-quiet/threads")
        threads = r.json()["threads"]
        # Only the rooted one appears
        assert len(threads) == 1
        assert threads[0]["comment"] == "rooted"


@pytest.mark.asyncio
async def test_reaction_on_multiple_entity_types():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for et in (
            "concept", "idea", "spec", "contributor", "community",
            "workspace", "asset", "contribution", "story",
            "config", "insight", "agent_task", "agent_run",
        ):
            r = await c.post(
                f"/api/reactions/{et}/test-{et}",
                json={"author_name": "P", "emoji": "✨"},
            )
            assert r.status_code == 201, f"{et} failed: {r.text}"
