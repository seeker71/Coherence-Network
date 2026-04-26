"""Idea dashboards — portfolio summary, progress dashboard, per-idea activity.

Extracted from idea_service.py (#163). Composite read functions that
roll multiple idea fields + governance signals into visitor-facing
reports.

Public surface (re-exported from idea_service):
  get_idea_activity, get_portfolio_summary, compute_progress_dashboard
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.models.idea import (
    IDEA_STAGE_ORDER,
    Idea,
    ManifestationStatus,
    ProgressDashboard,
    StageBucket,
)
from app.services import spec_registry_service
from app.services.idea_internal_filter import is_internal_idea_id

logger = logging.getLogger(__name__)


def get_idea_activity(idea_id: str, limit: int = 20) -> list[dict]:
    from app.services.idea_service import get_idea  # noqa: F401
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
        logger.warning("governance_service unavailable for idea timeline", exc_info=True)

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
        logger.warning("value_lineage_service unavailable for idea timeline", exc_info=True)

    # Sort by timestamp descending, limit
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:max(1, limit)]


def get_portfolio_summary() -> dict:
    from app.services.idea_service import _read_ideas  # noqa: F401
    """Return a summary of curated super-ideas grouped by pillar with health status.

    Health logic:
      - "red":    no specs linked at all
      - "green":  has specs AND (actual_value > 0 OR activity within 30 days OR any active spec)
      - "yellow": has specs but all done, no recorded value, no recent activity
    """
    from datetime import datetime, timedelta, timezone

    ideas = _read_ideas(persist_ensures=False)
    curated = [i for i in ideas if i.is_curated]

    # Pre-fetch all specs once to avoid N+1
    all_specs = spec_registry_service.list_specs(limit=1000, offset=0)
    specs_by_idea: dict[str, list] = {}
    for spec in all_specs:
        if spec.idea_id:
            specs_by_idea.setdefault(spec.idea_id, []).append(spec)

    children_by_parent: dict[str, int] = {}
    for idea in ideas:
        if idea.parent_idea_id:
            children_by_parent[idea.parent_idea_id] = children_by_parent.get(idea.parent_idea_id, 0) + 1

    recent_threshold = datetime.now(timezone.utc) - timedelta(days=30)
    items: list[dict] = []
    pillar_stats: dict[str, dict] = {}

    for idea in curated:
        idea_specs = specs_by_idea.get(idea.id, [])
        spec_count = len(idea_specs)
        done_spec_count = sum(1 for s in idea_specs if s.actual_value > 0)
        active_spec_count = spec_count - done_spec_count
        child_count = children_by_parent.get(idea.id, 0)

        if spec_count == 0:
            health = "red"
        else:
            has_value = idea.actual_value > 0
            has_recent_activity = False
            if idea.last_activity_at:
                try:
                    activity_dt = datetime.fromisoformat(idea.last_activity_at.replace("Z", "+00:00"))
                    has_recent_activity = activity_dt > recent_threshold
                except (ValueError, TypeError):
                    pass
            health = "green" if (has_value or has_recent_activity or active_spec_count > 0) else "yellow"

        pillar = idea.pillar or "unknown"
        items.append({
            "idea_id": idea.id,
            "name": idea.name,
            "stage": idea.stage.value if idea.stage else "none",
            "pillar": pillar,
            "spec_count": spec_count,
            "done_spec_count": done_spec_count,
            "active_spec_count": active_spec_count,
            "child_idea_count": child_count,
            "health_status": health,
        })

        stats = pillar_stats.setdefault(pillar, {
            "pillar": pillar,
            "idea_count": 0,
            "total_specs": 0,
            "done_specs": 0,
            "active_specs": 0,
        })
        stats["idea_count"] += 1
        stats["total_specs"] += spec_count
        stats["done_specs"] += done_spec_count
        stats["active_specs"] += active_spec_count

    items.sort(key=lambda x: (x["pillar"], x["name"]))

    return {
        "total_ideas": len(items),
        "total_specs": sum(e["spec_count"] for e in items),
        "total_done_specs": sum(e["done_spec_count"] for e in items),
        "pillars": sorted(pillar_stats.values(), key=lambda p: p["pillar"]),
        "ideas": items,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_progress_dashboard() -> ProgressDashboard:
    from app.services.idea_service import _read_ideas  # noqa: F401
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
