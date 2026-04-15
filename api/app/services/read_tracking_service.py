"""Read tracking service — records asset reads as daily aggregated counters.

Every GET of a concept or asset increments a daily counter. No per-read rows
(storage efficient). HyperLogLog-style unique counting not needed at this
stage — simple counters with concept breakdown.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Column, Date, Integer, Numeric, String, Text
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
# ORM Model
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_read(asset_id: str, concept_id: str | None = None) -> None:
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
    """Get read tracking table stats for monitoring."""
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
