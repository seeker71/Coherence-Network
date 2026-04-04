"""Tests for Social Platform Bots (spec-167).

Verifies:
- R1: Ideas created with interfaces=["discord"] carry the discord interface tag.
- R2: POST /api/ideas/{id}/questions/{idx}/vote records votes and returns aggregate counts.
- Duplicate vote returns 409. Invalid polarity returns 422.
- Nonexistent idea returns 404. Out-of-range question index returns 404.
- All three polarity types are accepted (positive, negative, excited).
- Discord-tagged ideas appear in the main idea list.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


async def _create_discord_idea(client, idea_id):
    resp = await client.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": f"Discord Idea {idea_id}",
            "description": "Created via Discord bot.",
            "potential_value": 100.0,
            "estimated_cost": 20.0,
            "confidence": 0.7,
            "interfaces": ["discord"],
            "open_questions": [
                {
                    "question": "Is this a good idea?",
                    "value_to_whole": 10.0,
                    "estimated_cost": 2.0,
                }
            ],
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_idea_carries_discord_interface_tag():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r1-tag")
    assert "discord" in idea.get("interfaces", [])


@pytest.mark.asyncio
async def test_discord_idea_retrievable_by_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r1-get")
        resp = await client.get(f"/api/ideas/{idea['id']}")
    assert resp.status_code == 200
    assert "discord" in resp.json().get("interfaces", [])


@pytest.mark.asyncio
async def test_vote_returns_aggregate_counts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-basic")
        resp = await client.post(
            f"/api/ideas/{idea['id']}/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "u001"},
        )
    assert resp.status_code == 200
    d = resp.json()
    assert d["votes"]["positive"] == 1
    assert d["votes"]["negative"] == 0
    assert d["votes"]["excited"] == 0
    assert d["your_vote"] == "positive"
    assert d["question_index"] == 0


@pytest.mark.asyncio
async def test_multiple_voters_aggregate_counts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-multi")
        iid = idea["id"]
        last = None
        for uid, pol in [("u1", "positive"), ("u2", "positive"), ("u3", "excited")]:
            last = await client.post(
                f"/api/ideas/{iid}/questions/0/vote",
                json={"polarity": pol, "discord_user_id": uid},
            )
            assert last.status_code == 200
    d = last.json()
    assert d["votes"]["positive"] == 2
    assert d["votes"]["excited"] == 1
    assert d["votes"]["negative"] == 0


@pytest.mark.asyncio
async def test_duplicate_vote_returns_409():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-dup")
        iid = idea["id"]
        payload = {"polarity": "positive", "discord_user_id": "dup-u"}
        r1 = await client.post(f"/api/ideas/{iid}/questions/0/vote", json=payload)
        assert r1.status_code == 200
        r2 = await client.post(f"/api/ideas/{iid}/questions/0/vote", json=payload)
    assert r2.status_code == 409
    assert r2.headers.get("X-Vote-Status") == "duplicate"


@pytest.mark.asyncio
async def test_invalid_polarity_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-badpol")
        resp = await client.post(
            f"/api/ideas/{idea['id']}/questions/0/vote",
            json={"polarity": "maybe", "discord_user_id": "u-x"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_discord_user_id_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-nouid")
        resp = await client.post(
            f"/api/ideas/{idea['id']}/questions/0/vote",
            json={"polarity": "positive"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_vote_nonexistent_idea_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/nonexistent-spb-xyz/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "u404"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vote_out_of_range_question_index_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r2-oob")
        resp = await client.post(
            f"/api/ideas/{idea['id']}/questions/99/vote",
            json={"polarity": "excited", "discord_user_id": "u-oob"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("polarity", ["positive", "negative", "excited"])
async def test_all_polarity_types_accepted(polarity):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, f"spb-pol-{polarity}")
        resp = await client.post(
            f"/api/ideas/{idea['id']}/questions/0/vote",
            json={"polarity": polarity, "discord_user_id": f"u-{polarity}"},
        )
    assert resp.status_code == 200
    d = resp.json()
    assert d["votes"][polarity] == 1
    assert d["your_vote"] == polarity


@pytest.mark.asyncio
async def test_discord_ideas_appear_in_idea_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_discord_idea(client, "spb-r1-list")
        resp = await client.get("/api/ideas")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json().get("ideas", [])]
    assert idea["id"] in ids
