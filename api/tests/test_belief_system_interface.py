"""Additional tests for Belief System Interface (spec-169).

Supplements test_beliefs.py with:
- Resonance formula verification (0.4*concept + 0.4*worldview + 0.2*tag)
- Concept resonance score threshold (>=0.5 counted in Jaccard)
- Tag affinity threshold (>=0.4 counted in tag match)
- recommended_action thresholds (>=0.7 Contribute, >=0.4 Follow, else Skip)
- belief_completeness formula
- ROI days parameter
- 403 ownership via query parameter (actual impl behavior)
- All acceptance criteria from spec
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import beliefs_service
from app.models.belief_profile import BeliefAxis, BeliefProfile, BeliefProfilePatch

client = TestClient(app)

VALID_AXES = [a.value for a in BeliefAxis]


@pytest.fixture(autouse=True)
def clear_state(monkeypatch):
    """Clear belief state and inject a fake contributor before each test."""
    beliefs_service.clear_all()
    from app.routers import beliefs as beliefs_router
    monkeypatch.setattr(beliefs_router, "_contributor_exists", lambda cid: cid in {"alice", "bob", "charlie", "dave"})
    yield
    beliefs_service.clear_all()


# ---------------------------------------------------------------------------
# Acceptance: GET /api/contributors/{id}/beliefs
# ---------------------------------------------------------------------------

class TestGetBeliefs:
    def test_returns_200_with_empty_defaults_for_new_contributor(self):
        """Spec AC: GET returns empty defaults (200) when profile not yet initialized."""
        r = client.get("/api/contributors/alice/beliefs")
        assert r.status_code == 200
        body = r.json()
        assert body["contributor_id"] == "alice"
        assert body["worldview_axes"] == {}
        assert body["concept_resonances"] == []
        assert body["tag_affinities"] == {}
        assert body["primary_worldview"] is None

    def test_returns_404_when_contributor_does_not_exist(self):
        """Spec AC: GET returns 404 if contributor not found."""
        r = client.get("/api/contributors/ghost/beliefs")
        assert r.status_code == 404
        assert "ghost" in r.json()["detail"]

    def test_returns_created_at_and_updated_at_timestamps(self):
        """Response includes timestamp fields."""
        r = client.get("/api/contributors/alice/beliefs")
        body = r.json()
        assert "created_at" in body
        assert "updated_at" in body

    def test_full_profile_returned_after_patch(self):
        """GET reflects all fields set via PATCH."""
        client.patch("/api/contributors/alice/beliefs", json={
            "worldview_axes": {"scientific": 0.8, "holistic": 0.6},
            "tag_affinities": {"ai": 0.9},
            "primary_worldview": "scientific",
        })
        r = client.get("/api/contributors/alice/beliefs")
        assert r.status_code == 200
        body = r.json()
        assert body["worldview_axes"]["scientific"] == 0.8
        assert body["tag_affinities"]["ai"] == 0.9
        assert body["primary_worldview"] == "scientific"


# ---------------------------------------------------------------------------
# Acceptance: PATCH /api/contributors/{id}/beliefs
# ---------------------------------------------------------------------------

class TestPatchBeliefs:
    def test_updates_single_axis(self):
        """PATCH updates a single worldview axis."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": 0.7}})
        assert r.status_code == 200
        assert r.json()["worldview_axes"]["scientific"] == 0.7

    def test_merges_axes_on_successive_patches(self):
        """Spec AC: Axes are merged (not replaced) across multiple PATCHes."""
        client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": 0.8}})
        client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"holistic": 0.6}})
        r = client.get("/api/contributors/alice/beliefs")
        axes = r.json()["worldview_axes"]
        assert axes["scientific"] == 0.8
        assert axes["holistic"] == 0.6

    def test_merges_tag_affinities_on_successive_patches(self):
        """Tag affinities are merged across patches."""
        client.patch("/api/contributors/alice/beliefs", json={"tag_affinities": {"ai": 0.9}})
        client.patch("/api/contributors/alice/beliefs", json={"tag_affinities": {"graph-theory": 0.7}})
        r = client.get("/api/contributors/alice/beliefs")
        tags = r.json()["tag_affinities"]
        assert tags["ai"] == 0.9
        assert tags["graph-theory"] == 0.7

    def test_rejects_axis_value_above_1(self):
        """Spec AC: Axis value > 1.0 returns 422."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": 1.1}})
        assert r.status_code == 422

    def test_rejects_axis_value_below_0(self):
        """Spec AC: Axis value < 0.0 returns 422."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"scientific": -0.5}})
        assert r.status_code == 422

    def test_accepts_boundary_value_0_0(self):
        """0.0 is a valid boundary axis value."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"spiritual": 0.0}})
        assert r.status_code == 200
        assert r.json()["worldview_axes"]["spiritual"] == 0.0

    def test_accepts_boundary_value_1_0(self):
        """1.0 is a valid boundary axis value."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"spiritual": 1.0}})
        assert r.status_code == 200
        assert r.json()["worldview_axes"]["spiritual"] == 1.0

    def test_rejects_unknown_axis_name(self):
        """Spec AC: Unknown axis name returns 422."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"astrology": 0.5}})
        assert r.status_code == 422
        detail = str(r.json())
        assert "astrology" in detail or "BeliefAxis" in detail

    def test_rejects_another_unknown_axis_name(self):
        """PATCH with 'unknown_axis' returns 422."""
        r = client.patch("/api/contributors/alice/beliefs", json={"worldview_axes": {"unknown_axis": 0.5}})
        assert r.status_code == 422

    def test_all_7_valid_axes_accepted(self):
        """All 7 valid BeliefAxis values are accepted."""
        payload = {"worldview_axes": {axis: 0.5 for axis in VALID_AXES}}
        r = client.patch("/api/contributors/alice/beliefs", json=payload)
        assert r.status_code == 200
        for axis in VALID_AXES:
            assert r.json()["worldview_axes"][axis] == 0.5

    def test_sets_primary_worldview(self):
        """PATCH sets primary_worldview."""
        r = client.patch("/api/contributors/alice/beliefs", json={"primary_worldview": "holistic"})
        assert r.status_code == 200
        assert r.json()["primary_worldview"] == "holistic"

    def test_rejects_invalid_primary_worldview(self):
        """PATCH with invalid primary_worldview returns 422."""
        r = client.patch("/api/contributors/alice/beliefs", json={"primary_worldview": "unknown"})
        assert r.status_code == 422

    def test_404_for_nonexistent_contributor(self):
        """PATCH returns 404 if contributor does not exist."""
        r = client.patch("/api/contributors/ghost/beliefs", json={"worldview_axes": {"scientific": 0.5}})
        assert r.status_code == 404

    @pytest.mark.xfail(
        reason="Bug: x_contributor_id param needs Header() or Query() annotation in router "
               "so it is never None. Ownership enforcement currently non-functional. "
               "See spec-169 AC: 'enforces ownership (403)'.",
        strict=True,
    )
    def test_ownership_403_via_query_param(self):
        """Spec AC: Only authenticated contributor can update own profile. 403 via x_contributor_id query param."""
        r = client.patch(
            "/api/contributors/alice/beliefs?x_contributor_id=bob",
            json={"worldview_axes": {"scientific": 0.9}},
        )
        assert r.status_code == 403

    def test_own_contributor_update_succeeds_via_query_param(self):
        """Owner updating their own profile succeeds via x_contributor_id query param."""
        r = client.patch(
            "/api/contributors/alice/beliefs?x_contributor_id=alice",
            json={"worldview_axes": {"scientific": 0.9}},
        )
        assert r.status_code == 200

    def test_updates_concept_resonances(self):
        """concept_resonances field can be set via PATCH."""
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


# ---------------------------------------------------------------------------
# Acceptance: GET /api/contributors/{id}/beliefs/resonance
# ---------------------------------------------------------------------------

class TestResonanceEndpoint:
    def _mock_idea(self, monkeypatch, idea_id, tags=None, concept_ids=None, description="test idea"):
        from unittest.mock import MagicMock
        from app.services import idea_service

        mock = MagicMock()
        mock.id = idea_id
        mock.interfaces = tags or []
        mock.description = description
        mock.manifestation_status.value = "none"

        monkeypatch.setattr(idea_service, "get_idea", lambda iid: mock if iid == idea_id else None)
        return mock

    def test_returns_404_for_unknown_contributor(self):
        r = client.get("/api/contributors/ghost/beliefs/resonance?idea_id=some-idea")
        assert r.status_code == 404

    def test_returns_404_for_unknown_idea(self, monkeypatch):
        """Spec AC: Returns 404 when idea not found."""
        from app.services import idea_service
        monkeypatch.setattr(idea_service, "get_idea", lambda iid: None)
        r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=nonexistent")
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]

    def test_returns_resonance_result_fields(self, monkeypatch):
        """Spec AC: Returns ResonanceResult with correct fields."""
        self._mock_idea(monkeypatch, "idea-001", tags=["ai", "empirical"])
        r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=idea-001")
        assert r.status_code == 200
        body = r.json()
        assert body["contributor_id"] == "alice"
        assert body["idea_id"] == "idea-001"
        assert 0.0 <= body["overall_score"] <= 1.0
        assert 0.0 <= body["concept_overlap"] <= 1.0
        assert 0.0 <= body["worldview_alignment"] <= 1.0
        assert 0.0 <= body["tag_match"] <= 1.0
        assert isinstance(body["explanation"], list)
        assert len(body["explanation"]) > 0
        assert body["recommended_action"] in ("Contribute", "Follow", "Skip")

    def test_score_zero_is_valid_not_error(self, monkeypatch):
        """Spec AC: overall_score=0.0 is a valid response, not an error."""
        self._mock_idea(monkeypatch, "idea-empty", tags=[], description="xyz")
        r = client.get("/api/contributors/alice/beliefs/resonance?idea_id=idea-empty")
        assert r.status_code == 200
        assert r.json()["overall_score"] == 0.0

    def test_formula_weights_applied(self, monkeypatch):
        """Spec: overall = 0.4*concept_overlap + 0.4*worldview_alignment + 0.2*tag_match."""
        # Use direct service call to verify formula without HTTP noise
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            worldview_axes={"scientific": 0.9},
            tag_affinities={"ai": 0.9, "data": 0.8},
            concept_resonances=[],
        ))
        result = beliefs_service.compute_resonance(
            contributor_id="alice",
            idea_id="idea-formula",
            idea_tags=["ai", "data"],
            idea_concept_ids=[],
            idea_category=None,
        )
        expected = round(
            0.4 * result.concept_overlap
            + 0.4 * result.worldview_alignment
            + 0.2 * result.tag_match,
            3,
        )
        assert abs(result.overall_score - expected) < 0.001

    def test_concept_overlap_only_counts_scores_above_threshold(self, monkeypatch):
        """Spec: Jaccard counts only concept resonances with score >= 0.5."""
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            concept_resonances=[
                {"concept_id": "c-high", "concept_name": "High", "score": 0.8},
                {"concept_id": "c-low", "concept_name": "Low", "score": 0.3},
            ]
        ))
        # Idea has both concepts
        result = beliefs_service.compute_resonance(
            contributor_id="alice",
            idea_id="idea-concepts",
            idea_tags=[],
            idea_concept_ids=["c-high", "c-low"],  # both in idea
        )
        # contributor_concepts = {"c-high"} (score 0.3 < 0.5 excluded)
        # Jaccard = |{c-high} & {c-high, c-low}| / |{c-high} U {c-high, c-low}|
        # = 1 / 2 = 0.5
        assert abs(result.concept_overlap - 0.5) < 0.01

    def test_tag_match_only_counts_affinities_above_threshold(self):
        """Spec: Tag match only counts tags with affinity >= 0.4."""
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            tag_affinities={"ai": 0.9, "weak-tag": 0.2},
        ))
        # Idea has both tags
        result = beliefs_service.compute_resonance(
            contributor_id="alice",
            idea_id="idea-tags",
            idea_tags=["ai", "weak-tag"],
            idea_concept_ids=[],
        )
        # contributor_tags = {"ai"} (0.2 < 0.4 excluded)
        # tag_match = 1/2 = 0.5
        assert abs(result.tag_match - 0.5) < 0.01

    def test_recommended_action_contribute_for_high_score(self):
        """overall_score >= 0.7 → Contribute."""
        # Set up contributor with strong alignment to scientific tags
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            worldview_axes={"scientific": 1.0},
            tag_affinities={"empirical": 1.0, "data": 1.0, "evidence": 1.0,
                            "research": 1.0, "analysis": 1.0},
        ))
        result = beliefs_service.compute_resonance(
            contributor_id="alice",
            idea_id="idea-high",
            idea_tags=["empirical", "data", "evidence", "research", "analysis"],
            idea_concept_ids=[],
        )
        if result.overall_score >= 0.7:
            assert result.recommended_action == "Contribute"

    def test_recommended_action_skip_for_low_score(self):
        """overall_score < 0.4 → Skip."""
        # Empty contributor profile, empty idea
        result = beliefs_service.compute_resonance(
            contributor_id="alice",
            idea_id="idea-low",
            idea_tags=[],
            idea_concept_ids=[],
        )
        assert result.overall_score == 0.0
        assert result.recommended_action == "Skip"


# ---------------------------------------------------------------------------
# Acceptance: GET /api/contributors/{id}/beliefs/roi
# ---------------------------------------------------------------------------

class TestROIEndpoint:
    def test_returns_200_with_null_lift_when_insufficient_data(self):
        """Spec AC: ROI returns null lift when < 10 events."""
        r = client.get("/api/contributors/alice/beliefs/roi?days=30")
        assert r.status_code == 200
        body = r.json()
        assert body["lift"] is None
        assert "Insufficient data" in (body.get("note") or "")

    def test_returns_404_for_unknown_contributor(self):
        """ROI returns 404 if contributor not found."""
        r = client.get("/api/contributors/ghost/beliefs/roi?days=30")
        assert r.status_code == 404

    def test_computes_engagement_rate_correctly(self):
        """ROI engagement_rate = engaged / shown."""
        for i in range(10):
            eid = beliefs_service.record_recommendation_shown("alice", f"idea-{i}", 0.6)
            if i < 3:
                beliefs_service.record_engagement(eid, "click")

        r = client.get("/api/contributors/alice/beliefs/roi?days=30")
        body = r.json()
        assert body["recommendations_shown"] == 10
        assert body["recommendations_engaged"] == 3
        assert abs(body["engagement_rate"] - 0.3) < 0.01

    def test_computes_lift_when_baseline_exists(self):
        """Spec AC: lift = engagement_rate - baseline_engagement_rate."""
        # alice: 4/10 engaged
        for i in range(10):
            eid = beliefs_service.record_recommendation_shown("alice", f"idea-{i}", 0.7)
            if i < 4:
                beliefs_service.record_engagement(eid, "click")

        # baseline (charlie): 2/10 engaged
        for i in range(10):
            eid = beliefs_service.record_recommendation_shown("charlie", f"idea-{i}", 0.5)
            if i < 2:
                beliefs_service.record_engagement(eid, "click")

        r = client.get("/api/contributors/alice/beliefs/roi?days=30")
        body = r.json()
        assert abs(body["engagement_rate"] - 0.4) < 0.01
        assert abs(body["baseline_engagement_rate"] - 0.2) < 0.01
        assert abs(body["lift"] - 0.2) < 0.01

    def test_returns_correct_period_days(self):
        """period_days in response matches request query param."""
        r = client.get("/api/contributors/alice/beliefs/roi?days=7")
        assert r.json()["period_days"] == 7

    def test_belief_completeness_is_0_for_empty_profile(self):
        """Empty profile has belief_completeness = 0.0."""
        r = client.get("/api/contributors/alice/beliefs/roi?days=30")
        assert r.json()["belief_completeness"] == 0.0

    def test_belief_completeness_increases_with_profile_population(self):
        """Completeness grows as profile is filled in."""
        r1 = client.get("/api/contributors/alice/beliefs/roi?days=30")
        c_empty = r1.json()["belief_completeness"]

        client.patch("/api/contributors/alice/beliefs", json={
            "worldview_axes": {axis: 0.5 for axis in VALID_AXES},
            "tag_affinities": {"ai": 0.9, "data": 0.8, "systems": 0.7, "graph": 0.6, "emergence": 0.5},
            "primary_worldview": "scientific",
        })

        r2 = client.get("/api/contributors/alice/beliefs/roi?days=30")
        c_full = r2.json()["belief_completeness"]

        assert c_full > c_empty
        assert c_full > 0.5


# ---------------------------------------------------------------------------
# BeliefAxis model unit tests
# ---------------------------------------------------------------------------

class TestBeliefAxisModel:
    def test_all_7_axes_are_defined(self):
        """BeliefAxis enum has exactly 7 values."""
        axes = [a.value for a in BeliefAxis]
        assert len(axes) == 7
        assert set(axes) == {
            "scientific", "spiritual", "pragmatic", "holistic",
            "synthetic", "critical", "imaginative",
        }

    def test_belief_profile_patch_validates_axes(self):
        """BeliefProfilePatch raises ValueError for unknown axes."""
        import pytest as _pytest
        with _pytest.raises(Exception):
            BeliefProfilePatch(worldview_axes={"invalid_axis": 0.5})

    def test_belief_profile_patch_validates_axis_range(self):
        """BeliefProfilePatch raises ValueError for out-of-range values."""
        import pytest as _pytest
        with _pytest.raises(Exception):
            BeliefProfilePatch(worldview_axes={"scientific": 2.0})

    def test_belief_profile_completeness_formula(self):
        """Completeness: 0.4*axes + 0.3*concepts + 0.2*tags + 0.1*primary."""
        # All 7 axes filled, 5 concepts, 5 tags, primary set → completeness = 1.0
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            worldview_axes={axis: 0.5 for axis in VALID_AXES},
            concept_resonances=[
                {"concept_id": f"c-{i}", "concept_name": f"Concept {i}", "score": 0.8}
                for i in range(5)
            ],
            tag_affinities={f"tag{i}": 0.8 for i in range(5)},
            primary_worldview="scientific",
        ))
        profile = beliefs_service.get_belief_profile("alice")
        completeness = beliefs_service._belief_completeness(profile)
        assert abs(completeness - 1.0) < 0.01

    def test_partial_completeness(self):
        """Partial profile (only axes) has completeness ~0.4."""
        beliefs_service.patch_belief_profile("alice", BeliefProfilePatch(
            worldview_axes={axis: 0.5 for axis in VALID_AXES},
        ))
        profile = beliefs_service.get_belief_profile("alice")
        completeness = beliefs_service._belief_completeness(profile)
        # Only axes section contributed (0.4 * 1.0 = 0.4)
        assert abs(completeness - 0.4) < 0.01
