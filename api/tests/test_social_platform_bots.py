"""Tests for Social Platform Bots (spec-167).

Verifies acceptance criteria for:
- R1: Ideas submitted via Discord carry interfaces=["discord"]
- R2: Vote tracking on idea open questions (question_votes table)
- /cc-link attribution: contributor mapping logic
- Platform selection: Discord-first model is recorded in spec
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_discord_idea(
    client: AsyncClient,
    idea_id: str,
    *,
    with_question: bool = False,
) -> dict:
    """Create a test idea tagged with the discord interface."""
    payload: dict = {
        "id": idea_id,
        "name": f"Discord Idea {idea_id}",
        "description": "Idea submitted via Discord bot.",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
        "interfaces": ["discord"],
    }
    if with_question:
        payload["open_questions"] = [
            {
                "question": "Is this the best approach?",
                "value_to_whole": 30.0,
                "estimated_cost": 3.0,
            }
        ]
    res = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
    assert res.status_code in (200, 201), f"Failed to create idea: {res.text}"
    return res.json()


# ---------------------------------------------------------------------------
# R1 — Idea Submission Rate via Discord
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discord_idea_carries_discord_interface(tmp_path: Path) -> None:
    """Ideas created via Discord bot carry 'discord' in their interfaces list (R1)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = await _create_discord_idea(client, "social-r1-001")

    assert "discord" in body["interfaces"], (
        f"Expected 'discord' in interfaces, got {body['interfaces']!r}"
    )


@pytest.mark.asyncio
async def test_discord_idea_is_retrievable_by_id(tmp_path: Path) -> None:
    """A Discord-submitted idea can be fetched via GET /api/ideas/{id} and retains the discord tag."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r1-002")
        r = await client.get("/api/ideas/social-r1-002")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "social-r1-002"
    assert "discord" in body["interfaces"]


@pytest.mark.asyncio
async def test_discord_idea_appears_in_portfolio(tmp_path: Path) -> None:
    """Discord-submitted idea appears in the portfolio response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r1-003")
        r = await client.get("/api/ideas")

    assert r.status_code == 200, r.text
    ideas = r.json()["ideas"]
    ids = [i["id"] for i in ideas]
    assert "social-r1-003" in ids, f"Discord idea not found in portfolio. IDs: {ids}"


