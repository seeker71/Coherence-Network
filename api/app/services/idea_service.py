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
    Idea,
    IdeaSelectionResult,
    IdeaType,
    PaginationInfo,
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


def _read_ideas(*, persist_ensures: bool = True) -> list[Idea]:
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
    ideas = _read_ideas()
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
    ideas = _read_ideas()
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
    ideas = _read_ideas()
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


def answer_question(
    idea_id: str,
    question: str,
    answer: str,
    measured_delta: float | None = None,
) -> tuple[IdeaWithScore | None, bool]:
    ideas = _read_ideas()
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


def storage_info() -> IdeaStorageInfo:
    """Expose idea registry storage backend and row counts for inspection."""
    info = idea_registry_service.storage_info()
    return IdeaStorageInfo(**info)
