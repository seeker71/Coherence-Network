"""Idea portfolio service: persistence, scoring, and prioritization."""

from __future__ import annotations

import json
import os
from typing import Any

from app.models.idea import (
    Idea,
    IdeaPortfolioResponse,
    IdeaQuestion,
    IdeaSummary,
    IdeaWithScore,
    ManifestationStatus,
)


DEFAULT_IDEAS: list[dict[str, Any]] = [
    {
        "id": "oss-interface-alignment",
        "name": "Align OSS intelligence interfaces with runtime",
        "description": "Expose and validate declared API routes used by web and scripts.",
        "potential_value": 90.0,
        "actual_value": 10.0,
        "estimated_cost": 18.0,
        "actual_cost": 0.0,
        "resistance_risk": 4.0,
        "confidence": 0.7,
        "manifestation_status": "partial",
        "interfaces": ["machine:api", "human:web", "ai:automation"],
        "open_questions": [
            {
                "question": "Which route set is canonical for current milestone?",
                "value_to_whole": 30.0,
                "estimated_cost": 1.0,
            },
            {
                "question": "What is the minimum E2E flow to validate machine-human interface integrity?",
                "value_to_whole": 25.0,
                "estimated_cost": 2.0,
            },
        ],
    },
    {
        "id": "portfolio-governance",
        "name": "Unified idea portfolio governance",
        "description": "Track potential value, actual value, cost, and open questions for all ideas.",
        "potential_value": 82.0,
        "actual_value": 12.0,
        "estimated_cost": 10.0,
        "actual_cost": 0.0,
        "resistance_risk": 2.0,
        "confidence": 0.75,
        "manifestation_status": "partial",
        "interfaces": ["machine:api", "human:docs", "human:operators"],
        "open_questions": [
            {
                "question": "Which leading indicators best represent energy flow to the whole?",
                "value_to_whole": 28.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "coherence-signal-depth",
        "name": "Increase coherence signal depth with real data",
        "description": "Convert coherence components from stubs to measured signals.",
        "potential_value": 78.0,
        "actual_value": 8.0,
        "estimated_cost": 24.0,
        "actual_cost": 0.0,
        "resistance_risk": 8.0,
        "confidence": 0.55,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "human:web", "external:github"],
        "open_questions": [
            {
                "question": "What minimal GitHub ingestion yields measurable component uplift?",
                "value_to_whole": 20.0,
                "estimated_cost": 4.0,
            }
        ],
    },
]

STANDING_QUESTION_TEXT = (
    "How can we improve this idea, and if it cannot be measured yet how can it be measured, "
    "and if it is measured how can that measurement be improved?"
)


def _default_portfolio_path() -> str:
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    return os.path.join(logs_dir, "idea_portfolio.json")


def _portfolio_path() -> str:
    return os.getenv("IDEA_PORTFOLIO_PATH", _default_portfolio_path())


def _ensure_portfolio_file() -> None:
    path = _portfolio_path()
    if os.path.isfile(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ideas": DEFAULT_IDEAS}, f, indent=2)


def _read_ideas() -> list[Idea]:
    _ensure_portfolio_file()
    path = _portfolio_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [Idea(**item) for item in DEFAULT_IDEAS]

    raw_ideas = data.get("ideas") if isinstance(data, dict) else None
    if not isinstance(raw_ideas, list):
        return [Idea(**item) for item in DEFAULT_IDEAS]

    ideas: list[Idea] = []
    for item in raw_ideas:
        try:
            ideas.append(Idea(**item))
        except Exception:
            continue
    if not ideas:
        ideas = [Idea(**item) for item in DEFAULT_IDEAS]

    ideas, changed = _ensure_standing_questions(ideas)
    if changed:
        _write_ideas(ideas)
    return ideas


def _write_ideas(ideas: list[Idea]) -> None:
    path = _portfolio_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ideas": [idea.model_dump(mode="json") for idea in ideas]}, f, indent=2)


def _ensure_standing_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        has_standing = any(q.question == STANDING_QUESTION_TEXT for q in idea.open_questions)
        if has_standing:
            continue
        default_value = 24.0 if idea.manifestation_status != ManifestationStatus.NONE else 20.0
        default_cost = 2.0 if idea.manifestation_status != ManifestationStatus.NONE else 3.0
        idea.open_questions.append(
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=default_value,
                estimated_cost=default_cost,
            )
        )
        changed = True
    return ideas, changed


def _score(idea: Idea) -> float:
    denom = max(idea.estimated_cost + idea.resistance_risk, 0.0001)
    return (idea.potential_value * idea.confidence) / denom


def _with_score(idea: Idea) -> IdeaWithScore:
    value_gap = max(idea.potential_value - idea.actual_value, 0.0)
    return IdeaWithScore(**idea.model_dump(), free_energy_score=round(_score(idea), 4), value_gap=round(value_gap, 4))


def list_ideas(only_unvalidated: bool = False) -> IdeaPortfolioResponse:
    ideas = _read_ideas()
    if only_unvalidated:
        ideas = [i for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED]

    ranked = sorted((_with_score(i) for i in ideas), key=lambda i: i.free_energy_score, reverse=True)
    total_potential = sum(i.potential_value for i in ideas)
    total_actual = sum(i.actual_value for i in ideas)
    summary = IdeaSummary(
        total_ideas=len(ideas),
        unvalidated_ideas=sum(1 for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED),
        validated_ideas=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED),
        total_potential_value=round(total_potential, 4),
        total_actual_value=round(total_actual, 4),
        total_value_gap=round(max(total_potential - total_actual, 0.0), 4),
    )
    return IdeaPortfolioResponse(ideas=ranked, summary=summary)


def get_idea(idea_id: str) -> IdeaWithScore | None:
    for idea in _read_ideas():
        if idea.id == idea_id:
            return _with_score(idea)
    return None


def update_idea(
    idea_id: str,
    actual_value: float | None = None,
    actual_cost: float | None = None,
    confidence: float | None = None,
    manifestation_status: ManifestationStatus | None = None,
) -> IdeaWithScore | None:
    ideas = _read_ideas()
    updated: Idea | None = None

    for idx, idea in enumerate(ideas):
        if idea.id != idea_id:
            continue
        if actual_value is not None:
            idea.actual_value = actual_value
        if actual_cost is not None:
            idea.actual_cost = actual_cost
        if confidence is not None:
            idea.confidence = confidence
        if manifestation_status is not None:
            idea.manifestation_status = manifestation_status
        ideas[idx] = idea
        updated = idea
        break

    if updated is None:
        return None

    _write_ideas(ideas)
    return _with_score(updated)


def answer_question(
    idea_id: str,
    question: str,
    answer: str,
    measured_delta: float | None = None,
) -> tuple[IdeaWithScore | None, bool]:
    ideas = _read_ideas()
    updated: Idea | None = None
    question_found = False

    for idx, idea in enumerate(ideas):
        if idea.id != idea_id:
            continue
        for q in idea.open_questions:
            if q.question == question:
                q.answer = answer
                if measured_delta is not None:
                    q.measured_delta = measured_delta
                question_found = True
                break
        ideas[idx] = idea
        updated = idea
        break

    if updated is None:
        return None, False
    if not question_found:
        return _with_score(updated), False

    _write_ideas(ideas)
    return _with_score(updated), True
