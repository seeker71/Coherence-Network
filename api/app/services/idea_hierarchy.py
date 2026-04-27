"""Idea hierarchy — parent/child relationships and super-idea rollup.

Extracted from idea_service.py (#163). Operations on the parent_idea_id /
child_idea_ids structure plus the rollup criteria for super-ideas.

Public surface (re-exported from idea_service):
  set_parent_idea, list_children_of, get_rollup_progress, validate_super_idea
"""

from __future__ import annotations

from app.models.idea import (
    Idea,
    IdeaType,
    IdeaWithScore,
    ManifestationStatus,
    RollupChildStatus,
    RollupProgress,
)
from app.services.idea_scoring import _with_score


def set_parent_idea(idea_id: str, parent_idea_id: str) -> bool:
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
    )  # noqa: F401
    """Set or update the parent_idea_id for an idea, maintaining child_idea_ids on parent."""
    ideas = _read_ideas(persist_ensures=True)
    target: Idea | None = None
    target_idx: int = -1
    old_parent_id: str | None = None

    for idx, idea in enumerate(ideas):
        if idea.id == idea_id:
            target = idea
            target_idx = idx
            old_parent_id = idea.parent_idea_id
            break

    if target is None:
        return False

    # Remove from old parent's child_idea_ids
    if old_parent_id and old_parent_id != parent_idea_id:
        for idea in ideas:
            if idea.id == old_parent_id and idea_id in idea.child_idea_ids:
                idea.child_idea_ids.remove(idea_id)
                _write_single_idea(idea, position=ideas.index(idea))
                break

    # Set new parent
    target.parent_idea_id = parent_idea_id if parent_idea_id != "" else None

    # Add to new parent's child_idea_ids
    if parent_idea_id:
        for idea in ideas:
            if idea.id == parent_idea_id and idea_id not in idea.child_idea_ids:
                idea.child_idea_ids.append(idea_id)
                _write_single_idea(idea, position=ideas.index(idea))
                break

    _write_single_idea(target, position=target_idx)
    return True


def list_children_of(parent_idea_id: str) -> list[IdeaWithScore]:
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
    )  # noqa: F401
    """Return all ideas whose parent_idea_id matches the given id, sorted by free-energy score desc."""
    ideas = _read_ideas(persist_ensures=False)
    children = [i for i in ideas if i.parent_idea_id == parent_idea_id]
    scored = [_with_score(i) for i in children]
    scored.sort(key=lambda i: i.free_energy_score, reverse=True)
    return scored


# ── Super-idea rollup (spec: super-idea-rollup-criteria) ─────────────────────


def get_rollup_progress(idea_id: str) -> RollupProgress | None:
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
    )  # noqa: F401
    """Return rollup progress for a super-idea: children validated / total children.

    Works for any idea type but is most meaningful for super-ideas.
    Returns None when idea_id does not exist.
    """
    ideas = _read_ideas(persist_ensures=False)
    parent = _resolve_idea_raw(idea_id, ideas)
    if parent is None:
        return None

    children_raw = [i for i in ideas if i.parent_idea_id == parent.id]
    children_total = len(children_raw)
    children_validated = sum(
        1 for c in children_raw if c.manifestation_status == ManifestationStatus.VALIDATED
    )

    all_validated = children_total > 0 and children_validated == children_total
    # Rollup is considered met when all children are validated.
    # The rollup_condition field is descriptive (human-readable) at this stage;
    # it is surfaced so operators can verify it manually.
    rollup_met = all_validated

    progress_pct = round(
        (children_validated / children_total * 100.0) if children_total > 0 else 0.0,
        2,
    )

    child_statuses = [
        RollupChildStatus(
            idea_id=c.id,
            name=c.name,
            manifestation_status=c.manifestation_status.value,
            validated=c.manifestation_status == ManifestationStatus.VALIDATED,
        )
        for c in children_raw
    ]

    return RollupProgress(
        idea_id=parent.id,
        idea_name=parent.name,
        idea_type=parent.idea_type.value,
        rollup_condition=parent.rollup_condition,
        children_total=children_total,
        children_validated=children_validated,
        progress_pct=progress_pct,
        all_children_validated=all_validated,
        rollup_met=rollup_met,
        manifestation_status=parent.manifestation_status.value,
        children=child_statuses,
    )


def validate_super_idea(idea_id: str) -> tuple[RollupProgress | None, str | None]:
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea, update_idea,
    )  # noqa: F401
    """Check rollup criteria for a super-idea and auto-update manifestation_status.

    Returns (progress, error_string).
    - error_string is None on success.
    - "not_found" when idea does not exist.
    - "not_super" when idea is not a super-idea.

    R2: Checks all children validated + rollup condition.
    R3: Auto-updates manifestation_status when rollup criteria are met.
         Also downgrades back to partial if a child regresses.
    """
    ideas = _read_ideas(persist_ensures=False)
    parent = _resolve_idea_raw(idea_id, ideas)
    if parent is None:
        return None, "not_found"

    if parent.idea_type != IdeaType.SUPER:
        return None, "not_super"

    progress = get_rollup_progress(idea_id)
    if progress is None:
        return None, "not_found"

    # Determine desired status
    if progress.rollup_met:
        desired = ManifestationStatus.VALIDATED
    elif progress.children_validated > 0:
        desired = ManifestationStatus.PARTIAL
    else:
        desired = ManifestationStatus.NONE

    # Auto-update if status changed (R3)
    if parent.manifestation_status != desired:
        update_idea(parent.id, manifestation_status=desired)
        # Refresh progress to reflect new status
        progress = get_rollup_progress(idea_id)

    return progress, None

