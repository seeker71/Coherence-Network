"""Acceptance-oriented API tests for the Discord bot (spec 164: bot-discord).

Verifies REST contracts the Node `discord-bot` relies on for slash commands,
pipeline feed, idea sync, and staking — without importing Discord.js.

See specs/164-discord-bot-channels-per-idea.md (Acceptance Criteria, Verification Scenarios).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_cc_status_health_contract() -> None:
    """R4 / Scenario 3: /cc-status reads GET /api/health — embed fields must exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "ok"
    assert "version" in body
    assert "uptime_human" in body
    assert "uptime_seconds" in body
    assert "schema_ok" in body
    assert "timestamp" in body
    assert "started_at" in body


@pytest.mark.asyncio
async def test_cc_idea_creates_and_retrieves_idea(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 2 + acceptance: /cc-idea creates an idea via POST /api/ideas; GET returns it."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    os.environ["IDEA_PORTFOLIO_PATH"] = str(tmp_path / "ideas.json")

    idea_id = "discord-test-idea-spec164"
    payload = {
        "id": idea_id,
        "name": "Discord test idea 001",
        "description": "Spec verification test idea for Discord bot acceptance.",
        "potential_value": 10.0,
        "estimated_cost": 1.0,
        "confidence": 0.7,
        "interfaces": ["discord"],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post = await client.post("/api/ideas", json=payload)
        assert post.status_code == 201, post.text
        created = post.json()
        assert created["name"] == payload["name"]
        assert "discord" in (created.get("interfaces") or [])

        get_one = await client.get(f"/api/ideas/{idea_id}")
        assert get_one.status_code == 200
        assert get_one.json()["name"] == payload["name"]


@pytest.mark.asyncio
async def test_cc_stake_backend_contract_matches_spec_r5() -> None:
    """R5: staking from Discord maps to POST /api/ideas/{id}/stake (canonical API)."""
    from app.services import graph_service

    idea_id = "discord-stake-contract-001"
    graph_service.create_node(
        id=idea_id,
        type="idea",
        name="Discord stake contract",
        description="Validates stake fields for /cc-stake confirm flow.",
        phase="gas",
        properties={
            "potential_value": 100.0,
            "estimated_cost": 10.0,
            "actual_value": 0.0,
            "actual_cost": 0.0,
            "confidence": 0.65,
            "manifestation_status": "none",
            "stage": "none",
            "idea_type": "standalone",
            "interfaces": [],
            "open_questions": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/ideas/{idea_id}/stake",
            json={
                "contributor_id": "discord_user_mapped_alice",
                "amount_cc": 25.0,
                "rationale": "spec-164 acceptance",
            },
        )

    assert res.status_code == 200, res.text
    data = res.json()
    assert "stake" in data
    assert data["stake"]["amount_cc"] == 25.0
    assert data["stake"].get("contributor") == "discord_user_mapped_alice"


@pytest.mark.asyncio
async def test_pipeline_feed_task_list_shape() -> None:
    """R6: pipeline feed polls agent tasks — list payload must include embed primitives."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/tasks", params={"limit": 5})

    assert res.status_code == 200, res.text
    body = res.json()
    assert "tasks" in body
    assert "total" in body
    assert isinstance(body["tasks"], list)
    for item in body["tasks"]:
        assert "id" in item
        assert "status" in item
        assert "task_type" in item
        assert "direction" in item
        assert "updated_at" in item or item.get("updated_at") is None


@pytest.mark.asyncio
async def test_active_idea_embed_fields_on_portfolio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1/R2: idea channel sync and embeds need stage, scores, and manifestation from GET /api/ideas."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    os.environ["IDEA_PORTFOLIO_PATH"] = str(tmp_path / "ideas.json")

    idea_id = "discord-portfolio-embed-001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Embed field check",
                "description": "x" * 50,
                "potential_value": 20.0,
                "estimated_cost": 2.0,
                "confidence": 0.8,
            },
        )
        assert create.status_code == 201

        lst = await client.get("/api/ideas", params={"limit": 100})
        assert lst.status_code == 200
        ideas = lst.json()["ideas"]
        match = next(i for i in ideas if i["id"] == idea_id)
        for key in ("id", "name", "description", "stage", "manifestation_status",
                    "free_energy_score", "potential_value", "actual_value"):
            assert key in match

@pytest.mark.asyncio
async def test_reaction_vote_endpoint_matches_spec164_scenario_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 4: POST vote then GET idea still resolves (R7 vote sync path)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/disc_sc4.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/disc_sc4.db"
    os.environ["IDEA_PORTFOLIO_PATH"] = str(tmp_path / "ideas.json")

    import app.services.unified_db as udb
    udb.reset_engine()

    idea_id = "discord-scenario4-vote"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        setup = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Vote scenario",
                "description": "Vote sync",
                "potential_value": 5.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
                "open_questions": [
                    {
                        "question": "Does reaction voting work?",
                        "value_to_whole": 10.0,
                        "estimated_cost": 1.0,
                    }
                ],
            },
        )
        assert setup.status_code in (200, 201), setup.text

        vote = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": "positive", "discord_user_id": "discord_reactor_1"},
        )
        assert vote.status_code == 200, vote.text

        gid = await client.get(f"/api/ideas/{idea_id}")
        assert gid.status_code == 200
        assert gid.json()["open_questions"][0]["question"].startswith("Does reaction")
