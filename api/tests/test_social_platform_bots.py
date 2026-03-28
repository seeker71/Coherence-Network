"""Tests for Social Platform Bots (spec-167).

Verifies:
- R1: Ideas created with interfaces=["discord"] are queryable and carry discord interface tag.
- R2: Reaction vote endpoint (POST /api/ideas/{id}/questions/{idx}/vote) records votes
  and returns aggregate counts. Verifies question_votes table row creation.
- R2 duplicate: 409 on duplicate vote with same polarity.
- R2 invalid polarity: 422 validation error for unknown polarity values.
- R3: vote counts returned in response (engagement measurability).
- Idea not found: 404 when voting on a nonexistent idea.
- Question index out of range: 404 when question index exceeds idea's questions.
- R1 interface filter: GET /api/ideas returns ideas with discord interface.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_idea_with_question(client: AsyncClient, idea_id: str) -> dict:
    """Create an idea with one open question and return the response JSON."""
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
    assert resp.status_code == 201, f"Idea creation failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# R1 — idea submission via Discord carries "discord" interface tag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idea_created_with_discord_interface_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: POST /api/ideas with interfaces=['discord'] stores the tag."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-r1")

    assert "discord" in idea.get("interfaces", []), (
        "Expected 'discord' in interfaces field of created idea"
    )


@pytest.mark.asyncio
async def test_idea_with_discord_interface_retrievable(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: An idea created with interfaces=['discord'] can be retrieved via GET /api/ideas/{id}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-retrieve")
        idea_id = idea["id"]

        resp = await client.get(f"/api/ideas/{idea_id}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert "discord" in fetched.get("interfaces", [])


# ---------------------------------------------------------------------------
# R2 — reaction vote volume (POST /api/ideas/{id}/questions/{idx}/vote)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vote_on_question_returns_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: Voting on a question returns aggregate vote counts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-vote-basic")
        idea_id = idea["id"]

        resp = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "user-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "votes" in data
        assert data["votes"]["positive"] == 1
        assert data["votes"]["negative"] == 0
        assert data["votes"]["excited"] == 0
        assert data["your_vote"] == "positive"
        assert data["question_index"] == 0


@pytest.mark.asyncio
async def test_multiple_votes_aggregate_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: Multiple users voting increments aggregate counts correctly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-multi-vote")
        idea_id = idea["id"]

        # Three different users vote
        for uid, polarity in [("u1", "positive"), ("u2", "positive"), ("u3", "excited")]:
            r = await client.post(
                f"/api/ideas/{idea_id}/questions/0/vote",
                json={"polarity": polarity, "discord_user_id": uid},
            )
            assert r.status_code == 200

        last = r.json()
        assert last["votes"]["positive"] == 2
        assert last["votes"]["excited"] == 1
        assert last["votes"]["negative"] == 0


@pytest.mark.asyncio
async def test_duplicate_vote_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: Duplicate vote (same user + same polarity) returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-dup-vote")
        idea_id = idea["id"]

        payload = {"polarity": "positive", "discord_user_id": "dup-user-001"}
        r1 = await client.post(f"/api/ideas/{idea_id}/questions/0/vote", json=payload)
        assert r1.status_code == 200

        r2 = await client.post(f"/api/ideas/{idea_id}/questions/0/vote", json=payload)
        assert r2.status_code == 409
        assert r2.headers.get("X-Vote-Status") == "duplicate"


@pytest.mark.asyncio
async def test_vote_invalid_polarity_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: Voting with an invalid polarity value returns 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-bad-polarity")
        idea_id = idea["id"]

        resp = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": "maybe", "discord_user_id": "user-x"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_vote_missing_discord_user_id_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: Voting without discord_user_id returns 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-no-uid")
        idea_id = idea["id"]

        resp = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": "positive"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_vote_nonexistent_idea_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vote on nonexistent idea returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/does-not-exist-xyz/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "user-404"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vote_question_index_out_of_range_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vote with question_index beyond idea's questions returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-oob-idx")
        idea_id = idea["id"]

        resp = await client.post(
            f"/api/ideas/{idea_id}/questions/99/vote",
            json={"polarity": "excited", "discord_user_id": "user-oob"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# R2 — all three polarity types are valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("polarity", ["positive", "negative", "excited"])
async def test_all_polarity_types_accepted(
    polarity: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: All three polarity types (positive, negative, excited) are accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, f"discord-idea-pol-{polarity}")
        idea_id = idea["id"]

        resp = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": polarity, "discord_user_id": f"user-{polarity}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["votes"][polarity] == 1
        assert data["your_vote"] == polarity


# ---------------------------------------------------------------------------
# R1 — ideas with discord interface are listed correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discord_ideas_appear_in_idea_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: Ideas with interfaces=['discord'] appear in the main idea list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea = await _create_idea_with_question(client, "discord-idea-list-check")
        idea_id = idea["id"]

        resp = await client.get("/api/ideas")
        assert resp.status_code == 200
        data = resp.json()
        ids = [i["id"] for i in data.get("ideas", [])]
        assert idea_id in ids
