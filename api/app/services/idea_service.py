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
        "id": "coherence-network-overall",
        "name": "Coherence Network overall system",
        "description": "Top-level system idea connecting all component ideas into one measurable operating model.",
        "potential_value": 100.0,
        "actual_value": 14.0,
        "estimated_cost": 20.0,
        "actual_cost": 0.0,
        "resistance_risk": 3.0,
        "confidence": 0.78,
        "manifestation_status": "partial",
        "interfaces": ["machine:api", "human:web", "ai:automation"],
        "open_questions": [
            {
                "question": "What evidence proves the overall system is improving end-to-end value flow?",
                "value_to_whole": 32.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "coherence-network-api-runtime",
        "name": "System component: API and runtime telemetry",
        "description": "Machine interface for inventory, telemetry, and validation contracts.",
        "potential_value": 90.0,
        "actual_value": 13.0,
        "estimated_cost": 16.0,
        "actual_cost": 0.0,
        "resistance_risk": 3.0,
        "confidence": 0.76,
        "manifestation_status": "partial",
        "interfaces": ["machine:api"],
        "open_questions": [
            {
                "question": "Which runtime signals best predict value creation by component?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "coherence-network-web-interface",
        "name": "System component: human web interface",
        "description": "Human interface for idea browsing, manifestation status, and intervention.",
        "potential_value": 86.0,
        "actual_value": 11.0,
        "estimated_cost": 14.0,
        "actual_cost": 0.0,
        "resistance_risk": 4.0,
        "confidence": 0.74,
        "manifestation_status": "partial",
        "interfaces": ["human:web"],
        "open_questions": [
            {
                "question": "Can operators inspect and intervene across all ideas from web UI only?",
                "value_to_whole": 26.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "coherence-network-agent-pipeline",
        "name": "System component: agent task pipeline",
        "description": "Automated task orchestration, monitor issues, and intervention loops.",
        "potential_value": 88.0,
        "actual_value": 12.0,
        "estimated_cost": 15.0,
        "actual_cost": 0.0,
        "resistance_risk": 4.0,
        "confidence": 0.73,
        "manifestation_status": "partial",
        "interfaces": ["ai:automation", "machine:api", "human:operators"],
        "open_questions": [
            {
                "question": "Which automated checks reduce unresolved pipeline issues fastest?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "coherence-network-value-attribution",
        "name": "System component: value attribution and ROI",
        "description": "Track idea/spec/implementation/review contributions and value realization.",
        "potential_value": 92.0,
        "actual_value": 13.0,
        "estimated_cost": 16.0,
        "actual_cost": 0.0,
        "resistance_risk": 3.0,
        "confidence": 0.77,
        "manifestation_status": "partial",
        "interfaces": ["machine:api", "human:web"],
        "open_questions": [
            {
                "question": "Which attribution signals best predict realized ROI payout quality?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-contribution-matching",
        "name": "Living Codex contribution matching engine",
        "description": "Match contributor profiles to highest-value contribution opportunities.",
        "potential_value": 96.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 5.0,
        "confidence": 0.7,
        "manifestation_status": "none",
        "interfaces": ["human:web", "machine:api", "ai:automation"],
        "open_questions": [
            {
                "question": "Which matching signals most improve contribution throughput with least coordination cost?",
                "value_to_whole": 28.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-personalized-experience",
        "name": "Living Codex personalized experience engine",
        "description": "Generate personalized views from stable profile state plus session context.",
        "potential_value": 94.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 5.0,
        "confidence": 0.69,
        "manifestation_status": "none",
        "interfaces": ["human:web", "machine:api"],
        "open_questions": [
            {
                "question": "Which personalization features increase contributor retention without reducing transparency?",
                "value_to_whole": 27.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-autonomous-learning-loop",
        "name": "Living Codex autonomous learning loop",
        "description": "Continuously detect knowledge gaps, generate tasks, and learn from outcomes.",
        "potential_value": 92.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 6.0,
        "confidence": 0.68,
        "manifestation_status": "none",
        "interfaces": ["ai:automation", "machine:api"],
        "open_questions": [
            {
                "question": "What minimal autonomous learning loop produces measurable value within one week?",
                "value_to_whole": 26.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-water-state-storage",
        "name": "Living Codex water-state storage architecture",
        "description": "Implement ICE/WATER/VAPOR/PLASMA storage tiers with lifecycle transitions.",
        "potential_value": 90.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 6.0,
        "confidence": 0.67,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "ai:automation"],
        "open_questions": [
            {
                "question": "Which data classes should be mapped first to water states for maximum ROI?",
                "value_to_whole": 25.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-ice-bootstrap-core",
        "name": "Living Codex ICE bootstrap core",
        "description": "Package and boot a self-contained immutable core that reconstructs the system.",
        "potential_value": 88.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 7.0,
        "confidence": 0.66,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "ai:automation", "human:operators"],
        "open_questions": [
            {
                "question": "What is the minimum reproducible ICE bootstrap artifact for this system?",
                "value_to_whole": 25.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-real-time-plasma-streams",
        "name": "Living Codex plasma real-time collaboration streams",
        "description": "Add event-stream collaboration for real-time co-creation and feedback loops.",
        "potential_value": 86.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 7.0,
        "confidence": 0.65,
        "manifestation_status": "none",
        "interfaces": ["human:web", "machine:api"],
        "open_questions": [
            {
                "question": "Which collaboration events provide the strongest signal of shared value creation?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-quantum-ontology-nodes",
        "name": "Living Codex quantum-inspired ontology nodes",
        "description": "Model superposition, entanglement, and coherence factors in knowledge graph nodes.",
        "potential_value": 84.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 8.0,
        "confidence": 0.64,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "human:docs"],
        "open_questions": [
            {
                "question": "Which ontology fields produce practical decision value without over-complexity?",
                "value_to_whole": 23.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-knowledge-hologram-analysis",
        "name": "Living Codex knowledge hologram analysis",
        "description": "Measure wholeness, interconnectedness, redundancy, and resilience in the knowledge graph.",
        "potential_value": 82.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 8.0,
        "confidence": 0.63,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "human:web"],
        "open_questions": [
            {
                "question": "Which hologram metrics best predict downstream system robustness?",
                "value_to_whole": 22.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-user-profile-complexity",
        "name": "Living Codex user complexity profile model",
        "description": "Capture identity, communication, skills, interests, and local context for contributors.",
        "potential_value": 80.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 7.0,
        "confidence": 0.64,
        "manifestation_status": "none",
        "interfaces": ["human:web", "machine:api"],
        "open_questions": [
            {
                "question": "Which profile dimensions improve collaboration quality while respecting privacy?",
                "value_to_whole": 22.0,
                "estimated_cost": 2.0,
            }
        ],
    },
    {
        "id": "living-codex-self-bootstrap-validation",
        "name": "Living Codex self-bootstrap validation suite",
        "description": "Run full self-bootstrap and coherence validation as a repeatable system contract.",
        "potential_value": 78.0,
        "actual_value": 0.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 6.0,
        "confidence": 0.65,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "human:operators", "ai:automation"],
        "open_questions": [
            {
                "question": "Which bootstrap validation checks should block promotion to public deployment?",
                "value_to_whole": 21.0,
                "estimated_cost": 2.0,
            }
        ],
    },
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
    {
        "id": "web-ui-governance",
        "name": "Web UI contribution cockpit",
        "description": "Continuously improve the human interface to inspect and contribute through ROI-first workflows.",
        "potential_value": 76.0,
        "actual_value": 9.0,
        "estimated_cost": 12.0,
        "actual_cost": 0.0,
        "resistance_risk": 3.0,
        "confidence": 0.72,
        "manifestation_status": "partial",
        "interfaces": ["human:web", "machine:api"],
        "open_questions": [
            {
                "question": "How can we improve the UI?",
                "value_to_whole": 26.0,
                "estimated_cost": 2.0,
            },
            {
                "question": "What is missing from the UI for machine and human contributors?",
                "value_to_whole": 25.0,
                "estimated_cost": 2.0,
            },
            {
                "question": "Which UI element has the highest actual value and least cost?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            },
            {
                "question": "Which UI element has the highest cost and least value?",
                "value_to_whole": 24.0,
                "estimated_cost": 2.0,
            },
        ],
    },
]

STANDING_QUESTION_TEXT = (
    "How can we improve this idea, and if it cannot be measured yet how can it be measured, "
    "and if it is measured how can that measurement be improved?"
)

REQUIRED_CORE_IDEA_IDS: tuple[str, ...] = (
    "coherence-network-overall",
    "coherence-network-api-runtime",
    "coherence-network-web-interface",
    "coherence-network-agent-pipeline",
    "coherence-network-value-attribution",
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

    ideas, default_changed = _ensure_default_ideas(ideas)
    ideas, standing_changed = _ensure_standing_questions(ideas)
    ideas, dedupe_changed = _dedupe_open_questions(ideas)
    if default_changed or standing_changed or dedupe_changed:
        _write_ideas(ideas)
    return ideas


def _write_ideas(ideas: list[Idea]) -> None:
    path = _portfolio_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ideas": [idea.model_dump(mode="json") for idea in ideas]}, f, indent=2)


def _ensure_default_ideas(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    existing_ids = {idea.id for idea in ideas}
    for raw in DEFAULT_IDEAS:
        candidate_id = str(raw.get("id") or "").strip()
        if not candidate_id or candidate_id in existing_ids:
            continue
        ideas.append(Idea(**raw))
        existing_ids.add(candidate_id)
        changed = True
    return ideas, changed


def _normalize_question_key(question: str) -> str:
    return " ".join((question or "").strip().lower().split())


def _dedupe_open_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        if not idea.open_questions:
            continue
        seen: dict[str, IdeaQuestion] = {}
        ordered_keys: list[str] = []
        for q in idea.open_questions:
            key = _normalize_question_key(q.question)
            existing = seen.get(key)
            if existing is None:
                seen[key] = q
                ordered_keys.append(key)
                continue
            existing_answered = bool((existing.answer or "").strip())
            incoming_answered = bool((q.answer or "").strip())
            replace = False
            if incoming_answered and not existing_answered:
                replace = True
            elif incoming_answered == existing_answered:
                if float(q.value_to_whole) > float(existing.value_to_whole):
                    replace = True
                elif float(q.value_to_whole) == float(existing.value_to_whole):
                    if float(q.estimated_cost) < float(existing.estimated_cost):
                        replace = True
            if replace:
                if (
                    existing_answered
                    and incoming_answered
                    and existing.answer
                    and q.answer
                    and existing.answer != q.answer
                ):
                    q.answer = f"{existing.answer}\n---\n{q.answer}"
                if existing.measured_delta is not None and q.measured_delta is None:
                    q.measured_delta = existing.measured_delta
                seen[key] = q
            changed = True
        deduped = [seen[key] for key in ordered_keys]
        if len(deduped) != len(idea.open_questions):
            idea.open_questions = deduped
            changed = True
    return ideas, changed


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
