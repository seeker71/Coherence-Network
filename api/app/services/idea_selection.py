"""Stochastic idea selection — softmax-weighted random pick.

Extracted from idea_service.py (#163). The body picks one idea from
the portfolio by softmax sampling over a chosen score (free_energy or
marginal_cc), with temperature controlling exploration vs. exploitation.

Public surface (re-exported from idea_service):
  select_idea
"""

from __future__ import annotations

import random

from app.models.idea import IdeaSelectionResult, IdeaType
from app.services.idea_scoring import _softmax_weights, _with_score


def select_idea(
    method: str = "marginal_cc",
    temperature: float = 1.0,
    exclude_ids: list[str] | None = None,
    only_actionable: bool = True,
    seed: int | None = None,
) -> IdeaSelectionResult:
    """Weighted stochastic idea selection.

    Picks one idea from the portfolio using softmax-weighted random sampling.
    The distribution matches ranking on average but allows exploration:

    - temperature=0: always picks the top-ranked idea (pure exploit)
    - temperature=1: probability proportional to score (balanced)
    - temperature=2+: flatter distribution (more exploration)

    method: "free_energy" or "marginal_cc" — which score to use as the basis.
    exclude_ids: ideas to skip (e.g., recently worked on).
    only_actionable: if True, skip super-ideas (not directly workable).
    seed: optional RNG seed for reproducibility.
    """
    # Lazy import to break circular: idea_service imports this module
    from app.services.idea_service import _read_ideas

    ideas = _read_ideas(persist_ensures=False)

    if only_actionable:
        ideas = [i for i in ideas if i.idea_type != IdeaType.SUPER]
    if exclude_ids:
        excl = set(exclude_ids)
        ideas = [i for i in ideas if i.id not in excl]

    if not ideas:
        raise ValueError("No ideas available for selection after filtering")

    scored = [_with_score(i) for i in ideas]

    # Get the raw scores for the chosen method
    if method == "marginal_cc":
        raw_scores = [s.marginal_cc_score for s in scored]
    else:
        raw_scores = [s.free_energy_score for s in scored]

    # Compute softmax weights
    weights = _softmax_weights(raw_scores, temperature)

    # Attach weights to scored ideas
    for s, w in zip(scored, weights):
        s.selection_weight = round(w, 6)

    # Stochastic pick
    rng = random.Random(seed)
    cumulative = 0.0
    roll = rng.random()
    picked_idx = len(scored) - 1  # fallback to last
    for i, w in enumerate(weights):
        cumulative += w
        if roll <= cumulative:
            picked_idx = i
            break

    selected = scored[picked_idx]

    # Find runner-up (highest weight that isn't the picked one)
    runner_up = None
    sorted_by_weight = sorted(
        [(i, s) for i, s in enumerate(scored) if i != picked_idx],
        key=lambda x: x[1].selection_weight,
        reverse=True,
    )
    if sorted_by_weight:
        runner_up = sorted_by_weight[0][1]

    # Record for A/B tracking
    from app.services import idea_selection_ab_service
    top_picks = sorted(scored, key=lambda s: s.selection_weight, reverse=True)[:5]
    total_gap = sum(s.value_gap for s in scored)
    total_remaining = sum(
        max(s.estimated_cost - s.actual_cost, 0.0) for s in scored
    )
    idea_selection_ab_service.record_selection(
        method=method,
        top_picks=[
            {
                "idea_id": s.id,
                "score": s.marginal_cc_score if method == "marginal_cc" else s.free_energy_score,
                "value_gap": s.value_gap,
                "remaining_cost": max(s.estimated_cost - s.actual_cost, 0.0),
            }
            for s in top_picks
        ],
        total_remaining_cost_cc=total_remaining,
        total_value_gap_cc=total_gap,
        expected_roi=total_gap / total_remaining if total_remaining > 0 else 0,
    )

    return IdeaSelectionResult(
        selected=selected,
        method=method,
        temperature=temperature,
        selection_weight=selected.selection_weight,
        runner_up=runner_up,
        pool_size=len(scored),
    )
