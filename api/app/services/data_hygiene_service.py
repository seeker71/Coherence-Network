"""Data hygiene service — monitors row counts, detects noise, alerts on growth anomalies.

Tracks per-table row counts over time and surfaces suspicious growth rates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.services import unified_db

logger = logging.getLogger(__name__)

# Tables to monitor and their expected max daily growth rates (rows/day)
# None means no cap — just track.
MONITORED_TABLES: dict[str, int | None] = {
    "runtime_events": 5_000,       # 46k already suspicious for young system
    "telemetry_snapshots": 500,
    "agent_tasks": 200,
    "telemetry_task_metrics": 500,
    "measurements": 100,
    "contribution_ledger": 50,
    "contributions": 200,
    "contributors": 20,
    "ideas": 50,
    "assets": 50,
}

# Alert thresholds
GROWTH_ALERT_MULTIPLIER = 2.0    # flag if growth > 2x expected
ABSOLUTE_NOISE_THRESHOLD = 10_000  # flag any table with > 10k rows under 7 days old


@dataclass
class TableStatus:
    table: str
    row_count: int
    exists: bool = True
    error: str | None = None
    expected_max_daily: int | None = None
    alert: bool = False
    alert_reason: str | None = None


@dataclass
class DbStatusReport:
    generated_at: str
    tables: list[TableStatus]
    total_rows: int
    alert_count: int
    alerts: list[dict[str, Any]]


def _count_rows(sess, table: str) -> tuple[int | None, str | None]:
    """Return (count, error_string)."""
    try:
        result = sess.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
        return result.scalar() or 0, None
    except Exception as exc:
        return None, str(exc)


def get_db_status() -> DbStatusReport:
    """Return row counts for all monitored tables with growth alerts."""
    now = datetime.now(timezone.utc)
    statuses: list[TableStatus] = []
    alerts: list[dict[str, Any]] = []

    try:
        with unified_db.session() as sess:
            for table, max_daily in MONITORED_TABLES.items():
                count, err = _count_rows(sess, table)
                if err is not None:
                    st = TableStatus(
                        table=table,
                        row_count=0,
                        exists=False,
                        error=err,
                        expected_max_daily=max_daily,
                    )
                    statuses.append(st)
                    continue

                alert = False
                alert_reason = None

                # Absolute noise check: flag large tables
                if count is not None and count > ABSOLUTE_NOISE_THRESHOLD:
                    alert = True
                    alert_reason = (
                        f"Row count {count:,} exceeds noise threshold "
                        f"{ABSOLUTE_NOISE_THRESHOLD:,} — investigate data accumulation"
                    )

                st = TableStatus(
                    table=table,
                    row_count=count or 0,
                    exists=True,
                    expected_max_daily=max_daily,
                    alert=alert,
                    alert_reason=alert_reason,
                )
                statuses.append(st)

                if alert:
                    alerts.append({
                        "table": table,
                        "row_count": count,
                        "reason": alert_reason,
                        "severity": "warning",
                    })

    except Exception as exc:
        logger.error("data_hygiene: failed to query DB: %s", exc)

    total = sum(s.row_count for s in statuses if s.exists)
    return DbStatusReport(
        generated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        tables=statuses,
        total_rows=total,
        alert_count=len(alerts),
        alerts=alerts,
    )


def get_runtime_events_investigation() -> dict[str, Any]:
    """Deep-dive on runtime_events noise — breakdown by type and age."""
    result: dict[str, Any] = {
        "table": "runtime_events",
        "investigation": {},
    }
    try:
        with unified_db.session() as sess:
            # Total count
            total = sess.execute(text("SELECT COUNT(*) FROM runtime_events")).scalar() or 0
            result["row_count"] = total

            # Try breakdown by event_type (column may vary)
            try:
                rows = sess.execute(
                    text(
                        "SELECT event_type, COUNT(*) AS cnt "
                        "FROM runtime_events "
                        "GROUP BY event_type "
                        "ORDER BY cnt DESC "
                        "LIMIT 20"
                    )
                ).fetchall()
                result["investigation"]["by_event_type"] = [
                    {"event_type": r[0], "count": r[1]} for r in rows
                ]
            except Exception:
                result["investigation"]["by_event_type"] = "column unavailable"

            # Try breakdown by age buckets
            try:
                age_rows = sess.execute(
                    text(
                        "SELECT "
                        "  CASE "
                        "    WHEN created_at >= datetime('now', '-1 day') THEN 'last_24h' "
                        "    WHEN created_at >= datetime('now', '-7 days') THEN 'last_7d' "
                        "    WHEN created_at >= datetime('now', '-30 days') THEN 'last_30d' "
                        "    ELSE 'older' "
                        "  END AS bucket, "
                        "  COUNT(*) AS cnt "
                        "FROM runtime_events "
                        "GROUP BY bucket"
                    )
                ).fetchall()
                result["investigation"]["by_age"] = {
                    r[0]: r[1] for r in age_rows
                }
            except Exception:
                # PostgreSQL syntax
                try:
                    age_rows = sess.execute(
                        text(
                            "SELECT "
                            "  CASE "
                            "    WHEN created_at >= NOW() - INTERVAL '1 day' THEN 'last_24h' "
                            "    WHEN created_at >= NOW() - INTERVAL '7 days' THEN 'last_7d' "
                            "    WHEN created_at >= NOW() - INTERVAL '30 days' THEN 'last_30d' "
                            "    ELSE 'older' "
                            "  END AS bucket, "
                            "  COUNT(*) AS cnt "
                            "FROM runtime_events "
                            "GROUP BY bucket"
                        )
                    ).fetchall()
                    result["investigation"]["by_age"] = {
                        r[0]: r[1] for r in age_rows
                    }
                except Exception as exc2:
                    result["investigation"]["by_age"] = f"unavailable: {exc2}"

    except Exception as exc:
        result["error"] = str(exc)

    return result
