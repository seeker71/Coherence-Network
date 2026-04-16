"""Read sensing service — records asset reads as daily aggregated counters
and per-contributor view events.

Every GET of a concept or asset increments a daily counter. Per-contributor
view events are stored in asset_view_events for CC reward sensing,
discovery chain tracking, and trending analytics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import mapped_column

log = logging.getLogger(__name__)

_ready = False


def _ensure_ready() -> None:
    global _ready
    if _ready:
        return
    _ready = True
    from app.services.unified_db import ensure_schema
    ensure_schema()


def _session():
    from app.services.unified_db import session
    return session()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

from app.services.unified_db import Base


class AssetReadDaily(Base):
    """Daily read counter per asset. One row per asset per day."""
    __tablename__ = "asset_reads_daily"

    asset_id = mapped_column(String(128), primary_key=True)
    day = mapped_column(Date, primary_key=True)
    read_count = mapped_column(Integer, default=0)
    cc_distributed = mapped_column(Numeric(18, 8), default=0)
    concepts = mapped_column(Text, default="{}")  # JSON string: {concept_id: count}

    def to_dict(self) -> dict[str, Any]:
        import json
        return {
            "asset_id": self.asset_id,
            "day": self.day.isoformat() if self.day else None,
            "read_count": self.read_count,
            "cc_distributed": float(self.cc_distributed or 0),
            "concepts": json.loads(self.concepts) if self.concepts else {},
        }


class AssetViewEvent(Base):
    """Per-contributor view event for CC reward sensing and discovery chains."""
    __tablename__ = "asset_view_events"

    id = mapped_column(String(64), primary_key=True)
    asset_id = mapped_column(String(128), nullable=False, index=True)
    concept_id = mapped_column(String(128), nullable=True)
    contributor_id = mapped_column(String(128), nullable=True, index=True)  # null = anonymous
    session_fingerprint = mapped_column(String(64), nullable=True)  # for anonymous dedup
    source_page = mapped_column(String(256), nullable=True)  # the page route
    referrer_contributor_id = mapped_column(String(128), nullable=True)  # who brought them
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Public API — daily aggregated reads
# ---------------------------------------------------------------------------

def record_read(
    asset_id: str,
    concept_id: str | None = None,
    contributor_id: str | None = None,
) -> None:
    """Increment today's read counter for an asset. Non-blocking."""
    import json
    _ensure_ready()
    today = date.today()

    try:
        with _session() as s:
            row = s.query(AssetReadDaily).filter_by(asset_id=asset_id, day=today).first()
            if row:
                row.read_count = (row.read_count or 0) + 1
                if concept_id:
                    concepts = json.loads(row.concepts or "{}")
                    concepts[concept_id] = concepts.get(concept_id, 0) + 1
                    row.concepts = json.dumps(concepts)
            else:
                concepts = {concept_id: 1} if concept_id else {}
                s.add(AssetReadDaily(
                    asset_id=asset_id,
                    day=today,
                    read_count=1,
                    cc_distributed=0,
                    concepts=json.dumps(concepts),
                ))
            s.commit()
    except Exception as e:
        log.warning("read_tracking: failed to record read for %s: %s", asset_id, e)


# ---------------------------------------------------------------------------
# Public API — per-contributor view events
# ---------------------------------------------------------------------------

def record_view(
    asset_id: str,
    concept_id: str | None = None,
    contributor_id: str | None = None,
    session_fingerprint: str | None = None,
    source_page: str | None = None,
    referrer_contributor_id: str | None = None,
) -> str | None:
    """Record a single view event. Returns the event ID, or None on failure."""
    _ensure_ready()
    event_id = str(uuid4())
    try:
        with _session() as s:
            s.add(AssetViewEvent(
                id=event_id,
                asset_id=asset_id,
                concept_id=concept_id,
                contributor_id=contributor_id,
                session_fingerprint=session_fingerprint,
                source_page=source_page,
                referrer_contributor_id=referrer_contributor_id,
            ))
            s.commit()
        return event_id
    except Exception as e:
        log.warning("read_tracking: failed to record view for %s: %s", asset_id, e)
        return None


