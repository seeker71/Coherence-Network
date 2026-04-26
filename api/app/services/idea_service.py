"""Idea portfolio service: pure DB reader with runtime discovery.

The DB (data/coherence.db) is the single source of truth for ideas.
Seed data is loaded via `scripts/seed_db.py`, not at runtime.
This module reads from DB, discovers new ideas from runtime evidence,
and writes back only genuinely new discoveries.
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
import threading
import time
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.config_loader import get_int, get_str
from app.models.coherence_credit import CostVector, ValueVector
from app.models.idea import (
    IDEA_STAGE_ORDER,
    GovernanceHealth,
    Idea,
    IdeaConceptResonanceMatch,
    IdeaConceptResonanceResponse,
    IdeaCountByStatus,
    IdeaCountResponse,
    IdeaLifecycle,
    IdeaShowcaseBudget,
    IdeaShowcaseItem,
    IdeaShowcaseResponse,
    IdeaSelectionResult,
    IdeaStage,
    IdeaTagCatalogEntry,
    IdeaTagCatalogResponse,
    IdeaTagUpdateResponse,
    IdeaType,
    IdeaWorkType,
    PaginationInfo,
    ProgressDashboard,
    IdeaPortfolioResponse,
    IdeaQuestionCreate,
    IdeaQuestion,
    IdeaSummary,
    IdeaStorageInfo,
    IdeaWithScore,
    ManifestationStatus,
    RollupChildStatus,
    RollupProgress,
    StageBucket,
)
from app.models.audit_ledger import AuditEntryCreate, AuditEntryType
from app.services import audit_ledger_service
from app.services import idea_graph_adapter as idea_registry_service  # Graph-backed
from app.services import idea_registry_service as _tag_store  # SQLAlchemy tag persistence
from app.services import commit_evidence_service
from app.services import runtime_service
from app.services import spec_registry_service
from app.services import value_lineage_service
from app.services.app_mode import debug_audit_enabled, running_under_test

logger = logging.getLogger(__name__)


# normalize_tags / validate_raw_tags / slugify moved to idea_text_helpers.py;
# re-imported below for backward compat (#163 modularity drift)
from app.services.idea_naming import (  # noqa: E402,F401
    _TAG_SLUG_PATTERN,
    normalize_tags,
    slugify,
    validate_raw_tags,
)
from app.services.idea_internal_filter import (  # noqa: E402,F401
    DEFAULT_INTERNAL_IDEA_PREFIXES,
    DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS,
    DISCOVERED_INTERNAL_ID_ALIASES,
    TRANSIENT_INTERNAL_ID_PATTERNS,
    _KNOWN_INTERNAL_IDEA_IDS,
    _SCHEMA_ARTIFACT_IDS,
    _canonical_discovered_idea_id,
    _configured_internal_idea_exact_ids,
    _configured_internal_idea_interface_tags,
    _configured_internal_idea_prefixes,
    _is_transient_internal_idea_id,
    _should_track_discovered_idea_id,
    canonical_discovered_idea_id,
    is_internal_idea_id,
)


def is_idea_external(idea_id: str) -> bool:
    """Return True if the idea has a workspace_git_url set (external repo manifestation)."""
    idea = get_idea(idea_id)
    if idea is None:
        return False
    if hasattr(idea, "workspace_git_url") and idea.workspace_git_url:
        return True
    if hasattr(idea, "idea") and hasattr(idea.idea, "workspace_git_url") and idea.idea.workspace_git_url:
        return True
    return False


def get_workspace_git_url(idea_id: str) -> str | None:
    """Return the workspace_git_url for an idea if set, None otherwise."""
    idea = get_idea(idea_id)
    if idea is None:
        return None
    if hasattr(idea, "workspace_git_url"):
        return idea.workspace_git_url
    if hasattr(idea, "idea") and hasattr(idea.idea, "workspace_git_url"):
        return idea.idea.workspace_git_url
    return None






def _resolve_idea_raw(id_or_slug: str, ideas: list) -> "Idea | None":
    """Resolve UUID, current slug, or historical slug to an Idea object."""
    # 1. Exact id match (UUID or legacy slug)
    for idea in ideas:
        if idea.id == id_or_slug:
            return idea
    # 2. Current slug match
    for idea in ideas:
        if idea.slug == id_or_slug:
            return idea
    # 3. Historical slug match
    for idea in ideas:
        if id_or_slug in (idea.slug_history or []):
            return idea
    return None


# Known internal idea IDs — these were previously loaded from derived_metadata
# in seed_ideas.json and are used for internal-idea classification only.
# The DB is the sole source of truth for idea data; this set is only for
# the is_internal_idea_id() classification heuristic.


_CACHE_LOCK = threading.Lock()
_TRACKED_IDEA_CACHE: dict[str, Any] = {"expires_at": 0.0, "idea_ids": [], "cache_key": ""}
_TRACKED_IDEA_CACHE_TTL_SECONDS = 300.0
_IDEAS_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": []}
_IDEAS_CACHE_TTL_SECONDS = 30.0  # 30s cache — prevents DB hammering under load












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
        logger.warning("commit_evidence_service unavailable", exc_info=True)
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
        f"{get_int('ideas', 'sync_runtime_window_seconds')}|"
        f"{get_int('ideas', 'sync_runtime_event_limit')}|"
        f"{get_int('ideas', 'sync_contribution_limit')}"
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
    explicit = get_str("ideas", "sync_enable_domain_discovery")
    if explicit:
        explicit = explicit.strip().lower()
        if explicit in {"1", "true", "yes", "on"}:
            return True
        if explicit in {"0", "false", "no", "off"}:
            return False
    if running_under_test():
        return False
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
        logger.warning("spec_registry_service unavailable during idea discovery", exc_info=True)
        spec_rows = []
    for row in spec_rows:
        idea_id = str(getattr(row, "idea_id", "") or "").strip()
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)

    try:
        lineage_rows = value_lineage_service.list_links(limit=2000)
    except Exception:
        logger.warning("value_lineage_service unavailable during idea discovery", exc_info=True)
        lineage_rows = []
    for row in lineage_rows:
        idea_id = str(getattr(row, "idea_id", "") or "").strip()
        canonical_id = _canonical_discovered_idea_id(idea_id)
        if canonical_id:
            discovered.add(canonical_id)

    runtime_window_raw = get_int("ideas", "sync_runtime_window_seconds") or 86400
    runtime_window_seconds = max(60, min(runtime_window_raw, 60 * 60 * 24 * 30))

    runtime_limit_raw = get_int("ideas", "sync_runtime_event_limit") or 2000
    runtime_event_limit = max(1, min(runtime_limit_raw, 5000))
    try:
        runtime_rows = runtime_service.summarize_by_idea(
            seconds=runtime_window_seconds,
            event_limit=runtime_event_limit,
            summary_limit=2000,
            summary_offset=0,
        )
    except Exception:
        logger.warning("runtime_service unavailable during idea discovery", exc_info=True)
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

    contribution_limit_raw = get_int("ideas", "sync_contribution_limit") or 3000
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
        logger.warning("DB query for contribution metadata failed", exc_info=True)
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


# Extracted to idea_resonance_helpers.py (#163)
from app.services.idea_resonance_tokens import (  # noqa: E402,F401
    _CONCEPT_RESONANCE_STOP_WORDS,
    _FUZZY_STOP_WORDS,
    _RESONANCE_TOKEN_PATTERN,
    _extract_resonance_tokens,
    _find_closest_graph_idea,
    _humanize_idea_id,
    _idea_concept_tokens,
    _idea_domain_tokens,
)


# Extracted to idea_derive_helper.py (#163)
from app.services.idea_derivation import (  # noqa: E402,F401
    _derived_idea_for_id,
    _idea_to_metadata,
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

    # Overlay tags from the SQLAlchemy tag store
    try:
        all_tags = _tag_store.load_all_idea_tags()
        if all_tags:
            for idea in ideas:
                if idea.id in all_tags:
                    idea.tags = all_tags[idea.id]
    except Exception:
        pass  # Non-fatal: ideas load without tags if tag table unavailable

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


# Extracted to idea_standing_questions (#163)
from app.services.idea_standing_questions import (  # noqa: E402,F401
    STANDING_QUESTION_TEXT,
    _ensure_standing_questions,
    _prune_internal_standing_questions,
)


# Extracted to idea_scoring_helpers (#163)
from app.services.idea_scoring import (  # noqa: E402,F401
    _build_cost_vector,
    _build_value_vector,
    _marginal_cc_return,
    _score,
    _softmax_weights,
    _with_score,
)


# Extracted to idea_selection (#163)
from app.services.idea_selection import select_idea  # noqa: E402,F401


# Extracted to idea_read (#163)
from app.services.idea_read import get_idea, list_ideas  # noqa: E402,F401


# Extracted to idea_write_ops (#163)
from app.services.idea_write_ops import (  # noqa: E402,F401
    add_question,
    create_idea,
    get_tag_catalog,
    set_idea_tags,
    update_idea,
    update_idea_slug,
    update_ideas_batch,
)


# Extracted to idea_hierarchy (#163)
from app.services.idea_hierarchy import (  # noqa: E402,F401
    get_rollup_progress,
    list_children_of,
    set_parent_idea,
    validate_super_idea,
)


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


# Extracted to idea_governance_views (#163)
from app.services.idea_governance_views import (  # noqa: E402,F401
    compute_governance_health,
    list_showcase_ideas,
)

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

    Special case (R3): when a review task completes, the idea advances to
    ``reviewing`` and then immediately to ``complete`` (with manifestation_status
    set to ``validated``), closing the idea lifecycle.
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

    # R3: Review completion closes the idea — advance from reviewing to complete
    if task_type == "review" and target_idea.stage == IdeaStage.REVIEWING:
        target_idea.stage = IdeaStage.COMPLETE
        _sync_manifestation_status(target_idea)

    ideas[target_idx] = target_idea
    _write_single_idea(target_idea, position=target_idx)


# Extracted to idea_views (#163)
from app.services.idea_views import (  # noqa: E402,F401
    get_concept_resonance_matches,
    get_idea_lifecycle,
    get_resonance_feed,
)


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


# Extracted to idea_dashboards (#163)
from app.services.idea_dashboards import (  # noqa: E402,F401
    compute_progress_dashboard,
    get_idea_activity,
    get_portfolio_summary,
)