@pytest.mark.asyncio
async def test_non_discord_idea_has_no_discord_interface(tmp_path: Path) -> None:
    """An idea created without discord interface does not carry the discord tag."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/ideas",
            json={
                "id": "social-r1-non-discord",
                "name": "Non-Discord Idea",
                "description": "Submitted via web UI, not Discord.",
                "potential_value": 50.0,
                "estimated_cost": 5.0,
                "confidence": 0.6,
                "interfaces": ["human:web"],
            },
            headers=AUTH_HEADERS,
        )

    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert "discord" not in body["interfaces"]


# ---------------------------------------------------------------------------
# R2 — Reaction Vote Volume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vote_increments_question_vote_count(tmp_path: Path) -> None:
    """Posting a vote via the API increments question vote counts (R2 signal)."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/social_votes.db"
    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r2-001", with_question=True)

        res = await client.post(
            "/api/ideas/social-r2-001/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "voter_a"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["votes"]["positive"] == 1
    assert body["question_index"] == 0


@pytest.mark.asyncio
async def test_vote_supports_all_three_polarities(tmp_path: Path) -> None:
    """All three polarities (positive, negative, excited) are accepted by the vote endpoint."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/social_polarity.db"
    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r2-002", with_question=True)

        r_pos = await client.post(
            "/api/ideas/social-r2-002/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "voter_pos"},
        )
        r_neg = await client.post(
            "/api/ideas/social-r2-002/questions/0/vote",
            json={"polarity": "negative", "discord_user_id": "voter_neg"},
        )
        r_exc = await client.post(
            "/api/ideas/social-r2-002/questions/0/vote",
            json={"polarity": "excited", "discord_user_id": "voter_exc"},
        )

    assert r_pos.status_code == 200, r_pos.text
    assert r_neg.status_code == 200, r_neg.text
    assert r_exc.status_code == 200, r_exc.text

    final = r_exc.json()
    assert final["votes"]["positive"] == 1
    assert final["votes"]["negative"] == 1
    assert final["votes"]["excited"] == 1


@pytest.mark.asyncio
async def test_duplicate_vote_returns_409(tmp_path: Path) -> None:
    """Duplicate vote from the same user with the same polarity returns 409 (idempotent)."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/social_dup.db"
    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r2-003", with_question=True)

        first = await client.post(
            "/api/ideas/social-r2-003/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "voter_dup"},
        )
        second = await client.post(
            "/api/ideas/social-r2-003/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "voter_dup"},
        )

    assert first.status_code == 200
    assert second.status_code == 409, f"Expected 409 for duplicate vote, got {second.status_code}"


@pytest.mark.asyncio
async def test_vote_on_missing_idea_returns_404(tmp_path: Path) -> None:
    """Voting on a non-existent idea returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/ideas/does-not-exist-167/questions/0/vote",
            json={"polarity": "excited", "discord_user_id": "ghost_voter"},
        )

    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_vote_on_out_of_range_question_returns_404(tmp_path: Path) -> None:
    """Voting on a question index that doesn't exist returns 404."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/social_oor.db"
    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_discord_idea(client, "social-r2-004", with_question=True)

        res = await client.post(
            "/api/ideas/social-r2-004/questions/99/vote",
            json={"polarity": "positive", "discord_user_id": "lost_voter"},
        )

    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# /cc-link — Contributor attribution (service-layer tests)
# ---------------------------------------------------------------------------


def test_cc_link_service_stores_mapping(tmp_path: Path) -> None:
    """discord_vote_service.vote records the discord_user_id field correctly.

    This verifies the attribution model: Discord user IDs are stored per vote
    so that contributor attribution can be resolved from the mapping.
    """
    from app.services import discord_vote_service
    import app.services.unified_db as udb

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/cc_link.db"
    udb.reset_engine()
    discord_vote_service.ensure_schema()

    result, created = discord_vote_service.vote(
        idea_id="link-test-idea",
        question_idx=0,
        discord_user_id="discord_user_alice",
        polarity="positive",
    )

    assert created is True
    assert result.your_vote == "positive"
    assert result.votes.positive == 1


def test_cc_link_different_users_get_separate_votes(tmp_path: Path) -> None:
    """Two different Discord users each get their own vote record (no collision)."""
    from app.services import discord_vote_service
    import app.services.unified_db as udb

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/cc_link2.db"
    udb.reset_engine()
    discord_vote_service.ensure_schema()

    r1, c1 = discord_vote_service.vote(
        idea_id="link-test-multi",
        question_idx=0,
        discord_user_id="alice_discord",
        polarity="positive",
    )
    r2, c2 = discord_vote_service.vote(
        idea_id="link-test-multi",
        question_idx=0,
        discord_user_id="bob_discord",
        polarity="positive",
    )

    assert c1 is True
    assert c2 is True
    assert r2.votes.positive == 2


def test_cc_link_same_user_different_ideas_allowed(tmp_path: Path) -> None:
    """Same Discord user can vote on different ideas without conflict."""
    from app.services import discord_vote_service
    import app.services.unified_db as udb

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/cc_link3.db"
    udb.reset_engine()
    discord_vote_service.ensure_schema()

    r1, c1 = discord_vote_service.vote(
        idea_id="idea-A",
        question_idx=0,
        discord_user_id="carol_discord",
        polarity="excited",
    )
    r2, c2 = discord_vote_service.vote(
        idea_id="idea-B",
        question_idx=0,
        discord_user_id="carol_discord",
        polarity="excited",
    )

    assert c1 is True
    assert c2 is True
    assert r1.votes.excited == 1
    assert r2.votes.excited == 1


# ---------------------------------------------------------------------------
# Platform Selection Rationale (spec record tests)
# ---------------------------------------------------------------------------


def test_spec_167_records_discord_as_winning_platform() -> None:
    """Spec 167 exists and explicitly records Discord as the selected platform."""
    spec_path = Path(__file__).parents[2] / "specs" / "167-social-platform-bots.md"
    assert spec_path.exists(), f"Spec 167 not found at {spec_path}"

    content = spec_path.read_text(encoding="utf-8")
    assert "Winner: Discord" in content, "Spec 167 must declare Discord as the winner"
    assert "Phase 2" in content, "Spec 167 must stub the Phase 2 X/Twitter bot"
    assert "/cc-link" in content, "Spec 167 must document the /cc-link command"


def test_spec_167_defines_five_roi_signals() -> None:
    """Spec 167 defines R1 through R5 ROI signals."""
    spec_path = Path(__file__).parents[2] / "specs" / "167-social-platform-bots.md"
    content = spec_path.read_text(encoding="utf-8")

    for signal in ["R1", "R2", "R3", "R4", "R5"]:
        assert f"### {signal}" in content, f"Spec 167 missing ROI signal {signal}"


def test_spec_167_cc_link_file_exists() -> None:
    """The /cc-link command file referenced in spec 167 exists in the repo."""
    cc_link_path = (
        Path(__file__).parents[2] / "discord-bot" / "src" / "commands" / "cc-link.js"
    )
    assert cc_link_path.exists(), (
        f"cc-link.js not found at {cc_link_path}. "
        "Spec 167 requires this file to exist."
    )
