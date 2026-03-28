"""Contributor growth service — computes streaks, levels, timeline, and milestones."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.models.contributor_growth import (
    ContributorGrowthSnapshot,
    Milestone,
    WeekBucket,
    compute_level,
)
from app.services.contribution_ledger_service import (
    ContributionLedgerRecord,
    _ensure_schema,
    _session,
)
from app.services import graph_service


_GRAPH_SCAN_LIMIT = 2000
_TIMELINE_WEEKS = 26  # 6 months of weekly buckets


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _week_monday(dt: datetime) -> datetime:
    """Return the Monday of the week containing dt (UTC midnight)."""
    dt_utc = dt.astimezone(timezone.utc)
    monday = dt_utc - timedelta(days=dt_utc.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _compute_streaks(sorted_mondays: list[datetime]) -> tuple[int, int]:
    """Return (current_streak_weeks, longest_streak_weeks) given sorted unique Mondays."""
    if not sorted_mondays:
        return 0, 0

    longest = 1
    current = 1
    week = timedelta(weeks=1)

    for i in range(1, len(sorted_mondays)):
        if sorted_mondays[i] - sorted_mondays[i - 1] == week:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    # Is the most recent week the current or previous week?
    now_monday = _week_monday(_utc_now())
    most_recent = sorted_mondays[-1]
    if most_recent >= now_monday - timedelta(weeks=1):
        final_current = current
    else:
        final_current = 0

    return final_current, longest


def _build_milestones(total: int, first_at: datetime | None, type_counts: dict[str, int]) -> list[Milestone]:
    milestones: list[Milestone] = []

    if total >= 1:
        milestones.append(Milestone(
            name="First Step",
            description="Made your first contribution.",
            reached_at=first_at,
            contribution_count=1,
        ))
    if total >= 5:
        milestones.append(Milestone(
            name="Getting Going",
            description="Five contributions recorded.",
            contribution_count=5,
        ))
    if total >= 10:
        milestones.append(Milestone(
            name="Double Digits",
            description="Ten contributions — a real pattern forming.",
            contribution_count=10,
        ))
    if total >= 25:
        milestones.append(Milestone(
            name="Quarter Century",
            description="Twenty-five contributions.",
            contribution_count=25,
        ))
    if total >= 50:
        milestones.append(Milestone(
            name="Half Hundred",
            description="Fifty contributions — sustained commitment.",
            contribution_count=50,
        ))
    if total >= 100:
        milestones.append(Milestone(
            name="Century",
            description="One hundred contributions. Remarkable.",
            contribution_count=100,
        ))

    # Type-specific milestones
    if type_counts.get("question", 0) >= 5:
        milestones.append(Milestone(
            name="Curious Mind",
            description="Asked five or more questions that shaped the system.",
            contribution_count=type_counts["question"],
        ))
    if type_counts.get("review", 0) >= 3:
        milestones.append(Milestone(
            name="Thoughtful Reviewer",
            description="Reviewed three or more contributions.",
            contribution_count=type_counts["review"],
        ))
    if type_counts.get("code", 0) >= 5:
        milestones.append(Milestone(
            name="Builder",
            description="Five or more code contributions.",
            contribution_count=type_counts["code"],
        ))
    if type_counts.get("spec", 0) >= 3:
        milestones.append(Milestone(
            name="Architect",
            description="Authored three or more specs.",
            contribution_count=type_counts["spec"],
        ))
    if type_counts.get("share", 0) >= 3:
        milestones.append(Milestone(
            name="Amplifier",
            description="Shared the network three or more times.",
            contribution_count=type_counts["share"],
        ))
    if type_counts.get("mentoring", 0) >= 2:
        milestones.append(Milestone(
            name="Guide",
            description="Mentored others at least twice.",
            contribution_count=type_counts["mentoring"],
        ))

    # Breadth milestone — contributed in 5+ types
    if len(type_counts) >= 5:
        milestones.append(Milestone(
            name="Polymath",
            description=f"Contributed in {len(type_counts)} different ways.",
            contribution_count=total,
        ))

    return milestones


def _resolve_display_name(contributor_id: str) -> str:
    """Try to resolve a human-readable name from the graph."""
    try:
        node = graph_service.get_node(f"contributor:{contributor_id}")
        if node and node.get("name"):
            return str(node["name"])
        result = graph_service.list_nodes(type="contributor", limit=_GRAPH_SCAN_LIMIT)
        for n in result.get("items", []):
            if (
                n.get("legacy_id") == contributor_id
                or n.get("id") == contributor_id
                or n.get("name") == contributor_id
            ):
                return str(n.get("name", contributor_id))
    except Exception:
        pass
    return contributor_id


def get_contributor_growth(contributor_id: str) -> ContributorGrowthSnapshot | None:
    """Compute full growth snapshot from the contribution ledger."""
    _ensure_schema()

    with _session() as s:
        records = (
            s.query(ContributionLedgerRecord)
            .filter_by(contributor_id=contributor_id)
            .order_by(ContributionLedgerRecord.recorded_at.asc())
            .all()
        )

    if not records:
        return None

    now = _utc_now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)

    total_cc = 0.0
    type_counts: dict[str, int] = {}
    contributions_last_30d = 0
    contributions_prev_30d = 0
    week_buckets: dict[str, dict] = {}
    first_at: datetime | None = None
    last_at: datetime | None = None
    active_mondays: list[datetime] = []

    for rec in records:
        ts = _to_utc(rec.recorded_at)

        total_cc += float(rec.amount_cc or 0)
        ctype = rec.contribution_type or "other"
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

        if ts:
            if first_at is None:
                first_at = ts
            last_at = ts

            if ts >= cutoff_30d:
                contributions_last_30d += 1
            elif ts >= cutoff_60d:
                contributions_prev_30d += 1

            monday = _week_monday(ts)
            key = monday.strftime("%Y-%m-%d")
            if key not in week_buckets:
                week_buckets[key] = {
                    "week_start": key,
                    "count": 0,
                    "types": {},
                    "total_cc": 0.0,
                }
                active_mondays.append(monday)
            week_buckets[key]["count"] += 1
            week_buckets[key]["total_cc"] += float(rec.amount_cc or 0)
            week_buckets[key]["types"][ctype] = week_buckets[key]["types"].get(ctype, 0) + 1

    # Sort active Mondays for streak computation
    active_mondays_sorted = sorted(set(active_mondays))
    current_streak, longest_streak = _compute_streaks(active_mondays_sorted)

    # Build 26-week timeline (fill empty weeks with zero buckets)
    timeline: list[WeekBucket] = []
    for i in range(_TIMELINE_WEEKS - 1, -1, -1):
        monday = _week_monday(now) - timedelta(weeks=i)
        key = monday.strftime("%Y-%m-%d")
        if key in week_buckets:
            b = week_buckets[key]
            timeline.append(WeekBucket(
                week_start=b["week_start"],
                count=b["count"],
                types=b["types"],
                total_cc=round(b["total_cc"], 4),
            ))
        else:
            timeline.append(WeekBucket(week_start=key, count=0))

    total = len(records)
    level = compute_level(total)
    milestones = _build_milestones(total, first_at, type_counts)

    # Growth percentage
    growth_pct: float | None = None
    if contributions_prev_30d > 0:
        growth_pct = round((contributions_last_30d - contributions_prev_30d) / contributions_prev_30d * 100, 1)
    elif contributions_last_30d > 0:
        growth_pct = 100.0

    display_name = _resolve_display_name(contributor_id)

    return ContributorGrowthSnapshot(
        contributor_id=contributor_id,
        display_name=display_name,
        total_contributions=total,
        total_cc=round(total_cc, 4),
        contributions_by_type=type_counts,
        level=level,
        current_streak_weeks=current_streak,
        longest_streak_weeks=longest_streak,
        last_active_at=last_at,
        weekly_timeline=timeline,
        contributions_last_30d=contributions_last_30d,
        contributions_prev_30d=contributions_prev_30d,
        growth_pct=growth_pct,
        milestones=milestones,
    )


def get_community_feed(limit: int = 50, offset: int = 0) -> dict:
    """Return recent contributions from all contributors for the community feed."""
    _ensure_schema()

    with _session() as s:
        total = s.query(ContributionLedgerRecord).count()
        records = (
            s.query(ContributionLedgerRecord)
            .order_by(ContributionLedgerRecord.recorded_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    items = []
    for rec in records:
        meta: dict = {}
        if rec.metadata_json:
            try:
                meta = json.loads(rec.metadata_json)
            except Exception:
                pass
        display_name = _resolve_display_name(rec.contributor_id)
        items.append({
            "id": rec.id,
            "contributor_id": rec.contributor_id,
            "display_name": display_name,
            "type": rec.contribution_type,
            "amount_cc": rec.amount_cc,
            "idea_id": rec.idea_id,
            "recorded_at": rec.recorded_at.isoformat() if rec.recorded_at else None,
            "metadata": meta,
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
