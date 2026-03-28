"""Tests for Belief System Interface (spec-169).

Covers:
- GET /api/contributors/{id}/beliefs
- PATCH /api/contributors/{id}/beliefs
- GET /api/contributors/{id}/beliefs/resonance
- GET /api/contributors/{id}/beliefs/roi
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import beliefs_service

client = TestClient(app)

VALID_AXES = ["scientific", "spiritual", "pragmatic", "holistic", "synthetic", "critical", "imaginative"]


@pytest.fixture(autouse=True)
def clear_state(monkeypatch):
    """Clear belief state and inject a fake contributor before each test."""
    beliefs_service.clear_all()

    # Monkey-patch contributor check so we don't need a real graph node
    from app.routers import beliefs as beliefs_router
    monkeypatch.setattr(beliefs_router, "_contributor_exists", lambda cid: cid in {"alice", "bob", "charlie"})
    yield
    beliefs_service.clear_all()


# ---------------------------------------------------------------------------
# GET /api/contributors/{id}/beliefs
# ---------------------------------------------------------------------------

def test_get_beliefs_returns_empty_defaults():
    """Unknown profile returns empty defaults with HTTP 200."""
    r = client.get("/api/contributors/alice/beliefs")
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["worldview_axes"] == {}
    assert body["concept_resonances"] == []
    assert body["tag_affinities"] == {}
    assert body["primary_worldview"] is None


def test_get_beliefs_404_for_unknown_contributor():
    """Non-existent contributor returns 404."""
    r = client.get("/api/contributors/nobody/beliefs")
    assert r.status_code == 404
    assert "nobody" in r.json()["detail"]


# ---------------------------------------------------------------------------
# PATCH /api/contributors/{id}/beliefs
# ---------------------------------------------------------------------------

def test_patch_beliefs_updates_axes():
    """PATCH sets worldview axes and returns updated profile."""
    payload = {"worldview_axes": {"scientific": 0.8, "holistic": 0.6}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["worldview_axes"]["scientific"] == 0.8
    assert body["worldview_axes"]["holistic"] == 0.6


def test_patch_beliefs_merges_axes():
    """PATCH merges axes rather than replacing them."""
    client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": 0.8}})
    client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"holistic": 0.6}})
    r = client.get("/api/contributors/alice/beliefs")
    axes = r.json()["worldview_axes"]
    assert axes.get("scientific") == 0.8
    assert axes.get("holistic") == 0.6


def test_patch_beliefs_updates_tag_affinities():
    """PATCH sets tag_affinities."""
    payload = {"tag_affinities": {"ai": 0.9, "graph-theory": 0.7}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200
    assert r.json()["tag_affinities"]["ai"] == 0.9


def test_patch_beliefs_sets_primary_worldview():
    """PATCH sets primary_worldview."""
    payload = {"primary_worldview": "scientific"}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200
    assert r.json()["primary_worldview"] == "scientific"


def test_patch_beliefs_rejects_invalid_axis():
    """PATCH with an unknown axis name returns 422."""
    payload = {"worldview_axes": {"astrology": 0.5}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 422
    detail = str(r.json())
    assert "astrology" in detail or "valid BeliefAxis" in detail


def test_patch_beliefs_rejects_out_of_range_value():
    """PATCH with axis value > 1.0 returns 422."""
    payload = {"worldview_axes": {"scientific": 1.5}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 422


def test_patch_beliefs_rejects_negative_value():
    """PATCH with axis value < 0.0 returns 422."""
    payload = {"worldview_axes": {"scientific": -0.1}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 422


def test_patch_beliefs_ownership_403():
    """PATCH as a different contributor returns 403."""
    payload = {"worldview_axes": {"scientific": 0.9}}
    r = client.patch(
        "/api/contributors/alice/beliefs",
        json=payload,
        headers={"x-contributor-id": "bob"},
    )
    assert r.status_code == 403


def test_patch_beliefs_own_contributor_succeeds():
    """PATCH as the same contributor succeeds."""
    payload = {"worldview_axes": {"scientific": 0.9}}
    r = client.patch(
        "/api/contributors/alice/beliefs",
        json=payload,
        headers={"x-contributor-id": "alice"},
    )
    assert r.status_code == 200


def test_patch_beliefs_404_for_unknown_contributor():
    """PATCH for non-existent contributor returns 404."""
    r = client.patch("/api/contributors/nobody/beliefs", json={"worldview_axes": {"scientific": 0.5}})
    assert r.status_code == 404


def test_patch_beliefs_persistence():
    """Profile persists across GET calls after PATCH."""
    client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": 0.8}})
    r = client.get("/api/contributors/alice/beliefs")
    assert r.json()["worldview_axes"]["scientific"] == 0.8


# ---------------------------------------------------------------------------
# GET /api/contributors/{id}/beliefs/resonance
# ---------------------------------------------------------------------------

def test_resonance_404_for_unknown_contributor():
    r = client.get("/api/contributors/nobody/beliefs/resonance?idea_id=some-idea")
    assert r.status_code == 404


def test_resonance_404_for_unknown_idea(monkeypatch):
    """Resonance endpoint returns 404 when idea is not found."""
    from app.services import idea_service
    monkeypatch.setattr(idea_service, "get_idea", lambda idea_id: None)

    r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=nonexistent-idea")
    assert r.status_code == 404
    assert "nonexistent-idea" in r.json()["detail"]


def test_resonance_returns_result(monkeypatch):
    """Resonance endpoint returns a ResonanceResult with required fields."""
    from unittest.mock import MagicMock
    from app.services import idea_service

    mock_idea = MagicMock()
    mock_idea.id = "idea-test-001"
    mock_idea.interfaces = ["ai", "graph-theory", "systems"]
    mock_idea.description = "A test idea about emergence and network theory"
    mock_idea.manifestation_status.value = "none"

    monkeypatch.setattr(idea_service, "get_idea", lambda idea_id: mock_idea if idea_id == "idea-test-001" else None)

    # Set up contributor beliefs
    client.patch("/api/contributors/alice/beliefs", json={
        "worldview_axes": {"scientific": 0.8, "holistic": 0.6},
        "tag_affinities": {"ai": 0.9, "graph-theory": 0.7},
    })

    r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=idea-test-001")
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["idea_id"] == "idea-test-001"
    assert 0.0 <= body["overall_score"] <= 1.0
    assert 0.0 <= body["concept_overlap"] <= 1.0
    assert 0.0 <= body["worldview_alignment"] <= 1.0
    assert 0.0 <= body["tag_match"] <= 1.0
    assert isinstance(body["explanation"], list)
    assert len(body["explanation"]) > 0
    assert body["recommended_action"] in ("Contribute", "Follow", "Skip")


def test_resonance_zero_score_is_valid(monkeypatch):
    """ResonanceResult with score=0.0 is valid (not an error)."""
    from unittest.mock import MagicMock
    from app.services import idea_service

    mock_idea = MagicMock()
    mock_idea.id = "idea-empty"
    mock_idea.interfaces = []
    mock_idea.description = "xyz"
    mock_idea.manifestation_status.value = "none"

    monkeypatch.setattr(idea_service, "get_idea", lambda idea_id: mock_idea if idea_id == "idea-empty" else None)

    r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=idea-empty")
    assert r.status_code == 200
    assert r.json()["overall_score"] == 0.0


def test_resonance_high_alignment(monkeypatch):
    """Contributor with strong AI belief + idea with AI tags should score > 0.0."""
    from unittest.mock import MagicMock
    from app.services import idea_service

    mock_idea = MagicMock()
    mock_idea.id = "idea-ai-heavy"
    mock_idea.interfaces = ["ai", "empirical", "data"]
    mock_idea.description = "Data-driven empirical AI research platform"
    mock_idea.manifestation_status.value = "none"

    monkeypatch.setattr(idea_service, "get_idea", lambda idea_id: mock_idea if idea_id == "idea-ai-heavy" else None)

    client.patch("/api/contributors/alice/beliefs", json={
        "worldview_axes": {"scientific": 0.9},
        "tag_affinities": {"ai": 0.9, "data": 0.8},
    })

    r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=idea-ai-heavy")
    assert r.status_code == 200
    assert r.json()["overall_score"] > 0.0


# ---------------------------------------------------------------------------
# GET /api/contributors/{id}/beliefs/roi
# ---------------------------------------------------------------------------

def test_roi_returns_insufficient_data_note():
    """ROI with < 10 events returns null lift and a note."""
    r = client.get("/api/contributors/alice/beliefs/roi?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["contributor_id"] == "alice"
    assert body["recommendations_shown"] == 0
    assert body["lift"] is None
    assert "Insufficient data" in (body.get("note") or "")


def test_roi_404_for_unknown_contributor():
    r = client.get("/api/contributors/nobody/beliefs/roi?days=30")
    assert r.status_code == 404


def test_roi_computes_lift_with_sufficient_data():
    """ROI computes lift when enough events exist."""
    # Inject 10 shown events for alice (4 engaged)
    for i in range(10):
        event_id = beliefs_service.record_recommendation_shown("alice", f"idea-{i}", 0.7)
        if i < 4:
            beliefs_service.record_engagement(event_id, "click")

    # Inject 10 baseline events for another contributor (2 engaged)
    for i in range(10):
        event_id = beliefs_service.record_recommendation_shown("charlie", f"idea-{i}", 0.5)
        if i < 2:
            beliefs_service.record_engagement(event_id, "click")

    r = client.get("/api/contributors/alice/beliefs/roi?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["recommendations_shown"] == 10
    assert body["recommendations_engaged"] == 4
    assert abs(body["engagement_rate"] - 0.4) < 0.01
    assert body["baseline_engagement_rate"] is not None
    assert abs(body["baseline_engagement_rate"] - 0.2) < 0.01
    assert body["lift"] is not None
    assert abs(body["lift"] - 0.2) < 0.01


def test_roi_belief_completeness_reflects_profile():
    """Belief completeness increases as profile is filled."""
    r1 = client.get("/api/contributors/alice/beliefs/roi?days=30")
    completeness_empty = r1.json()["belief_completeness"]

    client.patch("/api/contributors/alice/beliefs", json={
        "worldview_axes": {"scientific": 0.8, "holistic": 0.6, "pragmatic": 0.5,
                           "spiritual": 0.2, "synthetic": 0.4, "critical": 0.3, "imaginative": 0.7},
        "tag_affinities": {"ai": 0.9, "graph": 0.7, "systems": 0.6, "data": 0.5, "emergence": 0.8},
        "primary_worldview": "scientific",
    })

    r2 = client.get("/api/contributors/alice/beliefs/roi?days=30")
    completeness_full = r2.json()["belief_completeness"]

    assert completeness_full > completeness_empty


# ---------------------------------------------------------------------------
# BeliefAxis model validation
# ---------------------------------------------------------------------------

def test_all_valid_axes_accepted():
    """All 7 valid axes are accepted in a PATCH."""
    payload = {"worldview_axes": {axis: 0.5 for axis in VALID_AXES}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200
    body = r.json()
    for axis in VALID_AXES:
        assert body["worldview_axes"][axis] == 0.5


def test_boundary_values_accepted():
    """0.0 and 1.0 are valid axis values."""
    payload = {"worldview_axes": {"scientific": 0.0, "spiritual": 1.0}}
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200


def test_concept_resonances_stored():
    """concept_resonances can be set via PATCH."""
    payload = {
        "concept_resonances": [
            {"concept_id": "c-emergence", "concept_name": "Emergence", "score": 0.9}
        ]
    }
    r = client.patch("/api/contributors/alice/beliefs", json=payload)
    assert r.status_code == 200
    resonances = r.json()["concept_resonances"]
    assert len(resonances) == 1
    assert resonances[0]["concept_id"] == "c-emergence"
    assert resonances[0]["score"] == 0.9
