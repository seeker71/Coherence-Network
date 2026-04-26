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


# Extracted to idea_lifecycle_ops (#163)
from app.services.idea_lifecycle_ops import (  # noqa: E402,F401
    advance_idea_stage,
    answer_question,
    auto_advance_for_task,
    count_ideas,
    fork_idea,
    list_tracked_idea_ids,
    set_idea_stage,
    stake_on_idea,
    storage_info,
)


# Extracted to idea_governance_views (#163)
from app.services.idea_governance_views import (  # noqa: E402,F401
    compute_governance_health,
    list_showcase_ideas,
)


# Extracted to idea_views (#163)
from app.services.idea_views import (  # noqa: E402,F401
    get_concept_resonance_matches,
    get_idea_lifecycle,
    get_resonance_feed,
)


# Extracted to idea_dashboards (#163)
from app.services.idea_dashboards import (  # noqa: E402,F401
    compute_progress_dashboard,
    get_idea_activity,
    get_portfolio_summary,
)
