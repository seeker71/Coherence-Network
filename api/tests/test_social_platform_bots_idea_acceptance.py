"""Acceptance-oriented tests for idea social-platform-bots (spec 167).

Covers verification items and deliverables from specs/167-social-platform-bots.md
that complement api/tests/test_social_platform_bots.py and test_social_platform_bots_167.py:

- Discord-first decision and ROI R1–R5 headings in the spec document
- register-commands.js registers /cc-link alongside other bot commands
- Vote API: invalid question index (negative) returns 404
- Vote API: same Discord user cannot submit a second polarity (unique vote per question)
- Happy path: discord-tagged ideas remain visible in the portfolio list for R1-style filtering
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_acceptance_discord_idea_visible_for_r1_style_measurement() -> None:
    """R1: Ideas with interfaces=['discord'] appear in GET /api/ideas (measure via client filter)."""
    idea_id = "spb-acc-r1-list-measure"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "R1 measure",
                "description": "Discord-sourced idea for ROI numerator.",
                "potential_value": 10.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
                "interfaces": ["discord"],
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201, created.text
        listed = await client.get("/api/ideas")
    assert listed.status_code == 200
    ideas = listed.json().get("ideas", [])
    discord_subset = [i for i in ideas if "discord" in (i.get("interfaces") or [])]
    assert any(i.get("id") == idea_id for i in discord_subset), (
        "Expected discord interface ideas to be discoverable from the ideas list"
    )


@pytest.mark.asyncio
async def test_acceptance_vote_negative_question_index_returns_404() -> None:
    """Verification: vote targets a valid question index only (negative → 404)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "spb-acc-neg-idx",
                "name": "Neg index",
                "description": "x",
                "potential_value": 1.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
                "interfaces": ["discord"],
                "open_questions": [
                    {
                        "question": "Q?",
                        "value_to_whole": 1.0,
                        "estimated_cost": 0.1,
                    }
                ],
            },
            headers=AUTH_HEADERS,
        )
        resp = await client.post(
            "/api/ideas/spb-acc-neg-idx/questions/-1/vote",
            json={"polarity": "positive", "discord_user_id": "u-neg"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_acceptance_same_user_second_polarity_returns_409() -> None:
    """Edge: one vote per user per question; changing polarity hits unique constraint (409)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "spb-acc-polarity-switch",
                "name": "Polarity",
                "description": "x",
                "potential_value": 1.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
                "interfaces": ["discord"],
                "open_questions": [
                    {
                        "question": "Q?",
                        "value_to_whole": 1.0,
                        "estimated_cost": 0.1,
                    }
                ],
            },
            headers=AUTH_HEADERS,
        )
        uid = "same-user-polarity"
        r1 = await client.post(
            "/api/ideas/spb-acc-polarity-switch/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": uid},
        )
        r2 = await client.post(
            "/api/ideas/spb-acc-polarity-switch/questions/0/vote",
            json={"polarity": "negative", "discord_user_id": uid},
        )
    assert r1.status_code == 200
    assert r2.status_code == 409


def test_acceptance_spec_167_lists_roi_signals_r1_r5() -> None:
    """Spec verification table: R1–R5 are defined as measurable sections."""
    spec = REPO_ROOT / "specs" / "167-social-platform-bots.md"
    text = spec.read_text(encoding="utf-8")
    assert "Winner: Discord" in text
    for label in ("### R1", "### R2", "### R3", "### R4", "### R5"):
        assert label in text, f"Missing {label} in spec 167"


def test_acceptance_spec_167_phase2_stub_names_x_bot_and_tweepy() -> None:
    """Phase 2 stub: separate x-bot stack and tweepy (per spec)."""
    spec = REPO_ROOT / "specs" / "167-social-platform-bots.md"
    text = spec.read_text(encoding="utf-8")
    assert "x-bot/" in text
    assert "tweepy" in text


def test_acceptance_register_commands_includes_cc_link() -> None:
    """Deliverable: cc-link is registered with other slash commands."""
    reg = REPO_ROOT / "discord-bot" / "src" / "register-commands.js"
    body = reg.read_text(encoding="utf-8")
    assert "cc-link" in body
    assert "cc-link.js" in body or "ccLink" in body


def test_acceptance_cc_link_command_exports_slash_metadata() -> None:
    """/cc-link command module defines Discord slash command name cc-link."""
    cmd = REPO_ROOT / "discord-bot" / "src" / "commands" / "cc-link.js"
    body = cmd.read_text(encoding="utf-8")
    assert ".setName('cc-link')" in body
    assert "contributor_id" in body


def test_acceptance_spec_documents_cc_link_persistence_path() -> None:
    """Spec 167 describes contributor mapping storage for /cc-link (acceptance doc)."""
    spec = REPO_ROOT / "specs" / "167-social-platform-bots.md"
    text = spec.read_text(encoding="utf-8")
    assert "contributors" in text.lower() or "contributor_id" in text
    assert "cc-link" in text
