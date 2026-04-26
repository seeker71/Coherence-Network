"""Governance health + showcase views for the idea portfolio.

Extracted from idea_service.py (#163). Read-only reporting functions
that snapshot the body's governance state and produce funder-facing
showcase output.

Public surface (re-exported from idea_service):
  compute_governance_health, list_showcase_ideas
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.idea import (
    GovernanceHealth,
    IdeaShowcaseBudget,
    IdeaShowcaseItem,
    IdeaShowcaseResponse,
    ManifestationStatus,
)
from app.services.idea_internal_filter import is_internal_idea_id
from app.services.idea_scoring import _with_score


def compute_governance_health(window_days: int = 30) -> GovernanceHealth:
    """Compute portfolio governance effectiveness metrics (spec 126).

    Returns a snapshot answering: "Is governance producing results,
    and where is it stuck?"
    """
    from app.services.idea_service import _read_ideas
    ideas = _read_ideas()
    total = len(ideas)
    scored = [_with_score(i) for i in ideas]

    validated = [i for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED]
    validated_count = len(validated)

    # R2: throughput_rate = validated in window / total
    throughput_rate = validated_count / total if total > 0 else 0.0

    # R3: value_gap_trend — without historical snapshots, report current total
    # value gap as the trend baseline (negative = would be improving if compared).
    # First implementation: report sum of current value gaps; trend is 0.0 (no prior snapshot).
    current_total_gap = sum(s.value_gap for s in scored)
    value_gap_trend = 0.0  # No historical data yet; will be non-zero once snapshots exist

    # R4: question_answer_rate
    total_questions = 0
    answered_questions = 0
    for idea in ideas:
        for q in idea.open_questions:
            total_questions += 1
            if q.answer is not None and q.answer.strip():
                answered_questions += 1
    question_answer_rate = answered_questions / total_questions if total_questions > 0 else 1.0

    # R5: stale_ideas — not validated and no updated_at tracking yet,
    # so use ideas that are not validated and have zero actual_value
    # (proxy for "no activity"). actual_cost has a 0.5 CC creation floor
    # so we only check actual_value for real progress.
    stale_ideas: list[str] = []
    for idea in ideas:
        if idea.manifestation_status == ManifestationStatus.VALIDATED:
            continue
        if idea.actual_value == 0.0:
            stale_ideas.append(idea.id)

    # R6: governance_score composite 0.0–1.0
    stale_ratio = len(stale_ideas) / total if total > 0 else 0.0
    governance_score = (
        throughput_rate * 0.3
        + question_answer_rate * 0.3
        + (1.0 - stale_ratio) * 0.4
    )
    governance_score = max(0.0, min(1.0, round(governance_score, 4)))

    # R7: snapshot_at
    snapshot_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return GovernanceHealth(
        governance_score=governance_score,
        throughput_rate=round(throughput_rate, 4),
        value_gap_trend=round(value_gap_trend, 4),
        question_answer_rate=round(question_answer_rate, 4),
        stale_ideas=stale_ideas,
        total_ideas=total,
        validated_ideas=validated_count,
        snapshot_at=snapshot_at,
        window_days=window_days,
    )


def list_showcase_ideas() -> IdeaShowcaseResponse:
    """Return funder-facing showcase ideas with proof and budget context."""
    from app.services.idea_service import _read_ideas
    ideas = _read_ideas(persist_ensures=False)
    visible = [
        idea
        for idea in ideas
        if idea.actual_value > 0.0 and not is_internal_idea_id(idea.id, idea.interfaces)
    ]
    ranked = sorted(visible, key=lambda row: row.actual_value, reverse=True)

    showcase_items: list[IdeaShowcaseItem] = []
    for idea in ranked:
        remaining_cost = max((idea.estimated_cost or 0.0) - (idea.actual_cost or 0.0), 0.0)
        value_gap = max((idea.potential_value or 0.0) - (idea.actual_value or 0.0), 0.0)
        ask = (
            f"Close {round(value_gap, 2)} CC of remaining value with "
            f"{round(remaining_cost, 2)} CC additional budget."
        )

        proof_notes = [
            str(question.answer).strip()
            for question in idea.open_questions
            if question.answer and str(question.answer).strip()
        ]
        if proof_notes:
            early_proof = proof_notes[0]
        else:
            early_proof = (
                f"Measured {round(idea.actual_value, 2)} CC realized so far "
                f"at {round(idea.actual_cost, 2)} CC spent."
            )

        showcase_items.append(
            IdeaShowcaseItem(
                idea_id=idea.id,
                title=idea.name,
                clear_ask=ask,
                budget=IdeaShowcaseBudget(
                    estimated_cost_cc=round(idea.estimated_cost, 4),
                    spent_cost_cc=round(idea.actual_cost, 4),
                    remaining_cost_cc=round(remaining_cost, 4),
                ),
                early_proof=early_proof,
                current_status=idea.manifestation_status,
            )
        )

    return IdeaShowcaseResponse(ideas=showcase_items)