def get_asset_view_stats(asset_id: str, days: int = 30) -> dict[str, Any]:
    """View stats for an asset: totals, uniques, daily breakdown, top referrers."""
    _ensure_ready()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with _session() as s:
        base = s.query(AssetViewEvent).filter(
            AssetViewEvent.asset_id == asset_id,
            AssetViewEvent.created_at >= since,
        )

        total_views = base.count()

        unique_contributors = (
            s.query(func.count(func.distinct(AssetViewEvent.contributor_id)))
            .filter(
                AssetViewEvent.asset_id == asset_id,
                AssetViewEvent.created_at >= since,
                AssetViewEvent.contributor_id.isnot(None),
            )
            .scalar()
        ) or 0

        anonymous_views = (
            s.query(func.count(AssetViewEvent.id))
            .filter(
                AssetViewEvent.asset_id == asset_id,
                AssetViewEvent.created_at >= since,
                AssetViewEvent.contributor_id.is_(None),
            )
            .scalar()
        ) or 0

        # Daily breakdown
        rows = base.all()
        daily: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.created_at:
                day_key = row.created_at.strftime("%Y-%m-%d")
                daily[day_key] += 1

        # Top referrers
        referrer_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.referrer_contributor_id:
                referrer_counts[row.referrer_contributor_id] += 1
        top_referrers = sorted(
            [{"contributor_id": k, "referral_count": v} for k, v in referrer_counts.items()],
            key=lambda x: x["referral_count"],
            reverse=True,
        )[:10]

    return {
        "asset_id": asset_id,
        "days": days,
        "total_views": total_views,
        "unique_contributors": unique_contributors,
        "anonymous_views": anonymous_views,
        "daily_breakdown": dict(sorted(daily.items())),
        "top_referrers": top_referrers,
    }


