"""Idea lifecycle operations — staking, answering, stage transitions, forking.

Extracted from idea_service.py (#163). State-changing operations that
record contributor activity (stake, answer) or transition the idea
through its lifecycle (stage advance, fork).

Public surface (re-exported from idea_service):
  stake_on_idea, answer_question, advance_idea_stage, set_idea_stage,
  auto_advance_for_task, fork_idea
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.idea import (
    IDEA_STAGE_ORDER,
    Idea,
    IdeaCountByStatus,
    IdeaCountResponse,
    IdeaStage,
    IdeaStorageInfo,
    IdeaWithScore,
    ManifestationStatus,
)
from app.services import value_lineage_service
from app.services.idea_scoring import _with_score

logger = logging.getLogger(__name__)


# Stage → manifestation_status mapping (referenced by _sync_manifestation_status)
_STAGE_TO_MANIFESTATION: dict[IdeaStage, ManifestationStatus | None] = {
    IdeaStage.SPECCED: ManifestationStatus.PARTIAL,
    IdeaStage.IMPLEMENTING: ManifestationStatus.PARTIAL,
    IdeaStage.COMPLETE: ManifestationStatus.VALIDATED,
}

_TASK_TYPE_TARGET_STAGE: dict[str, IdeaStage] = {
    "spec": IdeaStage.SPECCED,
    "impl": IdeaStage.IMPLEMENTING,
    "test": IdeaStage.TESTING,
    "review": IdeaStage.REVIEWING,
}


def stake_on_idea(idea_id: str, contributor_id: str, amount_cc: float, rationale: str | None = None) -> dict:
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
    from app.services.idea_service import _tracked_idea_ids
    return _tracked_idea_ids()


def count_ideas() -> IdeaCountResponse:
    """Return total idea count and breakdown by manifestation status."""
    from app.services.idea_service import _read_ideas
    ideas = _read_ideas()
    by_status = IdeaCountByStatus(
        none=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.NONE),
        partial=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.PARTIAL),
        validated=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED),
    )
    return IdeaCountResponse(total=len(ideas), by_status=by_status)


def storage_info() -> IdeaStorageInfo:
    """Expose idea registry storage backend and row counts for inspection."""
    from app.services import idea_registry_service
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
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
    from app.services.idea_service import (
        _read_ideas, _resolve_idea_raw, _write_ideas, _write_single_idea,
        get_idea, update_idea, create_idea,
    )  # noqa: F401
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
