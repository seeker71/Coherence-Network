"""Tests for Social Platform Bots spec-167 — platform selection and ROI framework.

Verifies:
- R1: Ideas submitted via Discord carry interfaces=["discord"]
- R2: Vote tracking via question_votes table
- /cc-link: contributor attribution via discord_vote_service
- Platform selection: Discord declared winner in spec-167
- ROI signals R1-R5 defined in spec
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_discord_idea(client: AsyncClient, idea_id: str, *, with_question: bool = False) -> dict:
    payload: dict = {
        "id": idea_id,
        "name": f"Discord Idea {idea_id}",
        "description": "Submitted via Discord bot.",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
        "interfaces": ["discord"],
    }
    if with_question:
        payload["open_questions"] = [{
            "question": "Best approach?",
            "value_to_whole": 30.0,
            "estimated_cost": 3.0,
        }]
    res = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
    assert res.status_code in (200, 201), f"Failed to create idea: {res.text}"
    return res.json()


# ---------------------------------------------------------------------------
# R1 - Discord interface attribution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_discord_idea_carries_interface_tag() -> None:
    """R1: Ideas created via /cc-idea carry interfaces=['discord']."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = await _create_discord_idea(client, "spec167-r1-a")
    assert "discord" in body["interfaces"]


@pytest.mark.asyncio
async def test_r1_discord_idea_retrievable_by_id() -> None:
    """R1: Discord-submitted idea retains tag on GET /api/ideas/{id}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "spec167-r1-b")
        r = await client.get("/api/ideas/spec167-r1-b")
    assert r.status_code == 200
    assert "discord" in r.json()["interfaces"]


@pytest.mark.asyncio
async def test_r1_non_discord_idea_excluded() -> None:
    """R1: Ideas without discord interface do not carry the tag."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/ideas", json={
            "id": "spec167-r1-web",
            "name": "Web Idea",
            "description": "Via web UI.",
            "potential_value": 50.0,
            "estimated_cost": 5.0,
            "confidence": 0.6,
            "interfaces": ["human:web"],
        }, headers=AUTH_HEADERS)
    assert "discord" not in res.json()["interfaces"]


# ---------------------------------------------------------------------------
# R2 - Reaction vote volume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_vote_increments_count() -> None:
    """R2: POST vote increments question vote count."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATABASE_URL"] = f"sqlite:///{td}/r2a.db"
        import app.services.unified_db as udb
        udb.reset_engine()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _create_discord_idea(client, "spec167-r2-a", with_question=True)
            res = await client.post(
                "/api/ideas/spec167-r2-a/questions/0/vote",
                json={"polarity": "positive", "discord_user_id": "voter1"},
            )
        assert res.status_code == 200
        assert res.json()["votes"]["positive"] == 1


@pytest.mark.asyncio
async def test_r2_all_polarities_accepted() -> None:
    """R2: positive, negative, and excited polarities all accepted."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATABASE_URL"] = f"sqlite:///{td}/r2b.db"
        import app.services.unified_db as udb
        udb.reset_engine()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _create_discord_idea(client, "spec167-r2-b", with_question=True)
            last_res = None
            for pol, uid in [("positive", "u1"), ("negative", "u2"), ("excited", "u3")]:
                last_res = await client.post(
                    "/api/ideas/spec167-r2-b/questions/0/vote",
                    json={"polarity": pol, "discord_user_id": uid},
                )
                assert last_res.status_code == 200, f"polarity={pol} failed: {last_res.text}"
        assert last_res.json()["votes"] == {"positive": 1, "negative": 1, "excited": 1}


@pytest.mark.asyncio
async def test_r2_duplicate_vote_409() -> None:
    """R2: Same user + same polarity returns 409."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATABASE_URL"] = f"sqlite:///{td}/r2c.db"
        import app.services.unified_db as udb
        udb.reset_engine()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _create_discord_idea(client, "spec167-r2-c", with_question=True)
            r1 = await client.post(
                "/api/ideas/spec167-r2-c/questions/0/vote",
                json={"polarity": "positive", "discord_user_id": "dup"},
            )
            r2 = await client.post(
                "/api/ideas/spec167-r2-c/questions/0/vote",
                json={"polarity": "positive", "discord_user_id": "dup"},
            )
        assert r1.status_code == 200
        assert r2.status_code == 409


# ---------------------------------------------------------------------------
# /cc-link - contributor attribution
# ---------------------------------------------------------------------------


def test_cc_link_records_discord_user_id() -> None:
    """cc-link: vote service stores discord_user_id for attribution."""
    from app.services import discord_vote_service
    import app.services.unified_db as udb

    with tempfile.TemporaryDirectory() as td:
        os.environ["DATABASE_URL"] = f"sqlite:///{td}/link.db"
        udb.reset_engine()
        discord_vote_service.ensure_schema()
        result, created = discord_vote_service.vote(
            idea_id="link-idea-1", question_idx=0,
            discord_user_id="alice_discord", polarity="positive",
        )
    assert created is True
    assert result.votes.positive == 1
    assert result.your_vote == "positive"


def test_cc_link_separate_users_separate_votes() -> None:
    """cc-link: two different Discord users each get distinct vote records."""
    from app.services import discord_vote_service
    import app.services.unified_db as udb

    with tempfile.TemporaryDirectory() as td:
        os.environ["DATABASE_URL"] = f"sqlite:///{td}/link2.db"
        udb.reset_engine()
        discord_vote_service.ensure_schema()
        r1, c1 = discord_vote_service.vote("idea-x", 0, "alice", "positive")
        r2, c2 = discord_vote_service.vote("idea-x", 0, "bob", "positive")
    assert c1 and c2
    assert r2.votes.positive == 2


# ---------------------------------------------------------------------------
# Spec-as-code: spec-167 content validation
# ---------------------------------------------------------------------------


def test_spec_167_exists_and_records_discord_winner() -> None:
    """Spec 167 exists and declares Discord as the winning platform."""
    spec = Path(__file__).parents[2] / "specs" / "167-social-platform-bots.md"
    assert spec.exists(), f"Spec 167 not found at {spec}"
    content = spec.read_text(encoding="utf-8")
    assert "Winner: Discord" in content
    assert "Phase 2" in content
    assert "/cc-link" in content


def test_spec_167_has_r1_through_r5() -> None:
    """Spec 167 defines ROI signals R1 through R5."""
    spec = Path(__file__).parents[2] / "specs" / "167-social-platform-bots.md"
    content = spec.read_text(encoding="utf-8")
    for s in ["R1", "R2", "R3", "R4", "R5"]:
        assert f"### {s}" in content, f"Missing ROI signal {s} in spec 167"


def test_cc_link_command_file_exists() -> None:
    """discord-bot/src/commands/cc-link.js must exist (spec-167 deliverable)."""
    path = Path(__file__).parents[2] / "discord-bot" / "src" / "commands" / "cc-link.js"
    assert path.exists(), f"cc-link.js missing at {path}"
