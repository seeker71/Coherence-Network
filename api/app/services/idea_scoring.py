"""Idea scoring + cost/value vector decomposition.

Extracted from idea_service.py (#163). Pure functions over Idea models —
no DB, no cache, no I/O. Used internally by select_idea, list_ideas, and
the IdeaWithScore wrapper.

Public surface (imported back into idea_service for internal use):
  _score, _marginal_cc_return, _build_cost_vector, _build_value_vector,
  _with_score, _softmax_weights
"""

from __future__ import annotations

import math

from app.models.idea import CostVector, Idea, IdeaWithScore, ValueVector


def _score(idea: Idea) -> float:
    # Floor of 0.5 CC prevents astronomically inflated scores if both
    # estimated_cost and resistance_risk are near-zero.
    denom = max(idea.estimated_cost + idea.resistance_risk, 0.5)
    return (idea.potential_value * idea.confidence) / denom


def _marginal_cc_return(idea: Idea) -> float:
    """Method B: marginal CC return -- prioritizes uncaptured value per remaining CC."""
    pv = getattr(idea, 'potential_value', 0.0) or 0.0
    av = getattr(idea, 'actual_value', 0.0) or 0.0
    conf = getattr(idea, 'confidence', 0.5) or 0.5
    ec = getattr(idea, 'estimated_cost', 1.0) or 1.0
    ac = getattr(idea, 'actual_cost', 0.0) or 0.0
    rr = getattr(idea, 'resistance_risk', 1.0) or 1.0
    value_gap = max(pv - av, 0.0)
    remaining_cost = max(ec - ac, 0.1)
    return (value_gap * conf * conf) / (remaining_cost + rr * 0.5)


def _build_cost_vector(idea: Idea) -> CostVector:
    """Decompose estimated_cost into CC resource types."""
    ec = idea.estimated_cost or 0.0
    return CostVector(
        compute_cc=round(ec * 0.60, 4),
        infrastructure_cc=round(ec * 0.15, 4),
        human_attention_cc=round(ec * 0.25, 4),
        opportunity_cc=0.0,
        external_cc=0.0,
        total_cc=round(ec, 4),
    )


def _build_value_vector(idea: Idea) -> ValueVector:
    """Decompose potential_value into CC value types."""
    pv = idea.potential_value or 0.0
    return ValueVector(
        adoption_cc=round(pv * 0.50, 4),
        lineage_cc=round(pv * 0.30, 4),
        friction_avoided_cc=round(pv * 0.20, 4),
        revenue_cc=0.0,
        total_cc=round(pv, 4),
    )


def _with_score(idea: Idea) -> IdeaWithScore:
    value_gap = max(idea.potential_value - idea.actual_value, 0.0)
    remaining_cost_cc = round(max((idea.estimated_cost or 0.0) - (idea.actual_cost or 0.0), 0.0), 4)
    value_gap_cc = round(value_gap, 4)
    roi_cc = round(value_gap_cc / remaining_cost_cc, 4) if remaining_cost_cc > 0 else 0.0
    cost_vector = idea.cost_vector or _build_cost_vector(idea)
    value_vector = idea.value_vector or _build_value_vector(idea)
    data = idea.model_dump()
    data["cost_vector"] = cost_vector.model_dump()
    data["value_vector"] = value_vector.model_dump()
    return IdeaWithScore(
        **data,
        free_energy_score=round(_score(idea), 4),
        value_gap=round(value_gap, 4),
        marginal_cc_score=round(_marginal_cc_return(idea), 4),
        remaining_cost_cc=remaining_cost_cc,
        value_gap_cc=value_gap_cc,
        roi_cc=roi_cc,
    )


def _softmax_weights(scores: list[float], temperature: float) -> list[float]:
    """Convert raw scores to probability weights via softmax.

    temperature controls exploration:
      0.0  → deterministic (all weight on top score)
      1.0  → proportional to scores
      >1.0 → flatter distribution, more exploration
    """
    if not scores:
        return []
    if temperature <= 0.0:
        # Deterministic: all weight on the max
        max_s = max(scores)
        return [1.0 if s == max_s else 0.0 for s in scores]

    # Shift scores by max for numerical stability, scale by temperature
    max_s = max(scores)
    exps = [math.exp((s - max_s) / temperature) for s in scores]
    total = sum(exps)
    if total == 0:
        # Uniform fallback
        return [1.0 / len(scores)] * len(scores)
    return [e / total for e in exps]
