"""Idea CRUD writes — create, update, batch update, slug update, tags, questions.

Extracted from idea_service.py (#163). Mutating operations on the idea
portfolio. Each write goes through _write_ideas / _write_single_idea
(in idea_service) and invalidates the read cache.

Public surface (re-exported from idea_service):
  create_idea, set_idea_tags, get_tag_catalog, add_question,
  update_idea, update_ideas_batch, update_idea_slug
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.models.audit_ledger import AuditEntryCreate, AuditEntryType
from app.models.idea import (
    Idea,
    IdeaLifecycle,
    IdeaQuestion,
    IdeaQuestionCreate,
    IdeaTagCatalogEntry,
    IdeaTagCatalogResponse,
    IdeaTagUpdateResponse,
    IdeaType,
    IdeaWithScore,
    ManifestationStatus,
)
from app.services import audit_ledger_service, idea_registry_service as _tag_store
from app.services.app_mode import debug_audit_enabled
from app.services.idea_naming import normalize_tags, slugify
from app.services.idea_scoring import _with_score
from app.services.idea_standing_questions import (
    STANDING_QUESTION_TEXT,
    _ensure_standing_questions,
)

logger = logging.getLogger(__name__)


def create_idea(
    idea_id: str | None,
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
    tags: list[str] | None = None,
    work_type: IdeaWorkType | None = None,
    lifecycle: IdeaLifecycle | None = None,
    duplicate_of: str | None = None,
    workspace_git_url: str | None = None,
    slug: str | None = None,
    pillar: str | None = None,
    workspace_id: str | None = None,
    rollup_condition: str | None = None,
) -> IdeaWithScore | None:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    # Auto-generate UUID4 when caller omits the ID (new convention going forward)
    resolved_id: str = idea_id or str(uuid4())

    ideas = _read_ideas(persist_ensures=True)
    if any(existing.id == resolved_id for existing in ideas):
        return None

    normalized_tags = normalize_tags(tags or [])

    # Derive and uniquify slug
    raw_slug = slug or slugify(name)
    existing_slugs = {i.slug for i in ideas}
    if raw_slug not in existing_slugs or any(i.id == resolved_id and i.slug == raw_slug for i in ideas):
        final_slug = raw_slug
    else:
        suffix = 2
        while f"{raw_slug}-{suffix}" in existing_slugs:
            suffix += 1
        final_slug = f"{raw_slug}-{suffix}"

    idea = Idea(
        id=resolved_id,
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
        tags=normalized_tags,
        work_type=work_type,
        lifecycle=lifecycle or IdeaLifecycle.ACTIVE,
        duplicate_of=duplicate_of,
        workspace_git_url=workspace_git_url,
        slug=final_slug,
        slug_history=[],
        pillar=pillar,
        workspace_id=workspace_id or "coherence-network",
        rollup_condition=rollup_condition,
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

    # Persist tags to the SQLAlchemy tag store
    if normalized_tags:
        try:
            _tag_store.set_idea_tags(idea_id, normalized_tags)
        except Exception:
            pass  # Non-fatal; tags are already on the in-memory idea

    return _with_score(idea)


def set_idea_tags(idea_id: str, tags: list[str]) -> IdeaTagUpdateResponse | None:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    """Replace the full tag set for an idea. Returns None if idea not found.

    Tags are already expected to be normalized; this function persists them.
    """
    found = any(i.id == idea_id for i in _read_ideas())
    if not found:
        return None
    _tag_store.set_idea_tags(idea_id, tags)
    _invalidate_ideas_cache()
    return IdeaTagUpdateResponse(id=idea_id, tags=tags)


def get_tag_catalog() -> IdeaTagCatalogResponse:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    """Return the full normalized tag catalog with idea counts."""
    counts = _tag_store.get_all_tag_counts()
    entries = [
        IdeaTagCatalogEntry(tag=tag, idea_count=count)
        for tag, count in sorted(counts.items())
        if count >= 1
    ]
    return IdeaTagCatalogResponse(tags=entries)


def add_question(
    idea_id: str,
    question: str,
    value_to_whole: float,
    estimated_cost: float,
) -> tuple[IdeaWithScore | None, bool]:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
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
    description: str | None = None,
    name: str | None = None,
    work_type: IdeaWorkType | None = None,
    lifecycle: IdeaLifecycle | None = None,
    duplicate_of: str | None = None,
    workspace_git_url: str | None = None,
    interfaces: list[str] | None = None,
) -> IdeaWithScore | None:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    """Update an idea.

    Public API patch contract remains limited to actual_value/actual_cost/confidence/
    manifestation_status. Internal services may also adjust potential_value and
    estimated_cost for ROI normalization/calibration flows.
    """
    ideas = _read_ideas(persist_ensures=True)
    resolved = _resolve_idea_raw(idea_id, ideas)
    resolved_id = resolved.id if resolved else idea_id
    updated: Idea | None = None
    updated_idx: int = -1

    for idx, idea in enumerate(ideas):
        if idea.id != resolved_id:
            continue
        
        # Track changes for audit ledger
        changes = []
        import datetime as _dt
        idea.last_activity_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        if actual_value is not None and actual_value != idea.actual_value:
            changes.append(("actual_value", idea.actual_value, actual_value))
            idea.actual_value = actual_value
        if actual_cost is not None and actual_cost != idea.actual_cost:
            changes.append(("actual_cost", idea.actual_cost, actual_cost))
            idea.actual_cost = actual_cost
        if confidence is not None and confidence != idea.confidence:
            changes.append(("confidence", idea.confidence, confidence))
            idea.confidence = confidence
        if manifestation_status is not None and manifestation_status != idea.manifestation_status:
            changes.append(("manifestation_status", idea.manifestation_status.value, manifestation_status.value))
            idea.manifestation_status = manifestation_status
        if potential_value is not None and potential_value != idea.potential_value:
            changes.append(("potential_value", idea.potential_value, float(potential_value)))
            idea.potential_value = max(0.0, float(potential_value))
        if estimated_cost is not None and estimated_cost != idea.estimated_cost:
            changes.append(("estimated_cost", idea.estimated_cost, float(estimated_cost)))
            idea.estimated_cost = max(0.0, float(estimated_cost))
        if description is not None and description != idea.description:
            changes.append(("description", idea.description, description))
            idea.description = description
        if name is not None and name != idea.name:
            changes.append(("name", idea.name, name))
            idea.name = name
        if work_type is not None and work_type != idea.work_type:
            changes.append(("work_type", str(idea.work_type) if idea.work_type else None, work_type.value))
            idea.work_type = work_type
        if lifecycle is not None and lifecycle != idea.lifecycle:
            changes.append(("lifecycle", str(idea.lifecycle) if idea.lifecycle else None, lifecycle.value))
            idea.lifecycle = lifecycle
        if duplicate_of is not None and duplicate_of != idea.duplicate_of:
            changes.append(("duplicate_of", idea.duplicate_of, duplicate_of))
            idea.duplicate_of = duplicate_of
        if workspace_git_url is not None:
            idea.workspace_git_url = workspace_git_url
        if interfaces is not None and interfaces != idea.interfaces:
            changes.append(("interfaces", idea.interfaces, interfaces))
            idea.interfaces = interfaces

        for field, old_val, new_val in changes:
            if debug_audit_enabled():
                print(f"DEBUG: update_idea creating audit entry for {field}: {old_val} -> {new_val}")
            audit_ledger_service.append_entry(
                AuditEntryCreate(
                    entry_type=AuditEntryType.VALUATION_CHANGE,
                    sender_id="SYSTEM",
                    receiver_id="SYSTEM",
                    reason=f"Updated {field} for idea {idea_id}",
                    reference_id=idea_id,
                    metadata={
                        "field": field,
                        "old_value": old_val,
                        "new_value": new_val,
                    },
                )
            )
            
        ideas[idx] = idea
        updated = idea
        updated_idx = idx
        break

    if updated is None:
        logger.info("Idea not found for update: %s", idea_id)
        return None

    _write_single_idea(updated, position=updated_idx)
    return _with_score(updated)


def update_ideas_batch(
    updates: list[dict],
) -> list[IdeaWithScore | None]:
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    """Apply many updates in a single read+write cycle (no N+1).

    Each update dict must have `idea_id` plus any of the mutable fields
    accepted by `update_idea`:
      - actual_value, actual_cost, confidence (float | None)
      - manifestation_status (ManifestationStatus | None)
      - potential_value, estimated_cost, description, name (float/str | None)

    Returns an IdeaWithScore for each update in input order, or None for
    ideas that could not be resolved. The batch performs a single
    `_read_ideas()` call and a single `_write_ideas()` call, which is
    dramatically faster than looping `update_idea()` (each iteration of
    which re-reads the full portfolio because `_write_single_idea()`
    invalidates the cache).

    Audit ledger entries are still written per change, matching the
    individual-update path. Callers that want to skip audit entirely
    should write directly via `idea_registry_service`.
    """
    import datetime as _dt
    if not updates:
        return []

    ideas = _read_ideas(persist_ensures=True)
    by_id: dict[str, int] = {idea.id: idx for idx, idea in enumerate(ideas)}
    results: list[IdeaWithScore | None] = []
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    dirty = False

    for update in updates:
        idea_id = update.get("idea_id")
        if not idea_id:
            results.append(None)
            continue
        resolved = _resolve_idea_raw(idea_id, ideas)
        if resolved is None:
            results.append(None)
            logger.info("Idea not found in batch update: %s", idea_id)
            continue
        idx = by_id.get(resolved.id)
        if idx is None:
            results.append(None)
            continue

        idea = ideas[idx]
        changes: list[tuple[str, object, object]] = []
        idea.last_activity_at = now_iso

        def _set(field_name: str, value: object) -> None:
            if value is None:
                return
            current = getattr(idea, field_name)
            if current != value:
                changes.append((field_name, current, value))
                setattr(idea, field_name, value)

        _set("actual_value", update.get("actual_value"))
        _set("actual_cost", update.get("actual_cost"))
        _set("confidence", update.get("confidence"))
        _set("potential_value", update.get("potential_value"))
        _set("estimated_cost", update.get("estimated_cost"))
        ms = update.get("manifestation_status")
        if ms is not None and ms != idea.manifestation_status:
            changes.append(("manifestation_status", idea.manifestation_status.value, ms.value if hasattr(ms, "value") else str(ms)))
            idea.manifestation_status = ms

        # Audit entries — per change, same shape as update_idea.
        for field, old_val, new_val in changes:
            try:
                audit_ledger_service.append_entry(
                    AuditEntryCreate(
                        entry_type=AuditEntryType.VALUATION_CHANGE,
                        sender_id="SYSTEM",
                        receiver_id="SYSTEM",
                        reason=f"Updated {field} for idea {idea_id} (batch)",
                        reference_id=idea_id,
                        metadata={
                            "field": field,
                            "old_value": old_val,
                            "new_value": new_val,
                        },
                    )
                )
            except Exception:
                # Audit failures must never abort the data write
                logger.warning("audit_ledger append failed for %s in batch", idea_id, exc_info=True)

        if changes:
            dirty = True
            ideas[idx] = idea
        results.append(_with_score(idea))

    if dirty:
        _write_ideas(ideas)

    return results


def update_idea_slug(
    id_or_slug: str,
    new_slug: str,
) -> "IdeaWithScore | None":
    from app.services.idea_service import (
        _invalidate_ideas_cache,
        _read_ideas,
        _resolve_idea_raw,
        _write_ideas,
        _write_single_idea,
        get_idea,
    )  # noqa: F401
    """Rename an idea's slug. Appends old slug to history for permanent redirect."""
    ideas = _read_ideas(persist_ensures=True)
    idea = _resolve_idea_raw(id_or_slug, ideas)
    if idea is None:
        return None

    # Validate: new slug must not be current slug of a different idea
    new_slug_norm = slugify(new_slug) if new_slug else ""
    if not new_slug_norm:
        return None
    for other in ideas:
        if other.id != idea.id and other.slug == new_slug_norm:
            raise ValueError(f"Slug '{new_slug_norm}' is already used by idea '{other.id}'")

    old_slug = idea.slug
    if old_slug != new_slug_norm:
        if old_slug and old_slug not in idea.slug_history:
            idea.slug_history = list(idea.slug_history) + [old_slug]
        idea.slug = new_slug_norm

    from datetime import datetime, timezone
    idea.last_activity_at = datetime.now(timezone.utc).isoformat()

    idx = next((i for i, x in enumerate(ideas) if x.id == idea.id), 0)
    _write_single_idea(idea, position=idx)
    return _with_score(idea)


