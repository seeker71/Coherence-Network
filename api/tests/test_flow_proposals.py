"""Flow tests for proposals — light governance via the meeting gesture.

A proposal is a tiny piece of content anyone can create. Votes are
reactions; the tally is computed on read, not stored. Declines are
tracked but treated as cool rather than hostile.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_create_proposal_returns_id_and_open_window():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/proposals",
            json={
                "title": "Try Sunday harvests in the garden",
                "body": "We have more fruit than we can eat alone.",
                "author_name": "Paloma",
                "window_days": 7,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"]
        assert body["open"] is True


@pytest.mark.asyncio
async def test_proposal_tally_reads_from_reactions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/proposals",
            json={"title": "Tally test", "body": "", "author_name": "P"},
        )
        pid = r.json()["id"]

        # Three support, one amplify, one decline
        for emoji in ("💛", "💛", "💛", "🔥", "➡️"):
            await c.post(
                f"/api/reactions/proposal/{pid}",
                json={"author_name": "voter", "emoji": emoji},
            )

        r = await c.get(f"/api/proposals/{pid}/tally")
        assert r.status_code == 200
        t = r.json()
        assert t["counts"]["support"] == 3
        assert t["counts"]["amplify"] == 1
        assert t["counts"]["decline"] == 1
        # support (3) + 2*amplify (2) = 5 weighted yes vs 1 no
        assert t["weighted"]["yes"] == 5
        assert t["weighted"]["no"] == 1
        # amplify > 0 and 5 >= 3*max(1,1) = 3 → resonant
        assert t["status"] == "resonant"


@pytest.mark.asyncio
async def test_proposal_quiet_status_when_no_votes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/proposals",
            json={"title": "Quiet one", "body": "", "author_name": "P"},
        )
        pid = r.json()["id"]
        r = await c.get(f"/api/proposals/{pid}/tally")
        assert r.json()["status"] == "quiet"


@pytest.mark.asyncio
async def test_proposal_list_includes_tally_by_default():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post(
            "/api/proposals",
            json={"title": "Listed proposal", "body": "", "author_name": "P"},
        )
        r = await c.get("/api/proposals?limit=5")
        assert r.status_code == 200
        rows = r.json()["proposals"]
        assert rows and all("tally" in p for p in rows)


@pytest.mark.asyncio
async def test_proposal_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/proposals/does-not-exist")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_explore_proposal_returns_open_proposals():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post(
            "/api/proposals",
            json={"title": "Walk me", "body": "", "author_name": "P"},
        )
        r = await c.get("/api/explore/proposal?limit=20")
        assert r.status_code == 200
        titles = {q["title"] for q in r.json()["queue"]}
        assert "Walk me" in titles
