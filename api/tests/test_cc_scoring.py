"""Tests for CC-denominated scoring wired into IdeaWithScore."""
from __future__ import annotations

from app.models.idea import Idea, ManifestationStatus
from app.services.idea_service import _build_cost_vector, _build_value_vector, _with_score


def _make_idea(**overrides) -> Idea:
    defaults = dict(
        id="test-cc",
        name="CC Test",
        description="Unit test idea for CC scoring.",
        potential_value=100.0,
        actual_value=20.0,
        estimated_cost=40.0,
        actual_cost=10.0,
        resistance_risk=2.0,
        confidence=0.7,
        manifestation_status=ManifestationStatus.NONE,
    )
    defaults.update(overrides)
    return Idea(**defaults)


class TestBuildCostVector:
    def test_field_sum_equals_total(self) -> None:
        idea = _make_idea(estimated_cost=40.0)
        cv = _build_cost_vector(idea)
        component_sum = cv.compute_cc + cv.infrastructure_cc + cv.human_attention_cc + cv.opportunity_cc + cv.external_cc
        assert round(component_sum, 4) == cv.total_cc

    def test_total_equals_estimated_cost(self) -> None:
        idea = _make_idea(estimated_cost=55.5)
        cv = _build_cost_vector(idea)
        assert cv.total_cc == round(55.5, 4)

    def test_heuristic_proportions(self) -> None:
        idea = _make_idea(estimated_cost=100.0)
        cv = _build_cost_vector(idea)
        assert cv.compute_cc == 60.0
        assert cv.human_attention_cc == 25.0
        assert cv.infrastructure_cc == 15.0

    def test_zero_cost(self) -> None:
        idea = _make_idea(estimated_cost=0.0)
        cv = _build_cost_vector(idea)
        assert cv.total_cc == 0.0
        assert cv.compute_cc == 0.0


class TestBuildValueVector:
    def test_field_sum_equals_total(self) -> None:
        idea = _make_idea(potential_value=100.0)
        vv = _build_value_vector(idea)
        component_sum = vv.adoption_cc + vv.lineage_cc + vv.friction_avoided_cc + vv.revenue_cc
        assert round(component_sum, 4) == vv.total_cc

    def test_total_equals_potential_value(self) -> None:
        idea = _make_idea(potential_value=80.0)
        vv = _build_value_vector(idea)
        assert vv.total_cc == round(80.0, 4)

    def test_heuristic_proportions(self) -> None:
        idea = _make_idea(potential_value=200.0)
        vv = _build_value_vector(idea)
        assert vv.adoption_cc == 100.0
        assert vv.lineage_cc == 60.0
        assert vv.friction_avoided_cc == 40.0

    def test_zero_value(self) -> None:
        idea = _make_idea(potential_value=0.0)
        vv = _build_value_vector(idea)
        assert vv.total_cc == 0.0


class TestWithScoreCCFields:
    def test_cost_vector_populated(self) -> None:
        idea = _make_idea()
        scored = _with_score(idea)
        assert scored.cost_vector is not None
        assert scored.cost_vector.total_cc == round(idea.estimated_cost, 4)

    def test_value_vector_populated(self) -> None:
        idea = _make_idea()
        scored = _with_score(idea)
        assert scored.value_vector is not None
        assert scored.value_vector.total_cc == round(idea.potential_value, 4)

    def test_remaining_cost_cc(self) -> None:
        idea = _make_idea(estimated_cost=40.0, actual_cost=10.0)
        scored = _with_score(idea)
        assert scored.remaining_cost_cc == 30.0

    def test_remaining_cost_cc_no_negative(self) -> None:
        idea = _make_idea(estimated_cost=5.0, actual_cost=20.0)
        scored = _with_score(idea)
        assert scored.remaining_cost_cc == 0.0

    def test_value_gap_cc(self) -> None:
        idea = _make_idea(potential_value=100.0, actual_value=20.0)
        scored = _with_score(idea)
        assert scored.value_gap_cc == 80.0

    def test_roi_cc(self) -> None:
        idea = _make_idea(potential_value=100.0, actual_value=20.0, estimated_cost=40.0, actual_cost=10.0)
        scored = _with_score(idea)
        # value_gap_cc=80, remaining_cost_cc=30, roi=80/30
        expected = round(80.0 / 30.0, 4)
        assert scored.roi_cc == expected

    def test_roi_cc_zero_remaining(self) -> None:
        idea = _make_idea(estimated_cost=10.0, actual_cost=10.0)
        scored = _with_score(idea)
        assert scored.roi_cc == 0.0

    def test_existing_vectors_preserved(self) -> None:
        """If the idea already has cost_vector/value_vector, _with_score should use them."""
        from app.models.coherence_credit import CostVector, ValueVector
        custom_cv = CostVector(total_cc=99.0, compute_cc=99.0)
        custom_vv = ValueVector(total_cc=88.0, adoption_cc=88.0)
        idea = _make_idea(cost_vector=custom_cv, value_vector=custom_vv)
        scored = _with_score(idea)
        assert scored.cost_vector.total_cc == 99.0
        assert scored.value_vector.total_cc == 88.0
