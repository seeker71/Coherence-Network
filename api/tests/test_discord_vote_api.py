"""Tests for Discord reaction vote endpoint (spec-164 API Changes).

POST /api/ideas/{idea_id}/questions/{question_index}/vote
→ 200 on first vote with aggregate counts
→ 409 on duplicate vote
→ 404 for missing idea or question index
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}

VOTE_PAYLOAD = {
    "polarity": "positive",
    "discord_user_id": "discord_user_123",
}


async def _create_idea_with_question(client: AsyncClient, tmp_path: Path, idea_id: str) -> None:
    """Helper: create a test idea with one open question."""
    res = await client.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": "Test Idea with Question",
            "description": "Used for vote endpoint testing.",
            "potential_value": 100.0,
            "estimated_cost": 10.0,
            "confidence": 0.8,
            "open_questions": [
                {
                    "question": "Does this prove the voting API works?",
                    "value_to_whole": 20.0,
                    "estimated_cost": 2.0,
                }
            ],
        },
        headers=AUTH_HEADERS,
    )
    assert res.status_code in (200, 201), f"Setup failed: {res.text}"


@pytest.mark.asyncio
async def test_vote_returns_200_with_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """First vote returns 200 with aggregate vote counts."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_votes.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_votes.db"

    # Reset DB engine so the new URL is picked up
    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = "vote-test-001"
        await _create_idea_with_question(client, tmp_path, idea_id)

        res = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json=VOTE_PAYLOAD,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["question_index"] == 0
    assert body["votes"]["positive"] == 1
    assert body["votes"]["negative"] == 0
    assert body["votes"]["excited"] == 0
    assert body["your_vote"] == "positive"


@pytest.mark.asyncio
async def test_vote_duplicate_returns_409(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same user voting the same polarity twice returns 409."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_dup.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_dup.db"

    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = "vote-test-002"
        await _create_idea_with_question(client, tmp_path, idea_id)

        # First vote
        r1 = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json=VOTE_PAYLOAD,
        )
        assert r1.status_code == 200

        # Duplicate vote
        r2 = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json=VOTE_PAYLOAD,
        )

    assert r2.status_code == 409, r2.text


@pytest.mark.asyncio
async def test_vote_missing_idea_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Voting on a non-existent idea returns 404."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/ideas/does-not-exist/questions/0/vote",
            json=VOTE_PAYLOAD,
        )

    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_vote_out_of_range_question_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Voting on a question index beyond the list returns 404."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_oor.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_oor.db"

    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = "vote-test-003"
        await _create_idea_with_question(client, tmp_path, idea_id)

        res = await client.post(
            f"/api/ideas/{idea_id}/questions/99/vote",
            json=VOTE_PAYLOAD,
        )

    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_vote_multiple_users_aggregate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multiple users voting increments aggregate counts correctly."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_multi.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_multi.db"

    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = "vote-test-004"
        await _create_idea_with_question(client, tmp_path, idea_id)

        await client.post(f"/api/ideas/{idea_id}/questions/0/vote",
                          json={"polarity": "positive", "discord_user_id": "user_a"})
        await client.post(f"/api/ideas/{idea_id}/questions/0/vote",
                          json={"polarity": "positive", "discord_user_id": "user_b"})
        r3 = await client.post(f"/api/ideas/{idea_id}/questions/0/vote",
                               json={"polarity": "excited", "discord_user_id": "user_c"})

    assert r3.status_code == 200
    body = r3.json()
    assert body["votes"]["positive"] == 2
    assert body["votes"]["excited"] == 1
    assert body["votes"]["negative"] == 0


@pytest.mark.asyncio
async def test_vote_excited_polarity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Excited polarity records correctly."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_excited.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_excited.db"

    import app.services.unified_db as udb
    udb.reset_engine()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = "vote-test-005"
        await _create_idea_with_question(client, tmp_path, idea_id)

        res = await client.post(
            f"/api/ideas/{idea_id}/questions/0/vote",
            json={"polarity": "excited", "discord_user_id": "fan_999"},
        )

    assert res.status_code == 200
    assert res.json()["your_vote"] == "excited"
    assert res.json()["votes"]["excited"] == 1
