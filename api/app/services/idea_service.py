"""Idea portfolio service: pure DB reader with runtime discovery.

The DB (data/coherence.db) is the single source of truth for ideas.
Seed data is loaded via `scripts/seed_db.py`, not at runtime.
This module reads from DB, discovers new ideas from runtime evidence,
and writes back only genuinely new discoveries.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import threading
import time
from typing import Any

from sqlalchemy import text

from app.models.coherence_credit import CostVector, ValueVector
from app.models.idea import (
    IDEA_STAGE_ORDER,
    GovernanceHealth,
    Idea,
    IdeaCountByStatus,
    IdeaCountResponse,
    IdeaShowcaseBudget,
    IdeaShowcaseItem,
    IdeaShowcaseResponse,
    IdeaSelectionResult,
    IdeaStage,
    IdeaType,
    PaginationInfo,
    ProgressDashboard,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestion,
    IdeaSummary,
    IdeaStorageInfo,
    IdeaWithScore,
    ManifestationStatus,
    StageBucket,
)
from app.services import idea_registry_service
from app.services import commit_evidence_service
from app.services import runtime_service
from app.services import spec_registry_service
from app.services import value_lineage_service


# Known internal idea IDs — these were previously loaded from derived_metadata
# in seed_ideas.json and are used for internal-idea classification only.
# The DB is the sole source of truth for idea data; this set is only for
# the is_internal_idea_id() classification heuristic.
_KNOWN_INTERNAL_IDEA_IDS: set[str] = {
    "coherence-network-agent-pipeline",
    "coherence-network-api-runtime",
    "coherence-network-value-attribution",
    "coherence-network-web-interface",
    "deployment-gate-reliability",
    "interface-trust-surface",
    "minimum-e2e-path",
    "funder-proof-page",
    "idea-hierarchy-model",
    "unified-sqlite-store",
    "agent-prompt-ab-roi",
    "agent-failed-task-diagnostics",
    "agent-auto-heal",
    "agent-grounded-measurement",
}

STANDING_QUESTION_TEXT = (
    "How can we improve this idea, show whether it is working yet, "
    "and make that proof clearer over time?"
)

_CACHE_LOCK = threading.Lock()
_TRACKED_IDEA_CACHE: dict[str, Any] = {"expires_at": 0.0, "idea_ids": [], "cache_key": ""}
_TRACKED_IDEA_CACHE_TTL_SECONDS = 300.0
_IDEAS_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": []}
_IDEAS_CACHE_TTL_SECONDS = 180.0

DEFAULT_INTERNAL_IDEA_PREFIXES = (
    "spec-origin-",
    "endpoint-lineage-",
    "public-e2e-",
    "e2e-idea-",
)
DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS = {"machine:commit-evidence"}
TRANSIENT_INTERNAL_ID_PATTERNS = (
    re.compile(r"^public-e2e-[0-9a-f]{8}$"),
)
DISCOVERED_INTERNAL_ID_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^public-e2e-[0-9a-f]{8}$"), "deployment-gate-reliability"),
    (re.compile(r"^e2e-idea-[0-9a-f]{8}$"), "deployment-gate-reliability"),
    (re.compile(r"^spec-origin-"), "portfolio-governance"),
    (re.compile(r"^endpoint-lineage-"), "oss-interface-alignment"),
)


def _configured_internal_idea_prefixes() -> set[str]:
    raw = str(os.getenv("INTERNAL_IDEA_ID_PREFIXES", "")).strip()
    if not raw:
        return set(DEFAULT_INTERNAL_IDEA_PREFIXES)
    out = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return out or set(DEFAULT_INTERNAL_IDEA_PREFIXES)


def _configured_internal_idea_exact_ids() -> set[str]:
    out = set(_KNOWN_INTERNAL_IDEA_IDS)
    raw = str(os.getenv("INTERNAL_IDEA_ID_EXACT", "")).strip()
    if raw:
        out.update(item.strip().lower() for item in raw.split(",") if item.strip())
    return out


def _configured_internal_idea_interface_tags() -> set[str]:
    raw = str(os.getenv("INTERNAL_IDEA_INTERFACE_TAGS", "")).strip()
    if not raw:
        return set(DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS)
    out = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return out or set(DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS)


def is_internal_idea_id(idea_id: str, interfaces: list[str] | None = None) -> bool:
    normalized_id = str(idea_id or "").strip().lower()
    if not normalized_id:
        return False
    if normalized_id in _configured_internal_idea_exact_ids():
        return True
    for prefix in _configured_internal_idea_prefixes():
        if normalized_id.startswith(prefix):
            return True
    if isinstance(interfaces, list):
        tags = {str(item).strip().lower() for item in interfaces if str(item).strip()}
        if tags.intersection(_configured_internal_idea_interface_tags()):
            return True
    return False


def _is_transient_internal_idea_id(idea_id: str) -> bool:
    normalized_id = str(idea_id or "").strip().lower()
    if not normalized_id:
        return False
    return any(pattern.match(normalized_id) for pattern in TRANSIENT_INTERNAL_ID_PATTERNS)


def _canonical_discovered_idea_id(idea_id: str) -> str | None:
    normalized_id = str(idea_id or "").strip().lower()
    if not normalized_id or normalized_id == "unmapped":
        return None
    for pattern, target_id in DISCOVERED_INTERNAL_ID_ALIASES:
        if pattern.match(normalized_id):
            return target_id
    if _is_transient_internal_idea_id(normalized_id):
        return None
    return normalized_id


def canonical_discovered_idea_id(idea_id: str) -> str | None:
    return _canonical_discovered_idea_id(idea_id)


def _should_track_discovered_idea_id(idea_id: str) -> bool:
    return _canonical_discovered_idea_id(idea_id) is not None


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
    # With unified_db (spec 118), all services share one DB, so tracked
    # ideas from commit evidence are always in the same store as ideas.
    return True


def _invalidate_ideas_cache() -> None:
    with _CACHE_LOCK:
        _IDEAS_CACHE["expires_at"] = 0.0
        _IDEAS_CACHE["items"] = []
        _IDEAS_CACHE["cache_key"] = ""


def _cache_ideas(ideas: list[Idea]) -> None:
    with _CACHE_LOCK:
        _IDEAS_CACHE["items"] = [idea.model_copy(deep=True) for idea in ideas]
        _IDEAS_CACHE["expires_at"] = time.time() + _IDEAS_CACHE_TTL_SECONDS
        _IDEAS_CACHE["cache_key"] = _ideas_cache_key()


def _ideas_cache_key() -> str:
    from app.services import unified_db as _udb
    return (
        f"{_udb.database_url()}|"
        f"{os.getenv('IDEA_SYNC_RUNTIME_WINDOW_SECONDS','')}|"
        f"{os.getenv('IDEA_SYNC_RUNTIME_EVENT_LIMIT','')}|"
        f"{os.getenv('IDEA_SYNC_CONTRIBUTION_LIMIT','')}"
    )


def _read_ideas_cache() -> list[Idea] | None:
    with _CACHE_LOCK:
        cache_key = _ideas_cache_key()
        if (
            _IDEAS_CACHE.get("cache_key") != cache_key
            or _IDEAS_CACHE.get("expires_at", 0.0) <= time.time()
        ):
            return None
        cached = _IDEAS_CACHE.get("items")
        if not isinstance(cached, list):
            return None
        return [idea.model_copy(deep=True) for idea in cached]


def _tracked_idea_ids() -> list[str]:
    if not _should_include_default_tracked_ideas():
        return []
    now = time.time()
    from app.services import unified_db as _udb
    cache_key = _udb.database_url()
    with _CACHE_LOCK:
        if (
            _TRACKED_IDEA_CACHE.get("cache_key") == cache_key
            and _TRACKED_IDEA_CACHE.get("expires_at", 0.0) > now
        ):
            return list(_TRACKED_IDEA_CACHE.get("idea_ids", []))
    idea_ids = _tracked_idea_ids_from_store()

    with _CACHE_LOCK:
        _TRACKED_IDEA_CACHE["cache_key"] = cache_key
        _TRACKED_IDEA_CACHE["idea_ids"] = idea_ids
        _TRACKED_IDEA_CACHE["expires_at"] = now + _TRACKED_IDEA_CACHE_TTL_SECONDS
    return idea_ids


def _should_discover_registry_domain_ideas() -> bool:
    if not _should_include_default_tracked_ideas():
        return False
    explicit = str(os.getenv("IDEA_SYNC_ENABLE_DOMAIN_DISCOVERY", "")).strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    # Keep isolated pytest runs deterministic unless explicitly enabled.
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    # In runtime/deploy environments, always discover registry-domain ideas.
    return True


def _discover_registry_domain_idea_ids() -> list[str]:
    if not _should_discover_registry_domain_ideas():
        return []

    discovered: set[str] = {
        idea_id
        for idea_id in _tracked_idea_ids()
        if _should_track_discovered_idea_id(idea_id)
    }

    try:
        spec_rows = spec_registry_service.list_specs(limit=2000, offset=0)
    except Exception:
        spec_rows = []
    for row in spec_rows:
        idea_id = str(getattr(row, "idea_id", "") or "").strip()
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)

    try:
        lineage_rows = value_lineage_service.list_links(limit=2000)
    except Exception:
        lineage_rows = []
    for row in lineage_rows:
        idea_id = str(getattr(row, "idea_id", "") or "").strip()
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)

    try:
        runtime_window_raw = int(str(os.getenv("IDEA_SYNC_RUNTIME_WINDOW_SECONDS", "86400")).strip() or "86400")
    except ValueError:
        runtime_window_raw = 86400
    runtime_window_seconds = max(60, min(runtime_window_raw, 60 * 60 * 24 * 30))

    try:
        runtime_limit_raw = int(str(os.getenv("IDEA_SYNC_RUNTIME_EVENT_LIMIT", "2000")).strip() or "2000")
    except ValueError:
        runtime_limit_raw = 2000
    runtime_event_limit = max(1, min(runtime_limit_raw, 5000))
    try:
        runtime_rows = runtime_service.summarize_by_idea(
            seconds=runtime_window_seconds,
            event_limit=runtime_event_limit,
            summary_limit=2000,
            summary_offset=0,
        )
    except Exception:
        runtime_rows = []
    for row in runtime_rows:
        idea_id = str(getattr(row, "idea_id", "") or "").strip()
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)
    for idea_id in _contribution_metadata_idea_ids():
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)

    return sorted(discovered)


def _contribution_metadata_idea_ids() -> list[str]:
    from app.services import unified_db as _udb

    try:
        contribution_limit_raw = int(str(os.getenv("IDEA_SYNC_CONTRIBUTION_LIMIT", "3000")).strip() or "3000")
    except ValueError:
        contribution_limit_raw = 3000
    contribution_limit = max(1, min(contribution_limit_raw, 20000))

    rows: list[Any] = []
    try:
        with _udb.session() as session:
            rows = list(
                session.execute(
                    text("SELECT meta FROM contributions ORDER BY timestamp DESC LIMIT :limit"),
                    {"limit": contribution_limit},
                )
            )
    except Exception:
        return []

    discovered: set[str] = set()
    for row in rows:
        metadata: Any = None
        try:
            metadata = row[0] if isinstance(row, tuple) else row.meta  # type: ignore[attr-defined]
        except Exception:
            try:
                metadata = row[0]
            except Exception:
                metadata = None
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except ValueError:
                metadata = None
        if not isinstance(metadata, dict):
            continue
        raw_single = metadata.get("idea_id")
        if isinstance(raw_single, str) and raw_single.strip():
            discovered.add(raw_single.strip())
        raw_multi = metadata.get("idea_ids")
        if isinstance(raw_multi, list):
            for item in raw_multi:
                if isinstance(item, str) and item.strip():
                    discovered.add(item.strip())
    return sorted(discovered)


def _ensure_registry_domain_idea_entries(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    discovered_ids = _discover_registry_domain_idea_ids()
    if not discovered_ids:
        return ideas, False
    existing = {idea.id for idea in ideas}
    changed = False
    for idea_id in discovered_ids:
        if not _should_track_discovered_idea_id(idea_id):
            continue
        if idea_id in existing:
            continue
        ideas.append(_derived_idea_for_id(idea_id))
        existing.add(idea_id)
        changed = True
    return ideas, changed


def _prune_transient_internal_ideas(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    kept: list[Idea] = []
    changed = False
    for idea in ideas:
        canonical_id = _canonical_discovered_idea_id(idea.id)
        if canonical_id is not None and canonical_id != str(idea.id).strip().lower():
            changed = True
            continue
        if _is_transient_internal_idea_id(idea.id):
            changed = True
            continue
        kept.append(idea)
    return kept, changed


def _humanize_idea_id(idea_id: str) -> str:
    words = [part for part in idea_id.replace("_", "-").split("-") if part]
    if not words:
        return "Derived tracked idea"
    return " ".join(words).strip().capitalize()


def _derived_idea_for_id(idea_id: str) -> Idea:
    # Try to find metadata from DB for discovered ideas
    metadata: dict[str, Any] = {}
    try:
        db_ideas = idea_registry_service.load_ideas()
        for idea in db_ideas:
            if idea.id == idea_id:
                metadata = {
                    "name": idea.name,
                    "description": idea.description,
                    "interfaces": idea.interfaces,
                    "potential_value": idea.potential_value,
                    "actual_value": idea.actual_value,
                    "estimated_cost": idea.estimated_cost,
                    "actual_cost": idea.actual_cost,
                    "confidence": idea.confidence,
                    "resistance_risk": idea.resistance_risk,
                    "idea_type": idea.idea_type.value if idea.idea_type else "standalone",
                    "parent_idea_id": idea.parent_idea_id,
                    "child_idea_ids": idea.child_idea_ids or [],
                    "manifestation_status": idea.manifestation_status.value if idea.manifestation_status else "none",
                }
                break
    except Exception:
        pass
    name = str(metadata.get("name") or _humanize_idea_id(idea_id))
    description = str(
        metadata.get("description")
        or f"Automatically derived from commit-evidence tracking for idea id '{idea_id}'."
    )
    interfaces = metadata.get("interfaces")
    if not isinstance(interfaces, list) or not all(isinstance(x, str) for x in interfaces):
        interfaces = ["machine:api", "human:web", "machine:commit-evidence"]

    # Copy all numeric and enum fields from seed, with safe defaults
    potential_value = float(metadata.get("potential_value", 70.0))
    actual_value = float(metadata.get("actual_value", 0.0))
    estimated_cost = float(metadata.get("estimated_cost", 12.0))
    actual_cost = float(metadata.get("actual_cost", 0.0))
    confidence = float(metadata.get("confidence", 0.55))
    resistance_risk = float(metadata.get("resistance_risk", 3.0))

    # Hierarchy fields
    idea_type_str = metadata.get("idea_type", "standalone")
    try:
        idea_type = IdeaType(idea_type_str)
    except ValueError:
        idea_type = IdeaType.STANDALONE
    parent_idea_id = metadata.get("parent_idea_id")
    child_idea_ids = metadata.get("child_idea_ids", [])
    if not isinstance(child_idea_ids, list):
        child_idea_ids = []

    # Status
    status_str = metadata.get("manifestation_status", "none")
    try:
        status = ManifestationStatus(status_str)
    except ValueError:
        status = ManifestationStatus.NONE

    return Idea(
        id=idea_id,
        name=name,
        description=description,
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        resistance_risk=resistance_risk,
        confidence=max(0.0, min(confidence, 1.0)),
        manifestation_status=status,
        interfaces=interfaces,
        open_questions=[],
        idea_type=idea_type,
        parent_idea_id=parent_idea_id,
        child_idea_ids=child_idea_ids,
    )


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


def _read_ideas(*, persist_ensures: bool = False) -> list[Idea]:
    """Load ideas from DB, discover new ones from runtime, cache.

    When persist_ensures=False (e.g. guard/invariant runs), no writes are made.
    """
    cached = _read_ideas_cache()
    if cached is not None:
        return cached

    ideas = idea_registry_service.load_ideas()

    # Runtime discovery: find idea IDs referenced in evidence/specs/lineage
    ideas, tracked_changed = _ensure_tracked_idea_entries(ideas)
    ideas, domain_changed = _ensure_registry_domain_idea_entries(ideas)
    ideas, transient_pruned = _prune_transient_internal_ideas(ideas)
    ideas, pruned_standing = _prune_internal_standing_questions(ideas)
    ideas, standing_changed = _ensure_standing_questions(ideas)

    if persist_ensures and (tracked_changed or domain_changed or transient_pruned or pruned_standing or standing_changed):
        _write_ideas(ideas)

    _cache_ideas(ideas)
    return ideas


def _write_ideas(ideas: list[Idea]) -> None:
    idea_registry_service.save_ideas(ideas)
    _cache_ideas(ideas)


def _write_single_idea(idea: Idea, position: int) -> None:
    """Persist a single idea via upsert instead of rewriting the full list."""
    idea_registry_service.save_single_idea(idea, position=position)
    _invalidate_ideas_cache()


def _ensure_standing_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        if is_internal_idea_id(idea.id, idea.interfaces):
            continue
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


def _prune_internal_standing_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        if not is_internal_idea_id(idea.id, idea.interfaces):
            continue
        before = len(idea.open_questions)
        if before == 0:
            continue
        idea.open_questions = [q for q in idea.open_questions if q.question != STANDING_QUESTION_TEXT]
        if len(idea.open_questions) != before:
            changed = True
    return ideas, changed


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


def list_ideas(
    only_unvalidated: bool = False,
    limit: int | None = None,
    offset: int = 0,
    include_internal: bool = True,
    read_only_guard: bool = False,
    sort_method: str = "free_energy",
) -> IdeaPortfolioResponse:
    """When read_only_guard=True, ensure logic is applied in memory but not persisted (for invariant/guard runs).

    sort_method: "free_energy" (default, Method A) or "marginal_cc" (Method B).
    """
    ideas = _read_ideas(persist_ensures=not read_only_guard)
    if not include_internal:
        ideas = [i for i in ideas if not is_internal_idea_id(i.id, i.interfaces)]
    if only_unvalidated:
        ideas = [i for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED]

    scored = [_with_score(i) for i in ideas]
    if sort_method == "marginal_cc":
        sort_key = lambda i: i.marginal_cc_score
        raw_scores = [s.marginal_cc_score for s in scored]
    else:
        sort_key = lambda i: i.free_energy_score
        raw_scores = [s.free_energy_score for s in scored]

    # Compute selection weights (temperature=1.0) so list consumers can see
    # the probability each idea would have in a stochastic pick
    weights = _softmax_weights(raw_scores, temperature=1.0)
    for s, w in zip(scored, weights):
        s.selection_weight = round(w, 6)

    ranked = sorted(scored, key=sort_key, reverse=True)
    total_ranked = len(ranked)
    safe_offset = max(0, int(offset))
    safe_limit = None if limit is None else max(1, min(int(limit), 500))
    if safe_limit is None:
        page_items = ranked[safe_offset:]
    else:
        page_items = ranked[safe_offset:safe_offset + safe_limit]
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
    pagination = PaginationInfo(
        total=total_ranked,
        limit=safe_limit or max(total_ranked, 1),
        offset=safe_offset,
        returned=len(page_items),
        has_more=(safe_offset + len(page_items)) < total_ranked,
    )
    return IdeaPortfolioResponse(ideas=page_items, summary=summary, pagination=pagination)


def get_idea(idea_id: str) -> IdeaWithScore | None:
    for idea in _read_ideas():
        if idea.id == idea_id:
            return _with_score(idea)
    # Some runtime/inventory idea ids are derived and may not be persisted in the
    # portfolio store yet. Expose them so UI links remain walkable.
    if idea_id in _KNOWN_INTERNAL_IDEA_IDS:
        return _with_score(_derived_idea_for_id(idea_id))
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
    *,
    actual_value: float | None = None,
    actual_cost: float | None = None,
    resistance_risk: float | None = None,
    idea_type: IdeaType | None = None,
    parent_idea_id: str | None = None,
    child_idea_ids: list[str] | None = None,
    manifestation_status: ManifestationStatus | None = None,
    value_basis: dict[str, str] | None = None,
) -> IdeaWithScore | None:
    ideas = _read_ideas(persist_ensures=True)
    if any(existing.id == idea_id for existing in ideas):
        return None

    idea = Idea(
        id=idea_id,
        name=name,
        description=description,
        potential_value=potential_value,
        actual_value=actual_value if actual_value is not None else 0.0,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost if actual_cost is not None else 0.5,   # Design/description cost floor (0.5 CC)
        resistance_risk=resistance_risk if resistance_risk is not None else 2.5,  # Unknown ideas assume moderate risk
        confidence=max(0.0, min(confidence, 1.0)),
        manifestation_status=manifestation_status or ManifestationStatus.NONE,
        idea_type=idea_type or IdeaType.STANDALONE,
        parent_idea_id=parent_idea_id,
        child_idea_ids=child_idea_ids or [],
        value_basis=value_basis,
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
    ideas = _read_ideas(persist_ensures=True)
    updated: Idea | None = None
    updated_idx: int = -1
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
        updated_idx = idx
        break

    if updated is None:
        return None, False
    if not added:
        return _with_score(updated), False

    _write_single_idea(updated, position=updated_idx)
    return _with_score(updated), True


def update_idea(
    idea_id: str,
    actual_value: float | None = None,
    actual_cost: float | None = None,
    confidence: float | None = None,
    manifestation_status: ManifestationStatus | None = None,
    potential_value: float | None = None,
    estimated_cost: float | None = None,
) -> IdeaWithScore | None:
    """Update an idea.

    Public API patch contract remains limited to actual_value/actual_cost/confidence/
    manifestation_status. Internal services may also adjust potential_value and
    estimated_cost for ROI normalization/calibration flows.
    """
    ideas = _read_ideas(persist_ensures=True)
    updated: Idea | None = None
    updated_idx: int = -1

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
        if potential_value is not None:
            idea.potential_value = max(0.0, float(potential_value))
        if estimated_cost is not None:
            idea.estimated_cost = max(0.0, float(estimated_cost))
        ideas[idx] = idea
        updated = idea
        updated_idx = idx
        break

    if updated is None:
        return None

    _write_single_idea(updated, position=updated_idx)
    return _with_score(updated)


def stake_on_idea(idea_id: str, contributor_id: str, amount_cc: float, rationale: str | None = None) -> dict:
    """Stake CC on an idea — records contribution, increases potential_value, adds lineage investment."""
    from app.models.value_lineage import LineageLinkCreate, LineageContributors, LineageInvestment
    from app.services import contribution_ledger_service

    # 1. Verify idea exists
    idea = get_idea(idea_id)
    if idea is None:
        raise ValueError(f"Idea not found: {idea_id}")

    # 2. Record contribution via ledger
    stake_meta = {"rationale": rationale} if rationale else {}
    stake_record = contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="stake",
        amount_cc=amount_cc,
        idea_id=idea_id,
        metadata=stake_meta,
    )

    # 3. Increase the idea's potential_value by amount_cc * 0.5
    new_potential = (idea.potential_value or 0.0) + (amount_cc * 0.5)
    updated_idea = update_idea(idea_id, potential_value=new_potential)

    # 4. Add a value lineage investment with role="staker"
    #    Find existing lineage link for this idea, or create one
    all_links = value_lineage_service.list_links(limit=2000)
    idea_link = None
    for link in all_links:
        if link.idea_id == idea_id:
            idea_link = link
            break

    if idea_link is None:
        # Create a new lineage link for this idea
        idea_link = value_lineage_service.create_link(
            LineageLinkCreate(
                idea_id=idea_id,
                spec_id=f"stake-lineage-{idea_id}",
                implementation_refs=[],
                contributors=LineageContributors(),
                investments=[
                    LineageInvestment(
                        stage="staker",
                        contributor=contributor_id,
                        energy_units=amount_cc,
                        coherence_score=0.7,
                        awareness_score=0.7,
                        friction_score=0.3,
                    ),
                ],
                estimated_cost=0.0,
            )
        )
    else:
        # Append investment to existing link
        existing_investments = list(idea_link.investments)
        existing_investments.append(
            LineageInvestment(
                stage="staker",
                contributor=contributor_id,
                energy_units=amount_cc,
                coherence_score=0.7,
                awareness_score=0.7,
                friction_score=0.3,
            )
        )
        # Update the link record in DB
        with value_lineage_service._session() as s:
            rec = s.query(value_lineage_service.LineageLinkRecord).filter_by(id=idea_link.id).first()
            if rec is not None:
                import json as _json
                from datetime import datetime as _dt, timezone as _tz
                rec.investments_json = _json.dumps([i.model_dump(mode="json") for i in existing_investments])
                rec.updated_at = _dt.now(_tz.utc)

    return {
        "idea": updated_idea.model_dump(mode="json") if updated_idea else None,
        "stake_record": stake_record,
        "lineage_id": idea_link.id if idea_link else None,
    }


def answer_question(
    idea_id: str,
    question: str,
    answer: str,
    measured_delta: float | None = None,
) -> tuple[IdeaWithScore | None, bool]:
    ideas = _read_ideas(persist_ensures=True)
    updated: Idea | None = None
    updated_idx: int = -1
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
        updated_idx = idx
        break

    if updated is None:
        return None, False
    if not question_found:
        return _with_score(updated), False

    _write_single_idea(updated, position=updated_idx)
    return _with_score(updated), True


def list_tracked_idea_ids() -> list[str]:
    """Expose tracked idea IDs (from commit evidence artifacts)."""
    return _tracked_idea_ids()


def count_ideas() -> IdeaCountResponse:
    """Return total idea count and breakdown by manifestation status."""
    ideas = _read_ideas()
    by_status = IdeaCountByStatus(
        none=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.NONE),
        partial=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.PARTIAL),
        validated=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED),
    )
    return IdeaCountResponse(total=len(ideas), by_status=by_status)


def storage_info() -> IdeaStorageInfo:
    """Expose idea registry storage backend and row counts for inspection."""
    info = idea_registry_service.storage_info()
    return IdeaStorageInfo(**info)


def compute_governance_health(window_days: int = 30) -> GovernanceHealth:
    """Compute portfolio governance effectiveness metrics (spec 126).

    Returns a snapshot answering: "Is governance producing results,
    and where is it stuck?"
    """
    from datetime import datetime, timezone

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


# ---------------------------------------------------------------------------
# Idea lifecycle stage management (spec 138)
# ---------------------------------------------------------------------------

_STAGE_TO_MANIFESTATION: dict[IdeaStage, ManifestationStatus | None] = {
    IdeaStage.SPECCED: ManifestationStatus.PARTIAL,
    IdeaStage.IMPLEMENTING: ManifestationStatus.PARTIAL,
    IdeaStage.COMPLETE: ManifestationStatus.VALIDATED,
}

# Task type → target stage after that task type completes for the idea.
_TASK_TYPE_TARGET_STAGE: dict[str, IdeaStage] = {
    "spec": IdeaStage.SPECCED,
    "impl": IdeaStage.IMPLEMENTING,
    "test": IdeaStage.TESTING,
    "review": IdeaStage.REVIEWING,
}


def _sync_manifestation_status(idea: Idea) -> None:
    """Update manifestation_status to stay in sync with stage (R9)."""
    new_ms = _STAGE_TO_MANIFESTATION.get(idea.stage)
    if new_ms is not None:
        idea.manifestation_status = new_ms


def advance_idea_stage(idea_id: str) -> tuple[IdeaWithScore | None, str | None]:
    """Advance an idea to the next sequential stage.

    Returns (updated_idea, error_detail). error_detail is None on success.
    """
    ideas = _read_ideas(persist_ensures=True)
    target_idea: Idea | None = None
    target_idx: int = -1
    for idx, idea in enumerate(ideas):
        if idea.id == idea_id:
            target_idea = idea
            target_idx = idx
            break

    if target_idea is None:
        return None, "not_found"

    current_stage = target_idea.stage
    if current_stage == IdeaStage.COMPLETE:
        return _with_score(target_idea), "already_complete"

    current_index = IDEA_STAGE_ORDER.index(current_stage)
    next_stage = IDEA_STAGE_ORDER[current_index + 1]

    target_idea.stage = next_stage
    _sync_manifestation_status(target_idea)
    ideas[target_idx] = target_idea
    _write_single_idea(target_idea, position=target_idx)
    return _with_score(target_idea), None


def set_idea_stage(idea_id: str, stage: IdeaStage) -> tuple[IdeaWithScore | None, str | None]:
    """Explicitly set an idea's stage (admin override).

    Returns (updated_idea, error_detail).
    """
    ideas = _read_ideas(persist_ensures=True)
    target_idea: Idea | None = None
    target_idx: int = -1
    for idx, idea in enumerate(ideas):
        if idea.id == idea_id:
            target_idea = idea
            target_idx = idx
            break

    if target_idea is None:
        return None, "not_found"

    target_idea.stage = stage
    _sync_manifestation_status(target_idea)
    ideas[target_idx] = target_idea
    _write_single_idea(target_idea, position=target_idx)
    return _with_score(target_idea), None


def auto_advance_for_task(idea_id: str, task_type: str) -> None:
    """Best-effort auto-advance: if a task of the given type completes, advance the idea.

    Does nothing if the idea is already at or past the target stage.
    """
    target_stage = _TASK_TYPE_TARGET_STAGE.get(task_type)
    if target_stage is None:
        return

    ideas = _read_ideas(persist_ensures=True)
    target_idea: Idea | None = None
    target_idx: int = -1
    for idx, idea in enumerate(ideas):
        if idea.id == idea_id:
            target_idea = idea
            target_idx = idx
            break

    if target_idea is None:
        return

    current_index = IDEA_STAGE_ORDER.index(target_idea.stage)
    target_index = IDEA_STAGE_ORDER.index(target_stage)

    # Only advance forward, never regress
    if current_index >= target_index:
        return

    target_idea.stage = target_stage
    _sync_manifestation_status(target_idea)
    ideas[target_idx] = target_idea
    _write_single_idea(target_idea, position=target_idx)


def get_resonance_feed(window_hours: int = 24, limit: int = 20) -> list[dict]:
    """Return ideas with recent activity, sorted by most-recent-activity-first.

    Activity is determined by governance change requests updated within the
    window and ideas whose questions were recently answered.  When governance
    data is not easily queryable per-idea we fall back to returning recently
    active governance-referenced ideas merged with recently modified ideas.
    """
    from datetime import datetime, timedelta, timezone
    from app.services import governance_service

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max(1, window_hours))

    # Gather idea IDs referenced by recent governance change requests
    idea_activity: dict[str, datetime] = {}
    try:
        change_requests = governance_service.list_change_requests(limit=500)
        for cr in change_requests:
            cr_updated = cr.updated_at
            if cr_updated.tzinfo is None:
                cr_updated = cr_updated.replace(tzinfo=timezone.utc)
            if cr_updated < cutoff:
                continue
            payload = cr.payload or {}
            # Extract idea_id from payload (used by update / question CRs)
            idea_id = payload.get("idea_id") or payload.get("id")
            if isinstance(idea_id, str) and idea_id.strip():
                existing_ts = idea_activity.get(idea_id)
                if existing_ts is None or cr_updated > existing_ts:
                    idea_activity[idea_id] = cr_updated
    except Exception:
        pass

    ideas = _read_ideas(persist_ensures=False)

    # Build lookup
    idea_map: dict[str, Idea] = {idea.id: idea for idea in ideas}

    # Also consider ideas that have recently answered questions (proxy for
    # updated_at since Idea model lacks that field).  We include all ideas
    # that already appeared via governance plus any with answered questions.
    for idea in ideas:
        if idea.id in idea_activity:
            continue
        for q in idea.open_questions:
            if q.answer and str(q.answer).strip():
                # No timestamp on answers; include at cutoff time as fallback
                idea_activity.setdefault(idea.id, cutoff)
                break

    # Sort by recency
    sorted_ids = sorted(idea_activity.keys(), key=lambda iid: idea_activity[iid], reverse=True)

    feed: list[dict] = []
    for idea_id in sorted_ids:
        if len(feed) >= max(1, limit):
            break
        idea = idea_map.get(idea_id)
        if idea is None:
            continue
        scored = _with_score(idea)
        feed.append({
            "idea_id": idea.id,
            "name": idea.name,
            "last_activity_at": idea_activity[idea_id].isoformat(),
            "free_energy_score": scored.free_energy_score,
            "manifestation_status": idea.manifestation_status.value if idea.manifestation_status else "none",
        })

    return feed


def fork_idea(source_idea_id: str, forker_id: str, adaptation_notes: str | None = None) -> dict:
    """Fork an existing idea, creating a new idea with lineage link."""
    from uuid import uuid4
    from app.models.value_lineage import LineageLinkCreate, LineageContributors

    source = get_idea(source_idea_id)
    if source is None:
        raise ValueError(f"Source idea '{source_idea_id}' not found")

    short_uuid = uuid4().hex[:8]
    fork_id = f"fork-{source_idea_id}-{short_uuid}"
    description = source.description
    if adaptation_notes:
        description = description + "\n\n" + adaptation_notes

    created = create_idea(
        idea_id=fork_id,
        name=f"Fork of: {source.name}",
        description=description,
        potential_value=source.potential_value,
        estimated_cost=source.estimated_cost,
        confidence=round(max(0.0, min(source.confidence * 0.8, 1.0)), 4),
        parent_idea_id=source_idea_id,
        manifestation_status=ManifestationStatus.NONE,
    )
    if created is None:
        raise ValueError("Failed to create forked idea (duplicate ID)")

    # Create value lineage link: source -> fork
    link = value_lineage_service.create_link(
        LineageLinkCreate(
            idea_id=fork_id,
            spec_id=f"fork-lineage-{fork_id}",
            implementation_refs=[f"forked-from-{source_idea_id}"],
            contributors=LineageContributors(research=forker_id),
            estimated_cost=source.estimated_cost,
        )
    )

    return {
        "idea": created.model_dump(),
        "lineage_link_id": link.id,
        "source_idea_id": source_idea_id,
    }


def get_idea_activity(idea_id: str, limit: int = 20) -> list[dict]:
    """Return activity events for an idea."""
    from datetime import datetime, timezone
    from app.services import governance_service

    idea = get_idea(idea_id)
    if idea is None:
        raise ValueError(f"Idea '{idea_id}' not found")

    events: list[dict] = []

    # Check governance change requests referencing this idea
    try:
        change_requests = governance_service.list_change_requests(limit=500)
        for cr in change_requests:
            payload = cr.payload or {}
            ref_id = payload.get("idea_id") or payload.get("id")
            if ref_id != idea_id:
                continue
            cr_updated = cr.updated_at
            if cr_updated.tzinfo is None:
                cr_updated = cr_updated.replace(tzinfo=timezone.utc)
            events.append({
                "type": "change_request",
                "timestamp": cr_updated.isoformat(),
                "summary": f"Change request '{cr.title}' ({cr.status})",
                "contributor_id": cr.proposer_id,
            })
    except Exception:
        pass

    # Check questions for answers
    for q in idea.open_questions:
        if q.answer and str(q.answer).strip():
            events.append({
                "type": "question_answered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": f"Question answered: {q.question[:80]}",
                "contributor_id": None,
            })
        else:
            events.append({
                "type": "question_added",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": f"Question: {q.question[:80]}",
                "contributor_id": None,
            })

    # Check stage
    if idea.stage and idea.stage.value != "none":
        events.append({
            "type": "stage_advanced",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": f"Idea at stage: {idea.stage.value}",
            "contributor_id": None,
        })

    # Check value lineage for recorded value
    try:
        lineage_links = value_lineage_service.list_links(limit=500)
        for link in lineage_links:
            if link.idea_id == idea_id:
                link_updated = link.updated_at
                if link_updated.tzinfo is None:
                    link_updated = link_updated.replace(tzinfo=timezone.utc)
                events.append({
                    "type": "value_recorded",
                    "timestamp": link_updated.isoformat(),
                    "summary": f"Value lineage link: {link.id}",
                    "contributor_id": None,
                })
    except Exception:
        pass

    # Sort by timestamp descending, limit
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:max(1, limit)]


def compute_progress_dashboard() -> ProgressDashboard:
    """Compute per-stage idea counts and completion percentage."""
    ideas = _read_ideas(persist_ensures=False)
    by_stage: dict[str, StageBucket] = {}
    for stage in IDEA_STAGE_ORDER:
        by_stage[stage.value] = StageBucket()

    for idea in ideas:
        stage_val = idea.stage.value if idea.stage else "none"
        if stage_val not in by_stage:
            by_stage[stage_val] = StageBucket()
        by_stage[stage_val].count += 1
        by_stage[stage_val].idea_ids.append(idea.id)

    total = len(ideas)
    complete_count = by_stage.get("complete", StageBucket()).count
    completion_pct = round(complete_count / total, 4) if total > 0 else 0.0

    from datetime import datetime, timezone
    return ProgressDashboard(
        total_ideas=total,
        completion_pct=completion_pct,
        by_stage=by_stage,
        snapshot_at=datetime.now(timezone.utc).isoformat(),
    )
