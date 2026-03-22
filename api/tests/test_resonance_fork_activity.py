"""Tests for resonance feed, fork, and activity timeline features."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_resonance_feed_returns_recently_active_ideas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed an idea
        created = await client.post("/api/ideas", json={
            "id": "resonance-test-1",
            "name": "Resonance Test",
            "description": "Idea for resonance feed test.",
            "potential_value": 40.0,
            "estimated_cost": 8.0,
            "confidence": 0.7,
        }, headers=AUTH_HEADERS)
        assert created.status_code == 201

        # Answer a question to create activity
        await client.post("/api/ideas/resonance-test-1/questions", json={
            "question": "Is this working?",
            "value_to_whole": 10.0,
            "estimated_cost": 2.0,
        }, headers=AUTH_HEADERS)
        await client.post("/api/ideas/resonance-test-1/questions/answer", json={
            "question": "Is this working?",
            "answer": "Yes, confirmed working.",
        }, headers=AUTH_HEADERS)

        resp = await client.get("/api/ideas/resonance", params={"window_hours": 48, "limit": 10})

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # The idea with answered question should appear
    idea_ids = [item["idea_id"] for item in data]
    assert "resonance-test-1" in idea_ids
    # Each entry has expected fields
    for item in data:
        assert "idea_id" in item
        assert "name" in item
        assert "last_activity_at" in item
        assert "free_energy_score" in item


@pytest.mark.asyncio
async def test_fork_creates_new_idea_with_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed source idea
        created = await client.post("/api/ideas", json={
            "id": "fork-source",
            "name": "Source Idea",
            "description": "Original idea to fork.",
            "potential_value": 60.0,
            "estimated_cost": 15.0,
            "confidence": 0.9,
        }, headers=AUTH_HEADERS)
        assert created.status_code == 201

        # Fork it
        resp = await client.post(
            "/api/ideas/fork-source/fork",
            params={"forker_id": "user-42", "adaptation_notes": "Adapting for a new domain."},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "idea" in data
    assert "lineage_link_id" in data
    assert data["source_idea_id"] == "fork-source"

    idea = data["idea"]
    assert idea["parent_idea_id"] == "fork-source"
    assert idea["name"].startswith("Fork of:")
    assert idea["id"].startswith("fork-fork-source-")
    # Confidence should be 0.9 * 0.8 = 0.72
    assert abs(idea["confidence"] - 0.72) < 0.01
    assert idea["manifestation_status"] == "none"


@pytest.mark.asyncio
async def test_fork_creates_value_lineage_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed source idea
        await client.post("/api/ideas", json={
            "id": "fork-lineage-src",
            "name": "Lineage Source",
            "description": "Source for lineage test.",
            "potential_value": 50.0,
            "estimated_cost": 10.0,
            "confidence": 0.8,
        }, headers=AUTH_HEADERS)

        # Fork
        resp = await client.post(
            "/api/ideas/fork-lineage-src/fork",
            params={"forker_id": "researcher-1"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        link_id = data["lineage_link_id"]

        # Verify lineage link exists
        link_resp = await client.get(f"/api/value-lineage/links/{link_id}")

    assert link_resp.status_code == 200
    link_data = link_resp.json()
    assert link_data["id"] == link_id
    assert link_data["contributors"]["research"] == "researcher-1"


@pytest.mark.asyncio
async def test_activity_timeline_returns_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed idea with a question
        await client.post("/api/ideas", json={
            "id": "activity-test",
            "name": "Activity Test",
            "description": "Testing activity timeline.",
            "potential_value": 30.0,
            "estimated_cost": 5.0,
            "confidence": 0.6,
        }, headers=AUTH_HEADERS)

        await client.post("/api/ideas/activity-test/questions", json={
            "question": "What metrics matter?",
            "value_to_whole": 8.0,
            "estimated_cost": 1.5,
        }, headers=AUTH_HEADERS)

        resp = await client.get("/api/ideas/activity-test/activity", params={"limit": 10})

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each event has required fields
    for event in data:
        assert "type" in event
        assert "timestamp" in event
        assert "summary" in event
        assert event["type"] in (
            "change_request", "question_added", "question_answered",
            "stage_advanced", "value_recorded",
        )


@pytest.mark.asyncio
async def test_activity_timeline_404_for_missing_idea(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/nonexistent-idea/activity")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fork_404_for_missing_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/nonexistent-source/fork",
            params={"forker_id": "user-1"},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 404
