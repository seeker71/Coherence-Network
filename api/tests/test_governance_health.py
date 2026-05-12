"""Tests for compute_governance_health (spec: portfolio-governance-effectiveness).

Function lives at api/app/services/idea_governance_views.py (extracted
from idea_service in #163, same shape as idea_scoring extraction). Reads
the ideas list via idea_service._read_ideas; tests monkeypatch that to
control input.

Covers the spec's named requirements:
  R2 throughput_rate = validated_count / total
  R4 question_answer_rate = answered_questions / total_questions
  R5 stale_ideas: not validated AND actual_value == 0
  R6 governance_score = 0.3×throughput + 0.3×Q&A + 0.4×(1 - stale_ratio)
  governance_score clamped to 0.0–1.0
  R7 snapshot_at + window_days returned
"""
from __future__ import annotations

from app.models.idea import IdeaQuestion, ManifestationStatus
from app.services import idea_service
from app.services.idea_governance_views import compute_governance_health


def _idea(
    *,
    id: str,
    potential_value: float = 100.0,
    actual_value: float = 0.0,
    estimated_cost: float = 10.0,
    actual_cost: float = 0.0,
    confidence: float = 0.5,
    resistance_risk: float = 1.0,
    status: ManifestationStatus = ManifestationStatus.NONE,
    open_questions: list[IdeaQuestion] | None = None,
):
    """Build a real Idea instance (not a mock) — the function calls _with_score on it."""
    from app.models.idea import Idea
    return Idea(
        id=id,
        name=id,
        description=id,
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        confidence=confidence,
        resistance_risk=resistance_risk,
        manifestation_status=status,
        open_questions=open_questions or [],
    )


def test_empty_portfolio_returns_zero_throughput_and_perfect_qa(monkeypatch):
    """Empty list → throughput_rate=0, Q&A rate defaults to 1.0 (no questions), no stale ideas."""
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: [])

    health = compute_governance_health(window_days=30)
    assert health.total_ideas == 0
    assert health.validated_ideas == 0
    assert health.throughput_rate == 0.0
    assert health.question_answer_rate == 1.0  # default when no questions
    assert health.stale_ideas == []
    assert health.window_days == 30


def test_throughput_rate_is_validated_over_total(monkeypatch):
    """R2: throughput_rate = validated_count / total."""
    ideas = [
        _idea(id=f"i-{i}", actual_value=50, status=ManifestationStatus.VALIDATED) for i in range(3)
    ] + [_idea(id=f"j-{i}", actual_value=50) for i in range(2)]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)

    health = compute_governance_health()
    assert health.total_ideas == 5
    assert health.validated_ideas == 3
    assert health.throughput_rate == round(3 / 5, 4)


def test_question_answer_rate_counts_answered_only(monkeypatch):
    """R4: rate = answered (non-null, non-empty) / total."""
    ideas = [
        _idea(
            id="i-1",
            actual_value=50,
            open_questions=[
                IdeaQuestion(question="q1", value_to_whole=1.0, estimated_cost=1.0, answer="yes"),
                IdeaQuestion(question="q2", value_to_whole=1.0, estimated_cost=1.0, answer=""),  # empty → unanswered
                IdeaQuestion(question="q3", value_to_whole=1.0, estimated_cost=1.0, answer=None),
                IdeaQuestion(question="q4", value_to_whole=1.0, estimated_cost=1.0, answer="a real answer"),
            ],
        )
    ]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)

    health = compute_governance_health()
    # 2 of 4 answered → 0.5
    assert health.question_answer_rate == 0.5


def test_stale_ideas_are_unvalidated_with_zero_actual_value(monkeypatch):
    """R5: stale = not validated AND actual_value == 0."""
    ideas = [
        _idea(id="stale-1", actual_value=0.0),
        _idea(id="active-1", actual_value=10.0),
        _idea(id="validated-1", actual_value=0.0, status=ManifestationStatus.VALIDATED),
    ]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)

    health = compute_governance_health()
    assert health.stale_ideas == ["stale-1"]


def test_governance_score_composite_formula(monkeypatch):
    """R6: score = 0.3×throughput + 0.3×Q&A + 0.4×(1 - stale_ratio)."""
    # 2 ideas total, 1 validated → throughput=0.5
    # 1 unvalidated with actual_value=0 → stale_ratio=0.5
    # 1 question, answered → Q&A=1.0
    ideas = [
        _idea(
            id="v-1",
            actual_value=10.0,
            status=ManifestationStatus.VALIDATED,
            open_questions=[IdeaQuestion(question="q", value_to_whole=1.0, estimated_cost=1.0, answer="yes")],
        ),
        _idea(id="stale-1", actual_value=0.0),
    ]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)

    health = compute_governance_health()
    # 0.3*0.5 + 0.3*1.0 + 0.4*(1 - 0.5) = 0.15 + 0.30 + 0.20 = 0.65
    assert health.governance_score == 0.65


def test_governance_score_clamped_to_unit_interval(monkeypatch):
    """Score is always between 0.0 and 1.0 inclusive, regardless of inputs."""
    # Best case: all validated, all questions answered, no stale
    ideas = [
        _idea(
            id=f"i-{i}",
            actual_value=10.0,
            status=ManifestationStatus.VALIDATED,
            open_questions=[IdeaQuestion(question="q", value_to_whole=1.0, estimated_cost=1.0, answer="yes")],
        )
        for i in range(3)
    ]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)
    high = compute_governance_health()
    assert 0.0 <= high.governance_score <= 1.0
    assert high.governance_score == 1.0  # all signals at maximum

    # Worst case: nothing validated, all stale, no answered questions
    ideas = [_idea(id=f"i-{i}", actual_value=0.0) for i in range(3)]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)
    low = compute_governance_health()
    assert 0.0 <= low.governance_score <= 1.0
    # throughput=0, Q&A defaults to 1.0 (no questions), stale_ratio=1.0
    # score = 0 + 0.3 + 0 = 0.30
    assert low.governance_score == 0.30


def test_snapshot_at_and_window_days_are_returned(monkeypatch):
    """R7: snapshot_at is an ISO UTC timestamp; window_days reflects the call parameter."""
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: [])

    health = compute_governance_health(window_days=7)
    assert health.window_days == 7
    # ISO 8601 UTC: "YYYY-MM-DDTHH:MM:SSZ"
    assert health.snapshot_at.endswith("Z")
    assert "T" in health.snapshot_at
    assert len(health.snapshot_at) == 20  # exact ISO 8601 Z format


def test_validated_ideas_count_matches_status(monkeypatch):
    """validated_ideas counts ideas with manifestation_status=VALIDATED."""
    ideas = [
        _idea(id="v-1", actual_value=10.0, status=ManifestationStatus.VALIDATED),
        _idea(id="v-2", actual_value=10.0, status=ManifestationStatus.VALIDATED),
        _idea(id="p-1", actual_value=10.0, status=ManifestationStatus.PARTIAL),
        _idea(id="n-1", actual_value=10.0, status=ManifestationStatus.NONE),
    ]
    monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: ideas)

    health = compute_governance_health()
    assert health.total_ideas == 4
    assert health.validated_ideas == 2
