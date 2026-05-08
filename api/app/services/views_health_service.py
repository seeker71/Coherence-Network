"""Views-tracing health service.

The /api/views/ping path writes one row to ``asset_view_events`` and
upserts one row to ``asset_reads_daily`` on every visit. The events
table grows linearly with traffic; the daily table is bounded by
(assets × days).

This service is the body's proprioception of that growth — it answers
three questions a maintainer needs to ask before tracing becomes a
bottleneck:

  1. **How loud is the writer?** Latency per ping (p50 / p95 / p99
     observed in a sliding in-memory ring). If the ring shows the
     writer crossing budget, the synchronous path needs to move
     async or batch.
  2. **How fast is the table growing?** Events in the last hour /
     day / 7d / 30d, plus oldest-event-age. If growth crosses
     budget the trim script can roll old events into the daily
     aggregate and delete them.
  3. **How heavy is what we already hold?** Row count and approximate
     bytes (per-row size estimated from the schema). Low-precision
     but trends accurately.

Thresholds are deliberately conservative defaults — the body should
notice early, not at the edge of pain. Override via env or future
config.

Surface: ``GET /api/views/health`` returns this same dict; the
wellness check + maintainer dashboards read it.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque

from sqlalchemy import func

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process latency ring — last N ping durations in milliseconds.
# Bounded memory (deque maxlen). Reset on process restart, by design —
# what we care about is the rolling shape, not durable history.
# ---------------------------------------------------------------------------

_PING_LATENCY_RING_SIZE = 1024
_ping_latencies_ms: Deque[float] = deque(maxlen=_PING_LATENCY_RING_SIZE)


def record_ping_latency(duration_ms: float) -> None:
    """Append a latency sample to the rolling window. Called from the
    /api/views/ping handler; the caller is responsible for measuring
    its own duration (so the timing is accurate to the work it's
    actually instrumenting)."""
    if duration_ms < 0:
        return
    _ping_latencies_ms.append(duration_ms)


def _percentiles(samples: list[float]) -> dict[str, float | None]:
    if not samples:
        return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None, "samples": 0}
    s = sorted(samples)
    n = len(s)

    def at(p: float) -> float:
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return s[idx]

    return {
        "p50_ms": round(at(0.50), 2),
        "p95_ms": round(at(0.95), 2),
        "p99_ms": round(at(0.99), 2),
        "max_ms": round(s[-1], 2),
        "samples": n,
    }


# ---------------------------------------------------------------------------
# Storage health — row counts, growth bands, oldest event age, size estimate.
# ---------------------------------------------------------------------------

# Per-row byte estimate. The actual row carries: id (64 char string),
# asset_id (128), concept_id (128 nullable), contributor_id (128 nullable),
# session_fingerprint (64), source_page (256), referrer_contributor_id
# (128), created_at (8). Average non-null fill ~60%; with index overhead
# ~1.5x, ~640 bytes is realistic. Easy to tune as data arrives.
_BYTES_PER_EVENT_ROW = 640


def _session():
    from app.services.unified_db import session
    return session()


def _ensure_ready() -> None:
    from app.services.unified_db import ensure_schema
    ensure_schema()


def _count_in_window(s, AssetViewEvent, since: datetime) -> int:
    return (
        s.query(func.count(AssetViewEvent.id))
        .filter(AssetViewEvent.created_at >= since)
        .scalar()
    ) or 0


def _classify_growth(events_per_day: float) -> str:
    """Wellness band for daily event volume. Small numbers stay calm."""
    if events_per_day < 1_000:
        return "calm"
    if events_per_day < 10_000:
        return "active"
    if events_per_day < 100_000:
        return "loud"
    return "trim-recommended"


def _classify_size(rows: int) -> str:
    """Wellness band for total row count."""
    if rows < 100_000:
        return "calm"
    if rows < 1_000_000:
        return "active"
    if rows < 10_000_000:
        return "loud"
    return "trim-recommended"


def _classify_latency(p95_ms: float | None) -> str:
    """Wellness band for ping p95."""
    if p95_ms is None:
        return "no-data"
    if p95_ms < 30:
        return "calm"
    if p95_ms < 100:
        return "active"
    if p95_ms < 300:
        return "loud"
    return "investigate"


def get_views_health() -> dict[str, Any]:
    """Snapshot of the tracing system's own vital signs.

    Cheap to call: ``count`` queries on indexed columns, no full scans.
    The latency window is in-memory.
    """
    _ensure_ready()
    from app.services.read_tracking_service import AssetViewEvent

    now = datetime.now(timezone.utc)
    one_hour = now - timedelta(hours=1)
    one_day = now - timedelta(days=1)
    seven_days = now - timedelta(days=7)
    thirty_days = now - timedelta(days=30)

    with _session() as s:
        total_rows = s.query(func.count(AssetViewEvent.id)).scalar() or 0

        events_last_hour = _count_in_window(s, AssetViewEvent, one_hour)
        events_last_day = _count_in_window(s, AssetViewEvent, one_day)
        events_last_7d = _count_in_window(s, AssetViewEvent, seven_days)
        events_last_30d = _count_in_window(s, AssetViewEvent, thirty_days)

        oldest = (
            s.query(func.min(AssetViewEvent.created_at)).scalar()
            if total_rows
            else None
        )
        newest = (
            s.query(func.max(AssetViewEvent.created_at)).scalar()
            if total_rows
            else None
        )

    # Coerce to UTC-aware for arithmetic. SQLite hands back naive datetimes.
    def _utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    oldest_utc = _utc(oldest)
    newest_utc = _utc(newest)
    oldest_age_days = (now - oldest_utc).days if oldest_utc else None

    # Daily growth rate, smoothed across 7d when available.
    if events_last_7d > 0:
        growth_per_day = events_last_7d / 7.0
    else:
        growth_per_day = float(events_last_day)

    estimated_bytes = total_rows * _BYTES_PER_EVENT_ROW
    estimated_mb = round(estimated_bytes / (1024 * 1024), 2)

    latency = _percentiles(list(_ping_latencies_ms))

    growth_band = _classify_growth(growth_per_day)
    size_band = _classify_size(total_rows)
    latency_band = _classify_latency(latency["p95_ms"])

    flags: list[str] = []
    if growth_band == "trim-recommended":
        flags.append("growth_high")
    if size_band == "trim-recommended":
        flags.append("size_high")
    if latency_band == "investigate":
        flags.append("latency_high")

    return {
        "as_of": now.isoformat(),
        "writer": {
            "ping_latency": latency,
            "band": latency_band,
        },
        "events": {
            "total_rows": total_rows,
            "last_hour": events_last_hour,
            "last_day": events_last_day,
            "last_7d": events_last_7d,
            "last_30d": events_last_30d,
            "growth_per_day": round(growth_per_day, 1),
            "growth_band": growth_band,
            "oldest_at": oldest_utc.isoformat() if oldest_utc else None,
            "newest_at": newest_utc.isoformat() if newest_utc else None,
            "oldest_age_days": oldest_age_days,
        },
        "storage": {
            "estimated_bytes": estimated_bytes,
            "estimated_mb": estimated_mb,
            "bytes_per_row_estimate": _BYTES_PER_EVENT_ROW,
            "size_band": size_band,
        },
        "flags": flags,
        "thresholds": {
            "growth_per_day": {
                "calm": "< 1k",
                "active": "1k–10k",
                "loud": "10k–100k",
                "trim-recommended": "> 100k",
            },
            "total_rows": {
                "calm": "< 100k",
                "active": "100k–1M",
                "loud": "1M–10M",
                "trim-recommended": "> 10M",
            },
            "p95_ms": {
                "calm": "< 30",
                "active": "30–100",
                "loud": "100–300",
                "investigate": "> 300",
            },
        },
        "guidance": _guidance(flags),
    }


def _guidance(flags: list[str]) -> str:
    if not flags:
        return (
            "All bands within budget. The tracing layer is breathing. "
            "Re-check with /api/views/health when traffic shape shifts."
        )
    actions: list[str] = []
    if "growth_high" in flags:
        actions.append(
            "growth: run scripts/trim_view_events.py --older-than 30 to "
            "roll old per-event rows into the daily aggregate."
        )
    if "size_high" in flags:
        actions.append(
            "size: same trim script with a smaller --older-than window, "
            "or enable anonymous-event sampling via --sample-anonymous 0.1."
        )
    if "latency_high" in flags:
        actions.append(
            "latency: move record_view to a background queue or batch "
            "writes. The current synchronous commit blocks the request."
        )
    return " · ".join(actions)
