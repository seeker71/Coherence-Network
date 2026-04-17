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
async def test_reaction_on_multiple_entity_types():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for et in ("concept", "idea", "spec", "contributor", "community", "workspace", "asset", "contribution", "story"):
            r = await c.post(
                f"/api/reactions/{et}/test-{et}",
                json={"author_name": "P", "emoji": "✨"},
            )
            assert r.status_code == 201, f"{et} failed: {r.text}"
