"""Tests for Discord bot integration (spec 164).

Covers:
1. POST /api/ideas/{id}/questions/{idx}/vote — happy path
2. Vote on nonexistent idea — 404
3. Vote on out-of-range question index — 404
4. Vote direction toggle (up then down)
5. Embed formatting for ideas
6. Portfolio status embed
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import discord_bot_service


@pytest.fixture(autouse=True)
def _clean_votes():
    """Reset vote store between tests."""
    discord_bot_service.reset_votes()
    yield
    discord_bot_service.reset_votes()


def _seed_idea_with_question(monkeypatch, tmp_path):
    """Seed a test idea with one open question via the API service."""
    import os
    from app.services import unified_db, graph_service, idea_service

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path}/test_discord.db"
    unified_db.reset_engine()
    unified_db.ensure_schema()

    idea_service.create_idea(
        idea_id="discord-test-idea",
        name="Discord Test Idea",
        description="An idea for testing Discord bot features",
        potential_value=100.0,
        estimated_cost=10.0,
        confidence=0.8,
    )
    from app.models.idea import IdeaQuestionCreate
    idea_service.add_question(
        idea_id="discord-test-idea",
        question="Should we build this?",
        value_to_whole=20.0,
        estimated_cost=2.0,
    )


@pytest.mark.asyncio
async def test_vote_on_question_happy_path(monkeypatch, tmp_path):
    """Test 1: Voting on a valid idea question returns 200 with tally."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/discord-test-idea/questions/0/vote",
            json={"voter_id": "discord:user123", "direction": "up"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["idea_id"] == "discord-test-idea"
    assert data["question_index"] == 0
    assert isinstance(data["question"], str)
    assert len(data["question"]) > 0
    assert data["votes_up"] == 1
    assert data["votes_down"] == 0
    assert data["voter_id"] == "discord:user123"


@pytest.mark.asyncio
async def test_vote_nonexistent_idea_returns_404(monkeypatch, tmp_path):
    """Test 2: Voting on a nonexistent idea returns 404."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/no-such-idea/questions/0/vote",
            json={"voter_id": "discord:user123", "direction": "up"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vote_out_of_range_question_returns_404(monkeypatch, tmp_path):
    """Test 3: Voting on an out-of-range question index returns 404."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/discord-test-idea/questions/99/vote",
            json={"voter_id": "discord:user123", "direction": "up"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vote_direction_toggle(monkeypatch, tmp_path):
    """Test 4: Changing vote direction removes old vote and adds new."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Vote up
        resp1 = await client.post(
            "/api/ideas/discord-test-idea/questions/0/vote",
            json={"voter_id": "discord:user456", "direction": "up"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["votes_up"] == 1
        assert resp1.json()["votes_down"] == 0

        # Same user votes down — should toggle
        resp2 = await client.post(
            "/api/ideas/discord-test-idea/questions/0/vote",
            json={"voter_id": "discord:user456", "direction": "down"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["votes_up"] == 0
        assert resp2.json()["votes_down"] == 1


@pytest.mark.asyncio
async def test_idea_embed_formatting(monkeypatch, tmp_path):
    """Test 5: Embed formatting produces valid Discord embed structure."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/discord-test-idea/embed")

    assert resp.status_code == 200
    data = resp.json()
    assert "title" in data
    assert "Discord Test Idea" in data["title"]
    assert "fields" in data
    assert len(data["fields"]) >= 4
    assert "footer" in data
    assert data["footer"]["text"] == "Idea ID: discord-test-idea"
    assert "color" in data


@pytest.mark.asyncio
async def test_portfolio_status_embed(monkeypatch, tmp_path):
    """Test 6: Portfolio status embed returns valid structure."""
    _seed_idea_with_question(monkeypatch, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/portfolio/status-embed")

    assert resp.status_code == 200
    data = resp.json()
    assert "title" in data
    assert "Portfolio" in data["title"]
    assert "fields" in data
    field_names = [f["name"] for f in data["fields"]]
    assert "Total Ideas" in field_names
    assert "Validated" in field_names
