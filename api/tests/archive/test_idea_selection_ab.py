"""Tests for A/B idea selection methods."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.idea import Idea, IdeaWithScore, ManifestationStatus
from app.services.idea_service import _score, _marginal_cc_return, _with_score

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Unit tests: scoring functions
# ---------------------------------------------------------------------------


def _make_idea(**overrides) -> Idea:
    defaults = dict(
        id="test",
        name="Test",
        description="Test idea",
        potential_value=100.0,
        actual_value=0.0,
        estimated_cost=10.0,
        actual_cost=0.0,
        resistance_risk=1.0,
        confidence=0.8,
        manifestation_status=ManifestationStatus.NONE,
        interfaces=[],
        open_questions=[],
    )
    defaults.update(overrides)
    return Idea(**defaults)


def test_method_a_and_b_produce_different_rankings():
    """Method A and Method B should rank the same set of ideas differently."""
    # Idea A: nearly done, low cost, small gap
    idea_a = _make_idea(
        id="nearly-done",
        potential_value=20.0,
        actual_value=18.0,
        estimated_cost=2.0,
        actual_cost=1.5,
        confidence=0.9,
        resistance_risk=0.5,
    )
    # Idea B: big opportunity, large gap, more remaining work
    idea_b = _make_idea(
        id="big-opportunity",
        potential_value=100.0,
        actual_value=10.0,
        estimated_cost=20.0,
        actual_cost=2.0,
        confidence=0.7,
        resistance_risk=1.0,
    )

    # Method A (free energy) should rank idea_a higher (high pv*conf / low cost)
    fe_a = _score(idea_a)
    fe_b = _score(idea_b)
    # idea_a: (20*0.9)/(2+0.5) = 18/2.5 = 7.2
    # idea_b: (100*0.7)/(20+1) = 70/21 = 3.33
    assert fe_a > fe_b, "Method A should prefer nearly-done idea"

    # Method B (marginal CC) should rank idea_b higher (big gap, decent confidence)
    mc_a = _marginal_cc_return(idea_a)
    mc_b = _marginal_cc_return(idea_b)
    # idea_a gap=2, remaining=0.5, mc = (2*0.81)/(0.5+0.25) = 1.62/0.75 = 2.16
    # idea_b gap=90, remaining=18, mc = (90*0.49)/(18+0.5) = 44.1/18.5 = 2.38
    assert mc_b > mc_a, "Method B should prefer big-opportunity idea"


def test_method_b_scores_higher_for_big_gap_low_remaining_cost():
    """Method B rewards ideas with large uncaptured value and low remaining cost."""
    idea_big_gap = _make_idea(
        id="big-gap",
        potential_value=100.0,
        actual_value=5.0,
        estimated_cost=10.0,
        actual_cost=9.0,
        confidence=0.8,
        resistance_risk=0.5,
    )
    idea_small_gap = _make_idea(
        id="small-gap",
        potential_value=100.0,
        actual_value=95.0,
        estimated_cost=10.0,
        actual_cost=9.0,
        confidence=0.8,
        resistance_risk=0.5,
    )
    assert _marginal_cc_return(idea_big_gap) > _marginal_cc_return(idea_small_gap)


def test_method_a_scores_higher_for_nearly_done_ideas():
    """Method A (free energy) scores higher for ideas with low total cost."""
    idea_cheap = _make_idea(
        id="cheap",
        potential_value=50.0,
        estimated_cost=2.0,
        confidence=0.9,
        resistance_risk=0.5,
    )
    idea_expensive = _make_idea(
        id="expensive",
        potential_value=50.0,
        estimated_cost=20.0,
        confidence=0.9,
        resistance_risk=0.5,
    )
    assert _score(idea_cheap) > _score(idea_expensive)


def test_with_score_includes_all_fields():
    """_with_score should return IdeaWithScore with all three score fields."""
    idea = _make_idea()
    scored = _with_score(idea)
    assert isinstance(scored, IdeaWithScore)
    assert scored.free_energy_score >= 0.0
    assert scored.value_gap >= 0.0
    assert scored.marginal_cc_score >= 0.0


def test_idea_with_score_has_marginal_cc_score_field():
    """IdeaWithScore model includes marginal_cc_score with default 0.0."""
    idea = _make_idea()
    scored = IdeaWithScore(
        **idea.model_dump(),
        free_energy_score=1.0,
        value_gap=5.0,
    )
    assert scored.marginal_cc_score == 0.0

    scored2 = IdeaWithScore(
        **idea.model_dump(),
        free_energy_score=1.0,
        value_gap=5.0,
        marginal_cc_score=3.14,
    )
    assert scored2.marginal_cc_score == 3.14


# ---------------------------------------------------------------------------
# Integration tests: API endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sort_query_parameter_free_energy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GET /api/ideas?sort=free_energy returns ideas sorted by free_energy_score."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "fe-a", "name": "A", "description": "d",
            "potential_value": 50.0, "estimated_cost": 5.0, "confidence": 0.9,
        }, headers=AUTH_HEADERS)
        await client.post("/api/ideas", json={
            "id": "fe-b", "name": "B", "description": "d",
            "potential_value": 10.0, "estimated_cost": 20.0, "confidence": 0.3,
        }, headers=AUTH_HEADERS)

        resp = await client.get("/api/ideas?sort=free_energy")

    assert resp.status_code == 200
    data = resp.json()
    scores = [i["free_energy_score"] for i in data["ideas"]]
    assert scores == sorted(scores, reverse=True)
    # Every idea should have marginal_cc_score
    assert all("marginal_cc_score" in i for i in data["ideas"])


@pytest.mark.asyncio
async def test_sort_query_parameter_marginal_cc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GET /api/ideas?sort=marginal_cc returns ideas sorted by marginal_cc_score."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "mc-a", "name": "A", "description": "d",
            "potential_value": 100.0, "estimated_cost": 10.0, "confidence": 0.8,
        }, headers=AUTH_HEADERS)
        await client.post("/api/ideas", json={
            "id": "mc-b", "name": "B", "description": "d",
            "potential_value": 5.0, "estimated_cost": 20.0, "confidence": 0.3,
        }, headers=AUTH_HEADERS)

        resp = await client.get("/api/ideas?sort=marginal_cc")

    assert resp.status_code == 200
    data = resp.json()
    scores = [i["marginal_cc_score"] for i in data["ideas"]]
    assert scores == sorted(scores, reverse=True)
    # Every idea should also have free_energy_score
    assert all("free_energy_score" in i for i in data["ideas"])


@pytest.mark.asyncio
async def test_default_sort_is_free_energy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GET /api/ideas with no sort param defaults to free_energy ordering."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "def-a", "name": "A", "description": "d",
            "potential_value": 50.0, "estimated_cost": 5.0, "confidence": 0.9,
        }, headers=AUTH_HEADERS)

        resp_default = await client.get("/api/ideas")
        resp_explicit = await client.get("/api/ideas?sort=free_energy")

    assert resp_default.status_code == 200
    assert resp_explicit.status_code == 200
    default_order = [i["id"] for i in resp_default.json()["ideas"]]
    explicit_order = [i["id"] for i in resp_explicit.json()["ideas"]]
    assert default_order == explicit_order


# ---------------------------------------------------------------------------
# A/B recording and comparison
# ---------------------------------------------------------------------------


def test_record_selection_and_get_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """record_selection writes entries and get_comparison aggregates them."""
    from app.services import idea_selection_ab_service

    log_path = tmp_path / "ab_log.json"
    monkeypatch.setattr(idea_selection_ab_service, "_LOG_PATH", log_path)

    idea_selection_ab_service.record_selection(
        method="free_energy",
        top_picks=[{"idea_id": "a", "score": 5.0, "value_gap": 10.0, "remaining_cost": 2.0}],
        total_remaining_cost_cc=2.0,
        total_value_gap_cc=10.0,
        expected_roi=5.0,
    )
    idea_selection_ab_service.record_selection(
        method="marginal_cc",
        top_picks=[{"idea_id": "b", "score": 8.0, "value_gap": 50.0, "remaining_cost": 7.0}],
        total_remaining_cost_cc=7.0,
        total_value_gap_cc=50.0,
        expected_roi=7.14,
    )

    stats = idea_selection_ab_service.get_comparison()
    assert stats["total_selections"] == 2
    assert "free_energy" in stats["by_method"]
    assert "marginal_cc" in stats["by_method"]
    assert stats["by_method"]["free_energy"]["count"] == 1
    assert stats["by_method"]["marginal_cc"]["count"] == 1
    assert stats["by_method"]["free_energy"]["avg_expected_roi"] == 5.0
    assert stats["by_method"]["marginal_cc"]["avg_expected_roi"] == 7.14


def test_get_comparison_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_comparison returns empty stats when no log file exists."""
    from app.services import idea_selection_ab_service

    monkeypatch.setattr(idea_selection_ab_service, "_LOG_PATH", tmp_path / "nonexistent.json")
    stats = idea_selection_ab_service.get_comparison()
    assert stats == {"total_selections": 0, "by_method": {}}


@pytest.mark.asyncio
async def test_selection_ab_stats_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GET /api/ideas/selection-ab/stats returns comparison data."""
    from app.services import idea_selection_ab_service

    monkeypatch.setattr(idea_selection_ab_service, "_LOG_PATH", tmp_path / "ab_log.json")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/selection-ab/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert "total_selections" in data
    assert "by_method" in data
