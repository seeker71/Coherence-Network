"""Acceptance tests for GET /api/ideas/health (spec 126)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


async def _seed_ideas(client: AsyncClient) -> None:
    """Seed a mix of ideas for governance health testing."""
    # Validated idea with progress
    await client.post("/api/ideas", json={
        "id": "gov-validated",
        "name": "Validated Idea",
        "description": "Already validated.",
        "potential_value": 100.0,
        "estimated_cost": 20.0,
        "actual_value": 80.0,
        "actual_cost": 15.0,
        "manifestation_status": "validated",
    }, headers=AUTH_HEADERS)

    # In-progress idea (has actual cost/value, not validated)
    await client.post("/api/ideas", json={
        "id": "gov-in-progress",
        "name": "In Progress",
        "description": "Being worked on.",
        "potential_value": 50.0,
        "estimated_cost": 10.0,
        "actual_value": 10.0,
        "actual_cost": 5.0,
    }, headers=AUTH_HEADERS)

    # Stale idea (no progress, not validated)
    await client.post("/api/ideas", json={
        "id": "gov-stale",
        "name": "Stale Idea",
        "description": "No progress recorded.",
        "potential_value": 30.0,
        "estimated_cost": 8.0,
    }, headers=AUTH_HEADERS)

    # Idea with questions (one answered, one not)
    resp = await client.post("/api/ideas", json={
        "id": "gov-questions",
        "name": "Questions Idea",
        "description": "Has open questions.",
        "potential_value": 40.0,
        "estimated_cost": 12.0,
        "open_questions": [
            {"question": "Is this viable?", "value_to_whole": 5.0, "estimated_cost": 1.0},
            {"question": "What is the ROI?", "value_to_whole": 3.0, "estimated_cost": 0.5},
        ],
    }, headers=AUTH_HEADERS)
    # Answer one question
    await client.post("/api/ideas/gov-questions/questions/answer", json={
        "question": "Is this viable?",
        "answer": "Yes, confirmed viable.",
    }, headers=AUTH_HEADERS)


@pytest.mark.asyncio
async def test_health_returns_200_with_all_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1: GET /api/ideas/health returns GovernanceHealth with all fields."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _seed_ideas(client)
        resp = await client.get("/api/ideas/health")

    assert resp.status_code == 200
    data = resp.json()
    required_fields = {
        "governance_score", "throughput_rate", "value_gap_trend",
        "question_answer_rate", "stale_ideas", "total_ideas",
        "validated_ideas", "snapshot_at", "window_days",
    }
    assert required_fields.issubset(data.keys()), f"Missing: {required_fields - data.keys()}"
    assert data["total_ideas"] >= 4
    assert data["validated_ideas"] >= 1
    assert data["window_days"] == 30


@pytest.mark.asyncio
async def test_governance_score_bounded_0_to_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R6: governance_score is always in [0.0, 1.0]."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _seed_ideas(client)
        resp = await client.get("/api/ideas/health")

    score = resp.json()["governance_score"]
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_stale_ideas_excludes_validated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R5: stale_ideas never includes validated ideas."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _seed_ideas(client)
        resp = await client.get("/api/ideas/health")

    stale = resp.json()["stale_ideas"]
    # Validated ideas must never appear as stale
    assert "gov-validated" not in stale
    # In-progress idea (has actual_value > 0) must not be stale
    assert "gov-in-progress" not in stale
    # No-progress idea must be stale
    assert "gov-stale" in stale


@pytest.mark.asyncio
async def test_question_answer_rate_correct(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R4: question_answer_rate = answered / total questions."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _seed_ideas(client)
        resp = await client.get("/api/ideas/health")

    rate = resp.json()["question_answer_rate"]
    # 1 answered out of 6 total (2 seeded + 4 auto-added standing questions) ≈ 0.167
    assert 0.0 < rate < 1.0
    assert rate == pytest.approx(1.0 / 6.0, abs=0.02)


@pytest.mark.asyncio
async def test_custom_window_days(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R7: window_days parameter is passed through."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _seed_ideas(client)
        resp = await client.get("/api/ideas/health?window_days=7")

    assert resp.status_code == 200
    assert resp.json()["window_days"] == 7