def get_contributor_view_history(
    contributor_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """What a contributor has viewed, most recent first."""
    _ensure_ready()
    with _session() as s:
        rows = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.contributor_id == contributor_id)
            .order_by(AssetViewEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "asset_id": r.asset_id,
                "concept_id": r.concept_id,
                "source_page": r.source_page,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def get_trending(limit: int = 20, days: int = 7) -> list[dict[str, Any]]:
    """Assets ranked by view velocity (views per day over the period)."""
    _ensure_ready()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with _session() as s:
        results = (
            s.query(
                AssetViewEvent.asset_id,
                func.count(AssetViewEvent.id).label("view_count"),
                func.count(func.distinct(AssetViewEvent.contributor_id)).label("unique_viewers"),
            )
            .filter(AssetViewEvent.created_at >= since)
            .group_by(AssetViewEvent.asset_id)
            .order_by(func.count(AssetViewEvent.id).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "asset_id": row.asset_id,
                "view_count": row.view_count,
                "unique_viewers": row.unique_viewers,
                "velocity": round(row.view_count / max(days, 1), 2),
                "days": days,
            }
            for row in results
        ]


def get_discovery_chain(asset_id: str) -> list[dict[str, Any]]:
    """Referrer chain for an asset — who brought whom."""
    _ensure_ready()
    with _session() as s:
        rows = (
            s.query(AssetViewEvent)
            .filter(
                AssetViewEvent.asset_id == asset_id,
                AssetViewEvent.referrer_contributor_id.isnot(None),
            )
            .order_by(AssetViewEvent.created_at.asc())
            .all()
        )

        chain = []
        seen_pairs: set[tuple[str, str]] = set()
        for r in rows:
            pair = (r.referrer_contributor_id or "", r.contributor_id or "anonymous")
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                chain.append({
                    "referrer": r.referrer_contributor_id,
                    "viewer": r.contributor_id or "anonymous",
                    "first_seen": r.created_at.isoformat() if r.created_at else None,
                })

        return chain


def get_daily_reads(asset_id: str, day: date) -> dict[str, Any] | None:
    """Get daily read data for an asset."""
    _ensure_ready()
    with _session() as s:
        row = s.query(AssetReadDaily).filter_by(asset_id=asset_id, day=day).first()
        return row.to_dict() if row else None


def get_reads_range(asset_id: str, from_date: date, to_date: date) -> list[dict[str, Any]]:
    """Get read data for a date range."""
    _ensure_ready()
    with _session() as s:
        rows = (
            s.query(AssetReadDaily)
            .filter(AssetReadDaily.asset_id == asset_id)
            .filter(AssetReadDaily.day >= from_date)
            .filter(AssetReadDaily.day <= to_date)
            .order_by(AssetReadDaily.day)
            .all()
        )
        return [r.to_dict() for r in rows]


def get_all_reads_for_date(day: date) -> list[dict[str, Any]]:
    """Get all asset reads for a specific date (for daily hash computation)."""
    _ensure_ready()
    with _session() as s:
        rows = s.query(AssetReadDaily).filter_by(day=day).all()
        return [r.to_dict() for r in rows]


# ---------------------------------------------------------------------------
# Disk growth management
# ---------------------------------------------------------------------------

# Maximum rows before archival triggers (each row ~250 bytes → 100K rows ≈ 25MB)
MAX_ROWS_BEFORE_ARCHIVE = 100_000
# Keep this many days of data locally (older gets archived)
RETENTION_DAYS = 90


def get_table_stats() -> dict[str, Any]:
    """Get read sensing table stats for monitoring."""
    _ensure_ready()
    with _session() as s:
        total_rows = s.query(AssetReadDaily).count()
        from sqlalchemy import func
        oldest = s.query(func.min(AssetReadDaily.day)).scalar()
        newest = s.query(func.max(AssetReadDaily.day)).scalar()
        total_reads = s.query(func.sum(AssetReadDaily.read_count)).scalar() or 0
        est_size_bytes = total_rows * 250  # ~250 bytes per row
    return {
        "total_rows": total_rows,
        "oldest_date": oldest.isoformat() if oldest else None,
        "newest_date": newest.isoformat() if newest else None,
        "total_reads": total_reads,
        "estimated_size_mb": round(est_size_bytes / (1024 * 1024), 2),
        "archive_threshold_rows": MAX_ROWS_BEFORE_ARCHIVE,
        "retention_days": RETENTION_DAYS,
        "needs_archive": total_rows > MAX_ROWS_BEFORE_ARCHIVE,
    }


def archive_old_reads(before_date: date | None = None) -> dict[str, Any]:
    """Archive reads older than retention period. Returns archived data as JSON
    for upload to archive.org or Arweave.

    Does NOT delete until the archive is confirmed uploaded.
    """
    import json
    _ensure_ready()
    if before_date is None:
        before_date = date.today() - __import__("datetime").timedelta(days=RETENTION_DAYS)

    with _session() as s:
        old_rows = (
            s.query(AssetReadDaily)
            .filter(AssetReadDaily.day < before_date)
            .order_by(AssetReadDaily.day)
            .all()
        )
        if not old_rows:
            return {"archived": 0, "message": "nothing to archive"}

        archive_data = {
            "type": "read_tracking_archive",
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": old_rows[0].day.isoformat(),
                "to": old_rows[-1].day.isoformat(),
            },
            "row_count": len(old_rows),
            "data": [r.to_dict() for r in old_rows],
        }

        return {
            "archived": len(old_rows),
            "period": archive_data["period"],
            "archive_json": json.dumps(archive_data),
            "message": f"Call delete_archived_reads(before_date) after confirming upload",
        }


def delete_archived_reads(before_date: date) -> int:
    """Delete reads older than the given date. Only call after confirming archive upload."""
    _ensure_ready()
    with _session() as s:
        count = s.query(AssetReadDaily).filter(AssetReadDaily.day < before_date).delete()
        s.commit()
    log.info("read_tracking: deleted %d archived rows before %s", count, before_date)
    return count
