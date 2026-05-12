"""Tests for idea_scoring (spec: ideas-prioritization).

Pure functions extracted from idea_service.py (#163) — no DB, no cache,
no I/O. Used internally by select_idea, list_ideas, and the
IdeaWithScore wrapper.

Public surface tested:
  _score                — free-energy score
  _marginal_cc_return   — Method B scoring (uncaptured value per remaining CC)
  _build_cost_vector    — decompose estimated_cost into CC types
  _build_value_vector   — decompose potential_value into CC value types
  _with_score           — wrap Idea with score + vectors + ROI fields
  _softmax_weights      — temperature-controlled probability weights
"""
from __future__ import annotations

import math

from app.models.idea import Idea
from app.services.idea_scoring import (
    _build_cost_vector,
    _build_value_vector,
    _marginal_cc_return,
    _score,
    _softmax_weights,
    _with_score,
)


def _idea(
    *,
    name: str = "test-idea",
    potential_value: float = 100.0,
    actual_value: float = 0.0,
    estimated_cost: float = 50.0,
    actual_cost: float = 0.0,
    resistance_risk: float = 1.0,
    confidence: float = 0.5,
) -> Idea:
    return Idea(
        id=name,
        name=name,
        description="for test",
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        resistance_risk=resistance_risk,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# _score
# ---------------------------------------------------------------------------


def test_score_applies_free_energy_formula():
    """(potential_value × confidence) / max(estimated_cost + resistance_risk, 0.5)."""
    idea = _idea(potential_value=100, confidence=0.5, estimated_cost=10, resistance_risk=5)
    # (100 × 0.5) / max(10 + 5, 0.5) = 50 / 15 ≈ 3.333...
    assert _score(idea) == 50.0 / 15.0


def test_score_floors_denominator_at_half():
    """When estimated_cost + resistance_risk is tiny, denom floors at 0.5 — no astronomical score."""
    idea = _idea(potential_value=100, confidence=1.0, estimated_cost=0.0, resistance_risk=0.0)
    # denom = max(0.0, 0.5) = 0.5; score = 100 × 1.0 / 0.5 = 200
    assert _score(idea) == 200.0


def test_score_zero_when_no_potential_value():
    """An idea with no potential_value scores zero."""
    idea = _idea(potential_value=0.0)
    assert _score(idea) == 0.0


# ---------------------------------------------------------------------------
# _build_cost_vector / _build_value_vector
# ---------------------------------------------------------------------------


def test_build_cost_vector_decomposes_60_15_25():
    """estimated_cost decomposes 60% compute / 15% infra / 25% human attention."""
    cv = _build_cost_vector(_idea(estimated_cost=100.0))
    assert cv.compute_cc == 60.0
    assert cv.infrastructure_cc == 15.0
    assert cv.human_attention_cc == 25.0
    assert cv.opportunity_cc == 0.0
    assert cv.external_cc == 0.0
    assert cv.total_cc == 100.0


def test_build_value_vector_decomposes_50_30_20():
    """potential_value decomposes 50% adoption / 30% lineage / 20% friction-avoided."""
    vv = _build_value_vector(_idea(potential_value=100.0))
    assert vv.adoption_cc == 50.0
    assert vv.lineage_cc == 30.0
    assert vv.friction_avoided_cc == 20.0
    assert vv.revenue_cc == 0.0
    assert vv.total_cc == 100.0


def test_build_cost_vector_zero_inputs():
    """Zero estimated_cost yields zero across all axes (no NaN, no negatives)."""
    cv = _build_cost_vector(_idea(estimated_cost=0.0))
    assert cv.compute_cc == 0.0
    assert cv.infrastructure_cc == 0.0
    assert cv.human_attention_cc == 0.0
    assert cv.total_cc == 0.0


# ---------------------------------------------------------------------------
# _with_score
# ---------------------------------------------------------------------------


def test_with_score_wraps_idea_with_score_and_vectors():
    """_with_score produces IdeaWithScore with derived fields populated."""
    idea = _idea(potential_value=100, actual_value=20, estimated_cost=40, actual_cost=10, confidence=0.8, resistance_risk=2)
    wrapped = _with_score(idea)

    # value_gap = max(pv - av, 0)
    assert wrapped.value_gap == 80.0
    assert wrapped.value_gap_cc == 80.0
    # remaining_cost_cc = max(ec - ac, 0)
    assert wrapped.remaining_cost_cc == 30.0
    # roi_cc = value_gap_cc / remaining_cost_cc
    assert wrapped.roi_cc == round(80.0 / 30.0, 4)
    # score = _score(idea) rounded
    assert wrapped.free_energy_score == round(_score(idea), 4)
    # vectors present
    assert wrapped.cost_vector is not None
    assert wrapped.value_vector is not None


def test_with_score_clamps_value_gap_at_zero():
    """When actual_value exceeds potential_value (overdelivery), value_gap clamps at 0."""
    idea = _idea(potential_value=50, actual_value=80)
    wrapped = _with_score(idea)
    assert wrapped.value_gap == 0.0


def test_with_score_roi_zero_when_no_remaining_cost():
    """When the idea is fully spent (remaining_cost == 0), roi_cc is 0 (no division by zero)."""
    idea = _idea(estimated_cost=10, actual_cost=10, potential_value=100, actual_value=0)
    wrapped = _with_score(idea)
    assert wrapped.remaining_cost_cc == 0.0
    assert wrapped.roi_cc == 0.0


# ---------------------------------------------------------------------------
# _marginal_cc_return
# ---------------------------------------------------------------------------


def test_marginal_cc_return_zero_for_no_uncaptured_value():
    """If actual_value >= potential_value, value_gap is 0 → marginal return is 0."""
    idea = _idea(potential_value=50, actual_value=50)
    assert _marginal_cc_return(idea) == 0.0


def test_marginal_cc_return_higher_with_higher_confidence():
    """Higher confidence weights the uncaptured value more (conf² in numerator)."""
    low_conf = _idea(potential_value=100, actual_value=0, confidence=0.2, estimated_cost=10, resistance_risk=0)
    high_conf = _idea(potential_value=100, actual_value=0, confidence=0.9, estimated_cost=10, resistance_risk=0)
    assert _marginal_cc_return(high_conf) > _marginal_cc_return(low_conf)


# ---------------------------------------------------------------------------
# _softmax_weights
# ---------------------------------------------------------------------------


def test_softmax_empty_returns_empty():
    """No scores → empty weights, no crash."""
    assert _softmax_weights([], temperature=1.0) == []


def test_softmax_deterministic_at_zero_temperature():
    """Temperature 0 → 1.0 on the max, 0.0 elsewhere (no exploration)."""
    weights = _softmax_weights([1.0, 3.0, 2.0], temperature=0.0)
    assert weights == [0.0, 1.0, 0.0]


def test_softmax_higher_score_gets_higher_weight():
    """At nonzero temperature, the highest-score slot gets the highest weight, and weights sum to 1."""
    weights = _softmax_weights([1.0, 3.0, 2.0], temperature=1.0)
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-9)
    assert weights[1] == max(weights)  # index of score 3.0


def test_softmax_higher_temperature_flattens_distribution():
    """A larger temperature pushes weights toward uniform (more exploration)."""
    cold = _softmax_weights([1.0, 5.0], temperature=0.5)
    hot = _softmax_weights([1.0, 5.0], temperature=10.0)
    # Cold: weights are skewed; hot: closer to 50/50.
    assert max(cold) > max(hot)
    assert abs(hot[0] - hot[1]) < abs(cold[0] - cold[1])
