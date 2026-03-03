"""Idea portfolio service: persistence, scoring, and prioritization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.idea import (
    Idea,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestion,
    IdeaSummary,
    IdeaStorageInfo,
    IdeaWithScore,
    ManifestationStatus,
)
from app.services import idea_registry_service
from app.services import commit_evidence_service


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
    {
        "id": "federated-instance-aggregation",
        "name": "Federated instance aggregation for contributor-owned deployments",
        "description": (
            "Allow contributors to run full or partial forks and publish verifiable telemetry back to the shared system. "
            "This increases contributor throughput without central infrastructure bottlenecks and raises collective value."
        ),
        "potential_value": 128.0,
        "actual_value": 0.0,
        "estimated_cost": 26.0,
        "actual_cost": 0.0,
        "resistance_risk": 5.0,
        "confidence": 0.72,
        "manifestation_status": "none",
        "interfaces": ["machine:api", "machine:federation", "human:web", "external:forks"],
        "open_questions": [
            {
                "question": "What is the minimal federation contract for cross-instance data aggregation with provenance?",
                "value_to_whole": 34.0,
                "estimated_cost": 6.0,
            },
            {
                "question": "Which anti-duplication and trust signals are required before federated data affects ROI ranking?",
                "value_to_whole": 31.0,
                "estimated_cost": 5.0,
            },
        ],
    },
]

STANDING_QUESTION_TEXT = (
    "How can we improve this idea, and if it cannot be measured yet how can it be measured, "
    "and if it is measured how can that measurement be improved?"
)

_TRACKED_IDEA_CACHE: dict[str, Any] = {"expires_at": 0.0, "idea_ids": [], "cache_key": ""}
_TRACKED_IDEA_CACHE_TTL_SECONDS = 300.0
REQUIRED_SYSTEM_IDEA_IDS: tuple[str, ...] = ("federated-instance-aggregation",)

DERIVED_IDEA_METADATA: dict[str, dict[str, Any]] = {
    "coherence-network-agent-pipeline": {
        "name": "Coherence network agent pipeline",
        "description": "Evolve autonomous task orchestration, validation gates, and failure recovery signals.",
        "interfaces": ["machine:api", "machine:automation", "human:operators"],
        "potential_value": 88.0,
        "estimated_cost": 16.0,
        "confidence": 0.65,
    },
    "coherence-network-api-runtime": {
        "name": "Coherence network API runtime parity",
        "description": "Ensure public API behavior, runtime telemetry, and deployment state stay in sync.",
        "interfaces": ["machine:api", "human:web", "external:railway"],
        "potential_value": 80.0,
        "estimated_cost": 14.0,
        "confidence": 0.62,
    },
    "coherence-network-value-attribution": {
        "name": "Coherence network value attribution",
        "description": "Track value lineage from idea to payout with measurable contribution attribution.",
        "interfaces": ["machine:api", "human:web", "human:contributors"],
        "potential_value": 92.0,
        "estimated_cost": 18.0,
        "confidence": 0.68,
    },
    "coherence-network-web-interface": {
        "name": "Coherence network web interface parity",
        "description": "Keep human-facing navigation and detail views aligned with machine-facing inventory.",
        "interfaces": ["human:web", "machine:api", "human:contributors"],
        "potential_value": 84.0,
        "estimated_cost": 13.0,
        "confidence": 0.64,
    },
    "deployment-gate-reliability": {
        "name": "Deployment gate reliability",
        "description": "Harden deploy and validation gates so failures are detected quickly and recovered automatically.",
        "interfaces": ["external:github", "external:railway"],
        "potential_value": 86.0,
        "estimated_cost": 15.0,
        "confidence": 0.63,
    },
}


def _default_portfolio_path() -> str:
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    return os.path.join(logs_dir, "idea_portfolio.json")


def _portfolio_path() -> str:
    return os.getenv("IDEA_PORTFOLIO_PATH", _default_portfolio_path())


def _idea_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("idea_ids")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value:
            out.append(value)
    return out


def _tracked_idea_ids_from_store(max_files: int = 400) -> list[str]:
    try:
        db_rows = commit_evidence_service.list_records(limit=max(1, max_files))
    except Exception:
        db_rows = []
    out: set[str] = set()
    for row in db_rows:
        if not isinstance(row, dict):
            continue
        out.update(_idea_ids_from_payload(row))
    return sorted(out)


def _should_include_default_tracked_ideas() -> bool:
    # When callers isolate ideas into a custom portfolio path (common in tests),
    # avoid implicitly pulling repo-global tracked ids unless explicitly requested.
    if os.getenv("IDEA_COMMIT_EVIDENCE_DIR") or os.getenv("COMMIT_EVIDENCE_DATABASE_URL"):
        return True
    return os.getenv("IDEA_PORTFOLIO_PATH") in {None, ""}


def _tracked_idea_ids() -> list[str]:
    if not _should_include_default_tracked_ideas():
        return []
    return _tracked_idea_ids_from_store()


def _humanize_idea_id(idea_id: str) -> str:
    words = [part for part in idea_id.replace("_", "-").split("-") if part]
    if not words:
        return "Derived tracked idea"
    return " ".join(words).strip().capitalize()


def _derived_idea_for_id(idea_id: str) -> Idea:
    metadata = DERIVED_IDEA_METADATA.get(idea_id, {})
    name = str(metadata.get("name") or _humanize_idea_id(idea_id))
    description = str(
        metadata.get("description")
        or f"Automatically derived from commit-evidence tracking for idea id '{idea_id}'."
    )
    interfaces = metadata.get("interfaces")
    if not isinstance(interfaces, list) or not all(isinstance(x, str) for x in interfaces):
        interfaces = ["machine:api", "human:web", "machine:commit-evidence"]
    potential_value = float(metadata.get("potential_value", 70.0))
    estimated_cost = float(metadata.get("estimated_cost", 12.0))
    confidence = float(metadata.get("confidence", 0.55))

    return Idea(
        id=idea_id,
        name=name,
        description=description,
        potential_value=potential_value,
        actual_value=0.0,
        estimated_cost=estimated_cost,
        actual_cost=0.0,
        resistance_risk=3.0,
        confidence=max(0.0, min(confidence, 1.0)),
        manifestation_status=ManifestationStatus.NONE,
        interfaces=interfaces,
        open_questions=[],
    )


def _default_idea_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in DEFAULT_IDEAS:
        raw_id = item.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            out[raw_id] = item
    return out


def _ensure_required_system_ideas(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    existing = {idea.id for idea in ideas}
    defaults_by_id = _default_idea_map()

    for required_id in REQUIRED_SYSTEM_IDEA_IDS:
        if required_id in existing:
            continue
        payload = defaults_by_id.get(required_id)
        if not isinstance(payload, dict):
            continue
        try:
            ideas.append(Idea(**payload))
        except Exception:
            continue
        existing.add(required_id)
        changed = True
    return ideas, changed


def _ensure_tracked_idea_entries(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    tracked_ids = _tracked_idea_ids()
    if not tracked_ids:
        return ideas, False
    existing = {idea.id for idea in ideas}
    changed = False
    for idea_id in tracked_ids:
        if idea_id in existing:
            continue
        ideas.append(_derived_idea_for_id(idea_id))
        existing.add(idea_id)
        changed = True
    return ideas, changed


def _write_snapshot_file(ideas: list[Idea]) -> None:
    storage = idea_registry_service.storage_info()
    if storage.get("backend") == "postgresql":
        purge_raw = str(os.getenv("TRACKING_PURGE_IMPORTED_FILES", "1")).strip().lower()
        if purge_raw not in {"0", "false", "no", "off"}:
            try:
                Path(_portfolio_path()).unlink(missing_ok=True)
            except OSError:
                pass
        return

    path = _portfolio_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ideas": [idea.model_dump(mode="json") for idea in ideas]}, f, indent=2)


def _read_legacy_file_ideas() -> tuple[list[Idea], str]:
    path = _portfolio_path()
    if not os.path.isfile(path):
        return [Idea(**item) for item in DEFAULT_IDEAS], "defaults"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [Idea(**item) for item in DEFAULT_IDEAS], "defaults"

    raw_ideas = data.get("ideas") if isinstance(data, dict) else None
    if not isinstance(raw_ideas, list):
        return [Idea(**item) for item in DEFAULT_IDEAS], "defaults"

    ideas: list[Idea] = []
    for item in raw_ideas:
        try:
            ideas.append(Idea(**item))
        except Exception:
            continue
    if not ideas:
        ideas = [Idea(**item) for item in DEFAULT_IDEAS]
        return ideas, "defaults"
    return ideas, "legacy_json"


def _read_ideas() -> list[Idea]:
    ideas = idea_registry_service.load_ideas()
    if not ideas:
        ideas, source = _read_legacy_file_ideas()
        ideas, required_changed = _ensure_required_system_ideas(ideas)
        ideas, tracked_changed = _ensure_tracked_idea_entries(ideas)
        ideas, standing_changed = _ensure_standing_questions(ideas)
        bootstrap_source = source
        if required_changed:
            bootstrap_source = f"{bootstrap_source}+required_system_ideas"
        if tracked_changed or source == "defaults":
            bootstrap_source = f"{bootstrap_source}+derived"
        if standing_changed:
            bootstrap_source = f"{bootstrap_source}+standing_question"
        idea_registry_service.save_ideas(ideas, bootstrap_source=bootstrap_source)
        _write_snapshot_file(ideas)
        return ideas

    ideas, required_changed = _ensure_required_system_ideas(ideas)
    ideas, tracked_changed = _ensure_tracked_idea_entries(ideas)
    ideas, standing_changed = _ensure_standing_questions(ideas)
    if required_changed or tracked_changed or standing_changed:
        _write_ideas(ideas)
    else:
        path = _portfolio_path()
        if not os.path.isfile(path):
            _write_snapshot_file(ideas)
    return ideas


def _write_ideas(ideas: list[Idea]) -> None:
    idea_registry_service.save_ideas(ideas)
    _write_snapshot_file(ideas)


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


def create_idea(
    idea_id: str,
    name: str,
    description: str,
    potential_value: float,
    estimated_cost: float,
    confidence: float = 0.5,
    interfaces: list[str] | None = None,
    open_questions: list[IdeaQuestionCreate] | None = None,
) -> IdeaWithScore | None:
    ideas = _read_ideas()
    if any(existing.id == idea_id for existing in ideas):
        return None

    idea = Idea(
        id=idea_id,
        name=name,
        description=description,
        potential_value=potential_value,
        actual_value=0.0,
        estimated_cost=estimated_cost,
        actual_cost=0.0,
        resistance_risk=1.0,
        confidence=max(0.0, min(confidence, 1.0)),
        manifestation_status=ManifestationStatus.NONE,
        interfaces=[x for x in (interfaces or []) if isinstance(x, str) and x.strip()],
        open_questions=[
            IdeaQuestion(
                question=item.question,
                value_to_whole=item.value_to_whole,
                estimated_cost=item.estimated_cost,
            )
            for item in (open_questions or [])
        ],
    )

    ideas.append(idea)
    ideas, _ = _ensure_standing_questions(ideas)
    _write_ideas(ideas)
    return _with_score(idea)


def add_question(
    idea_id: str,
    question: str,
    value_to_whole: float,
    estimated_cost: float,
) -> tuple[IdeaWithScore | None, bool]:
    ideas = _read_ideas()
    updated: Idea | None = None
    added = False
    normalized = question.strip().lower()

    for idx, idea in enumerate(ideas):
        if idea.id != idea_id:
            continue
        exists = any(q.question.strip().lower() == normalized for q in idea.open_questions)
        if not exists:
            idea.open_questions.append(
                IdeaQuestion(
                    question=question,
                    value_to_whole=value_to_whole,
                    estimated_cost=estimated_cost,
                )
            )
            added = True
        ideas[idx] = idea
        updated = idea
        break

    if updated is None:
        return None, False
    if not added:
        return _with_score(updated), False

    _write_ideas(ideas)
    return _with_score(updated), True


def update_idea(
    idea_id: str,
    actual_value: float | None = None,
    actual_cost: float | None = None,
    potential_value: float | None = None,
    estimated_cost: float | None = None,
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
        if potential_value is not None:
            idea.potential_value = potential_value
        if estimated_cost is not None:
            idea.estimated_cost = estimated_cost
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


def list_tracked_idea_ids() -> list[str]:
    """Expose tracked idea IDs (from commit evidence artifacts)."""
    return _tracked_idea_ids()


def storage_info() -> IdeaStorageInfo:
    """Expose idea registry storage backend and row counts for inspection."""
    info = idea_registry_service.storage_info()
    return IdeaStorageInfo(**info)
