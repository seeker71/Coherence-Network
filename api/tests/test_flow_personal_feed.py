"""Flow tests for the personal feed — your corner of the organism.

The endpoint is a union read across voices, reactions, and proposals
filtered to the viewer's identity. Each item carries a reason caption;
we test that the right items surface under the right reasons.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_personal_feed_shows_own_voice_and_reactions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        me = "pf-dweller-one"
        cid = "lc-pf-home"
        await c.post(
            "/api/graph/nodes",
            json={
                "id": cid, "type": "concept", "name": "PF Home",
                "description": "T", "properties": {"domains": ["living-collective"]},
            },
        )
        # Voice I gave
        await c.post(
            f"/api/concepts/{cid}/voices",
            json={"author_name": "Dweller", "body": "my lived thing", "author_id": me},
        )
        # Reaction with comment I wrote
        await c.post(
            "/api/reactions/idea/some-idea",
            json={
                "author_name": "Dweller",
                "comment": "interesting angle",
                "author_id": me,
            },
        )
        r = await c.get(f"/api/feed/personal?contributor_id={me}")
        assert r.status_code == 200
        items = r.json()["items"]
        reasons = {it["reason"] for it in items}
        assert "i_voiced" in reasons
        assert "i_reacted" in reasons


@pytest.mark.asyncio
async def test_personal_feed_shows_reaction_on_my_voice():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        me = "pf-dweller-two"
        cid = "lc-pf-witnessed"
        await c.post(
            "/api/graph/nodes",
            json={
                "id": cid, "type": "concept", "name": "Witnessed",
                "description": "T", "properties": {"domains": ["living-collective"]},
            },
        )
        await c.post(
            f"/api/concepts/{cid}/voices",
            json={"author_name": "Me", "body": "lived", "author_id": me},
        )
        await c.post(
            f"/api/reactions/concept/{cid}",
            json={"author_name": "Witness", "emoji": "💛"},
        )
        r = await c.get(f"/api/feed/personal?contributor_id={me}")
        items = r.json()["items"]
        assert any(it["reason"] == "reaction_on_my_voice" for it in items)


@pytest.mark.asyncio
async def test_personal_feed_surfaces_lifted_proposals():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        me = "pf-proposer"
        r = await c.post(
            "/api/proposals",
            json={
                "title": "Open pot-luck Sundays",
                "body": "",
                "author_name": "Me",
                "author_id": me,
            },
        )
        pid = r.json()["id"]
        for emoji in ("💛", "💛", "💛", "🔥"):
            await c.post(
                f"/api/reactions/proposal/{pid}",
                json={"author_name": "voter", "emoji": emoji},
            )
        await c.post(f"/api/proposals/{pid}/resolve")
        r = await c.get(f"/api/feed/personal?contributor_id={me}")
        items = r.json()["items"]
        # The proposal should now surface as lifted_from_my_proposal, pointing
        # at the new idea (entity_type=idea)
        lifted = [it for it in items if it["reason"] == "lifted_from_my_proposal"]
        assert lifted
        assert lifted[0]["entity_type"] == "idea"


@pytest.mark.asyncio
async def test_personal_feed_localizes_reason_captions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        me = "pf-localized"
        await c.post(
            "/api/reactions/concept/lc-loc",
            json={"author_name": "Me", "comment": "hola", "author_id": me},
        )
        r = await c.get(
            "/api/feed/personal",
            params={"contributor_id": me, "lang": "es"},
        )
        items = r.json()["items"]
        assert items
        assert "Reaccionaste" in items[0]["reason_label"]


@pytest.mark.asyncio
async def test_personal_feed_empty_without_identity():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/feed/personal")
        assert r.status_code == 200
        assert r.json()["count"] == 0
