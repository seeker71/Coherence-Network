"""Read-only idea views — lifecycle, activity feed, concept resonance matches.

Extracted from idea_service.py (#163). All functions are pure reads
that compose other services (governance, resonance tokens, scoring) to
produce visitor-facing dictionaries.

Public surface (re-exported from idea_service):
  get_idea_lifecycle, get_resonance_feed, get_concept_resonance_matches
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.models.idea import (
    Idea,
    IdeaConceptResonanceMatch,
    IdeaConceptResonanceResponse,
)
from app.services.idea_resonance_tokens import (
    _idea_concept_tokens,
    _idea_domain_tokens,
)
from app.services.idea_scoring import _with_score

logger = logging.getLogger(__name__)


def get_idea_lifecycle(idea_id: str) -> dict | None:
    from app.services.idea_service import _read_ideas, get_idea  # noqa: F401
    """Return lifecycle closure state for an idea (R6).

    Returns None when the idea does not exist.
    """
    idea = get_idea(idea_id)
    if idea is None:
        return None

    # Build task summary from agent service
    from app.services import agent_service
    tasks_data = agent_service.list_tasks_for_idea(idea_id)

    task_phases = ["spec", "test", "impl", "review"]
    task_summary: dict[str, dict] = {}
    groups_by_type = {
        g.get("task_type") if isinstance(g, dict) else g.task_type: g
        for g in (tasks_data.get("groups", []) if isinstance(tasks_data, dict) else tasks_data.groups)
    }

    for phase in task_phases:
        group = groups_by_type.get(phase)
        if group is None:
            task_summary[phase] = {"count": 0, "latest_status": None}
        else:
            count = group.get("count") if isinstance(group, dict) else group.count
            # Find latest status — prefer done > completed > running > pending
            status_counts = group.get("status_counts") if isinstance(group, dict) else group.status_counts
            if isinstance(status_counts, dict):
                sc = status_counts
            else:
                sc = status_counts.model_dump() if hasattr(status_counts, "model_dump") else {}
            status_priority = ["done", "completed", "running", "pending", "failed", "needs_decision"]
            latest = None
            for s in status_priority:
                if sc.get(s, 0) > 0:
                    latest = s
                    break
            task_summary[phase] = {"count": count, "latest_status": latest}

    # Determine closure state
    stage = idea.stage if hasattr(idea, "stage") else getattr(idea, "stage", "none")
    stage_val = stage.value if hasattr(stage, "value") else str(stage)
    ms = idea.manifestation_status if hasattr(idea, "manifestation_status") else "none"
    ms_val = ms.value if hasattr(ms, "value") else str(ms)

    is_closed = stage_val == "complete" and ms_val == "validated"

    # Build closure blockers
    blockers: list[str] = []
    if not is_closed:
        for phase in task_phases:
            info = task_summary[phase]
            if info["count"] == 0:
                blockers.append(f"{phase} phase not started")
            elif info["latest_status"] not in ("done", "completed"):
                blockers.append(f"{phase} phase not finished (latest: {info['latest_status']})")

    return {
        "idea_id": idea_id,
        "stage": stage_val,
        "manifestation_status": ms_val,
        "is_closed": is_closed,
        "task_summary": task_summary,
        "closure_blockers": blockers,
    }


def get_resonance_feed(window_hours: int = 24, limit: int = 20) -> list[dict]:
    from app.services.idea_service import _read_ideas, get_idea  # noqa: F401
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
        logger.warning("governance_service unavailable for idea activity", exc_info=True)

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


def get_concept_resonance_matches(
    idea_id: str,
    *,
    limit: int = 5,
    min_score: float = 0.05,
) -> IdeaConceptResonanceResponse | None:
    from app.services.idea_service import _read_ideas, get_idea  # noqa: F401
    """Return conceptually related ideas, sorted to favor cross-domain overlap."""
    source = get_idea(idea_id)
    if source is None:
        return None

    source_concepts = _idea_concept_tokens(source)
    source_domains = _idea_domain_tokens(source)
    if not source_concepts:
        return IdeaConceptResonanceResponse(idea_id=source.id, matches=[], total=0)

    matches: list[IdeaConceptResonanceMatch] = []
    for candidate in _read_ideas(persist_ensures=False):
        if candidate.id == source.id:
            continue

        candidate_concepts = _idea_concept_tokens(candidate)
        shared_concepts = sorted(source_concepts & candidate_concepts)
        if not shared_concepts:
            continue

        candidate_domains = _idea_domain_tokens(candidate)
        combined_concepts = source_concepts | candidate_concepts
        concept_overlap = len(shared_concepts) / max(len(combined_concepts), 1)
        domain_union = source_domains | candidate_domains
        domain_novelty = 0.0
        if domain_union:
            domain_novelty = len(candidate_domains - source_domains) / len(domain_union)
        cross_domain = bool(source_domains and candidate_domains and source_domains != candidate_domains)
        resonance_score = concept_overlap + (0.25 * domain_novelty if cross_domain else 0.0)
        resonance_score = round(min(1.0, resonance_score), 4)
        if resonance_score < min_score:
            continue

        scored_candidate = _with_score(candidate)
        matches.append(
            IdeaConceptResonanceMatch(
                idea_id=candidate.id,
                name=candidate.name,
                resonance_score=resonance_score,
                free_energy_score=scored_candidate.free_energy_score,
                shared_concepts=shared_concepts[:8],
                source_domains=sorted(source_domains),
                candidate_domains=sorted(candidate_domains),
                cross_domain=cross_domain,
            )
        )

    matches.sort(
        key=lambda item: (
            item.cross_domain,
            item.resonance_score,
            item.free_energy_score,
            item.idea_id,
        ),
        reverse=True,
    )
    return IdeaConceptResonanceResponse(
        idea_id=source.id,
        matches=matches[: max(1, limit)],
        total=len(matches),
    )


