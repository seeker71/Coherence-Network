"""Idea portfolio service: persistence, scoring, and prioritization."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.models.idea import (
    Idea,
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


def _load_seed_ideas() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load seed ideas from data/seed_ideas.json (single source of truth)."""
    seed_path = Path(__file__).resolve().parents[3] / "data" / "seed_ideas.json"
    try:
        with open(seed_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("default_ideas", []), data.get("derived_metadata", {})
    except (OSError, json.JSONDecodeError):
        return [], {}


DEFAULT_IDEAS: list[dict[str, Any]]
DERIVED_IDEA_METADATA: dict[str, dict[str, Any]]
DEFAULT_IDEAS, DERIVED_IDEA_METADATA = _load_seed_ideas()

STANDING_QUESTION_TEXT = (
    "How can we improve this idea, show whether it is working yet, "
    "and make that proof clearer over time?"
)

_TRACKED_IDEA_CACHE: dict[str, Any] = {"expires_at": 0.0, "idea_ids": [], "cache_key": ""}
_TRACKED_IDEA_CACHE_TTL_SECONDS = 300.0
REQUIRED_SYSTEM_IDEA_IDS: tuple[str, ...] = (
    "federated-instance-aggregation",
    "community-project-funder-match",
)
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


def _default_portfolio_path() -> str:
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    return os.path.join(logs_dir, "idea_portfolio.json")


def _portfolio_path() -> str:
    return os.getenv("IDEA_PORTFOLIO_PATH", _default_portfolio_path())


def _configured_internal_idea_prefixes() -> set[str]:
    raw = str(os.getenv("INTERNAL_IDEA_ID_PREFIXES", "")).strip()
    if not raw:
        return set(DEFAULT_INTERNAL_IDEA_PREFIXES)
    out = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return out or set(DEFAULT_INTERNAL_IDEA_PREFIXES)


def _configured_internal_idea_exact_ids() -> set[str]:
    out = {idea_id.strip().lower() for idea_id in DERIVED_IDEA_METADATA if idea_id.strip()}
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
    _IDEAS_CACHE["expires_at"] = 0.0
    _IDEAS_CACHE["items"] = []
    _IDEAS_CACHE["cache_key"] = ""


def _cache_ideas(ideas: list[Idea]) -> None:
    _IDEAS_CACHE["items"] = [idea.model_copy(deep=True) for idea in ideas]
    _IDEAS_CACHE["expires_at"] = time.time() + _IDEAS_CACHE_TTL_SECONDS
    _IDEAS_CACHE["cache_key"] = _ideas_cache_key()


def _ideas_cache_key() -> str:
    from app.services import unified_db as _udb
    return (
        f"{_udb.database_url()}|"
        f"{_portfolio_path()}|"
        f"{os.getenv('IDEA_SYNC_RUNTIME_WINDOW_SECONDS','')}|"
        f"{os.getenv('IDEA_SYNC_RUNTIME_EVENT_LIMIT','')}|"
        f"{os.getenv('IDEA_SYNC_CONTRIBUTION_LIMIT','')}"
    )


def _read_ideas_cache() -> list[Idea] | None:
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
    cache_key = (
        f"{_udb.database_url()}"
        f"|{os.getenv('IDEA_PORTFOLIO_PATH','')}"
    )
    if (
        _TRACKED_IDEA_CACHE.get("cache_key") == cache_key
        and _TRACKED_IDEA_CACHE.get("expires_at", 0.0) > now
    ):
        return list(_TRACKED_IDEA_CACHE.get("idea_ids", []))
    idea_ids = _tracked_idea_ids_from_store()

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
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    if not database_url:
        return []

    try:
        contribution_limit_raw = int(str(os.getenv("IDEA_SYNC_CONTRIBUTION_LIMIT", "3000")).strip() or "3000")
    except ValueError:
        contribution_limit_raw = 3000
    contribution_limit = max(1, min(contribution_limit_raw, 20000))

    engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine_kwargs["poolclass"] = NullPool

    rows: list[Any] = []
    try:
        engine = create_engine(database_url, **engine_kwargs)
        with engine.connect() as conn:
            rows = list(
                conn.execute(
                    text("SELECT meta FROM contributions ORDER BY timestamp DESC LIMIT :limit"),
                    {"limit": contribution_limit},
                )
            )
    except Exception:
        return []
    finally:
        try:
            engine.dispose()
        except Exception:
            pass

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


def _read_ideas(*, persist_ensures: bool = True) -> list[Idea]:
    """Load ideas, run ensure logic, optionally persist. When persist_ensures=False (e.g. guard/invariant runs), no writes are made."""
    cached = _read_ideas_cache()
    if cached is not None:
        return cached

    ideas = idea_registry_service.load_ideas()
    if not ideas:
        ideas, source = _read_legacy_file_ideas()
        ideas, required_changed = _ensure_required_system_ideas(ideas)
        ideas, tracked_changed = _ensure_tracked_idea_entries(ideas)
        ideas, domain_discovered_changed = _ensure_registry_domain_idea_entries(ideas)
        ideas, transient_pruned_changed = _prune_transient_internal_ideas(ideas)
        ideas, pruned_changed = _prune_internal_standing_questions(ideas)
        ideas, standing_changed = _ensure_standing_questions(ideas)
        ideas, hierarchy_changed = _ensure_idea_hierarchy(ideas)
        if persist_ensures:
            bootstrap_source = source
            if required_changed:
                bootstrap_source = f"{bootstrap_source}+required_system_ideas"
            if tracked_changed or source == "defaults":
                bootstrap_source = f"{bootstrap_source}+derived"
            if domain_discovered_changed:
                bootstrap_source = f"{bootstrap_source}+domain_discovery"
            if standing_changed or pruned_changed or transient_pruned_changed or hierarchy_changed:
                bootstrap_source = f"{bootstrap_source}+standing_question"
            idea_registry_service.save_ideas(ideas, bootstrap_source=bootstrap_source)
            _write_snapshot_file(ideas)
        _cache_ideas(ideas)
        return ideas

    ideas, required_changed = _ensure_required_system_ideas(ideas)
    ideas, tracked_changed = _ensure_tracked_idea_entries(ideas)
    ideas, domain_discovered_changed = _ensure_registry_domain_idea_entries(ideas)
    ideas, transient_pruned_changed = _prune_transient_internal_ideas(ideas)
    ideas, pruned_changed = _prune_internal_standing_questions(ideas)
    ideas, standing_changed = _ensure_standing_questions(ideas)
    ideas, hierarchy_changed = _ensure_idea_hierarchy(ideas)
    if persist_ensures:
        if (
            required_changed
            or tracked_changed
            or domain_discovered_changed
            or standing_changed
            or pruned_changed
            or transient_pruned_changed
            or hierarchy_changed
        ):
            _write_ideas(ideas)
        else:
            path = _portfolio_path()
            if not os.path.isfile(path):
                _write_snapshot_file(ideas)
    _cache_ideas(ideas)
    return ideas


def _write_ideas(ideas: list[Idea]) -> None:
    idea_registry_service.save_ideas(ideas)
    _write_snapshot_file(ideas)
    _cache_ideas(ideas)


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


def _ensure_idea_hierarchy(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    """Sync idea_type, parent_idea_id, child_idea_ids, and default answers from source to persisted ideas."""
    changed = False
    defaults = _default_idea_map()
    for idea in ideas:
        source = defaults.get(idea.id) or DERIVED_IDEA_METADATA.get(idea.id)
        if not source:
            continue
        # Sync idea_type
        new_type_str = source.get("idea_type")
        if new_type_str:
            try:
                new_type = IdeaType(new_type_str)
            except ValueError:
                new_type = None
            if new_type and idea.idea_type != new_type:
                idea.idea_type = new_type
                changed = True
        # Sync parent_idea_id
        new_parent = source.get("parent_idea_id")
        if new_parent and idea.parent_idea_id != new_parent:
            idea.parent_idea_id = new_parent
            changed = True
        # Sync child_idea_ids
        new_children = source.get("child_idea_ids")
        if isinstance(new_children, list) and sorted(idea.child_idea_ids) != sorted(new_children):
            idea.child_idea_ids = list(new_children)
            changed = True
        # Sync default answers: only if the persisted question has no answer yet
        source_questions = source.get("open_questions", [])
        if isinstance(source_questions, list):
            source_answers = {
                q["question"]: q
                for q in source_questions
                if isinstance(q, dict) and q.get("answer")
            }
            if source_answers:
                for q in idea.open_questions:
                    if q.answer:
                        continue
                    source_q = source_answers.get(q.question)
                    if source_q and source_q.get("answer"):
                        q.answer = source_q["answer"]
                        if source_q.get("measured_delta") is not None:
                            q.measured_delta = source_q["measured_delta"]
                        changed = True
    return ideas, changed


def _score(idea: Idea) -> float:
    denom = max(idea.estimated_cost + idea.resistance_risk, 0.0001)
    return (idea.potential_value * idea.confidence) / denom


def _with_score(idea: Idea) -> IdeaWithScore:
    value_gap = max(idea.potential_value - idea.actual_value, 0.0)
    return IdeaWithScore(**idea.model_dump(), free_energy_score=round(_score(idea), 4), value_gap=round(value_gap, 4))


def list_ideas(
    only_unvalidated: bool = False,
    limit: int | None = None,
    offset: int = 0,
    include_internal: bool = True,
    read_only_guard: bool = False,
) -> IdeaPortfolioResponse:
    """When read_only_guard=True, ensure logic is applied in memory but not persisted (for invariant/guard runs)."""
    ideas = _read_ideas(persist_ensures=not read_only_guard)
    if not include_internal:
        ideas = [i for i in ideas if not is_internal_idea_id(i.id, i.interfaces)]
    if only_unvalidated:
        ideas = [i for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED]

    ranked = sorted((_with_score(i) for i in ideas), key=lambda i: i.free_energy_score, reverse=True)
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
    if idea_id in DERIVED_IDEA_METADATA:
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
