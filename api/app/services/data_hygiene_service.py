"""Data hygiene monitoring — row counts, growth rates, anomaly detection.

Provides:
- get_table_row_counts()  — current row count for each tracked table
- get_growth_summary()    — per-table growth rate since a baseline snapshot
- detect_growth_anomalies() — flag tables growing faster than expected
- get_health_dashboard()  — human-readable health overview
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import inspect, text

from app.services import unified_db as _udb

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected daily growth rates (rows/day) per table. Tables that exceed
# ANOMALY_MULTIPLIER × their expected rate trigger an alert.
# ---------------------------------------------------------------------------

EXPECTED_DAILY_GROWTH: dict[str, float] = {
    "runtime_events": 2000.0,       # API calls throughout the day
    "telemetry_snapshots": 200.0,   # periodic snapshots
    "agent_tasks": 100.0,           # tasks created per day
    "telemetry_task_metrics": 120.0,
    "measurements": 50.0,
    "contribution_ledger": 30.0,
    # Low-churn tables
    "contributors": 5.0,
    "graph_nodes": 20.0,
    "graph_edges": 30.0,
    "ideas": 20.0,
}

# A table is "suspicious" when its row count is more than this multiple
# of the expected baseline for a young system (system age: days since epoch).
ANOMALY_MULTIPLIER: float = 3.0

# Maximum ratio rows-per-day that triggers an alert even without a baseline
MAX_ROWS_PER_DAY_RATIO: float = 5.0


@dataclass
class TableStats:
    """Row-count statistics for a single table."""

    table: str
    row_count: int
    expected_daily_growth: float
    snapshot_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_high_volume(self) -> bool:
        return self.row_count > 10_000

    def growth_anomaly_score(self, system_age_days: float) -> float:
        """Score 0–∞.  >1.0 means growth is faster than ANOMALY_MULTIPLIER × expected."""
        if system_age_days <= 0 or self.expected_daily_growth <= 0:
            return 0.0
        expected_total = self.expected_daily_growth * system_age_days * ANOMALY_MULTIPLIER
        return self.row_count / max(expected_total, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "row_count": self.row_count,
            "expected_daily_growth": self.expected_daily_growth,
            "is_high_volume": self.is_high_volume,
            "snapshot_at": self.snapshot_at.isoformat(),
        }


@dataclass
class GrowthAnomaly:
    """An anomalous growth event for a single table."""

    table: str
    row_count: int
    expected_max: float
    anomaly_score: float
    severity: str  # "warning" | "critical"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "row_count": self.row_count,
            "expected_max": round(self.expected_max, 1),
            "anomaly_score": round(self.anomaly_score, 3),
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class HealthDashboard:
    """Aggregate view of database hygiene health."""

    generated_at: datetime
    system_age_days: float
    tables: list[TableStats]
    anomalies: list[GrowthAnomaly]
    total_rows: int
    health_score: float  # 0.0–1.0

    @property
    def status(self) -> str:
        if not self.anomalies:
            return "healthy"
        critical = [a for a in self.anomalies if a.severity == "critical"]
        return "critical" if critical else "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "system_age_days": round(self.system_age_days, 2),
            "status": self.status,
            "health_score": round(self.health_score, 4),
            "total_rows": self.total_rows,
            "anomaly_count": len(self.anomalies),
            "anomalies": [a.to_dict() for a in self.anomalies],
            "tables": [t.to_dict() for t in self.tables],
        }


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _db_tables() -> list[str]:
    """Return all table names currently registered in the unified DB."""
    engine = _udb.engine()
    inspector = inspect(engine)
    return inspector.get_table_names()


def _count_table(table_name: str) -> int:
    """Return row count for a named table, 0 if table does not exist."""
    try:
        with _udb.session() as s:
            result = s.execute(text(f"SELECT COUNT(*) FROM {table_name}"))  # noqa: S608
            return int(result.scalar() or 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_table_row_counts(tables: list[str] | None = None) -> dict[str, int]:
    """Return {table_name: row_count} for the specified or all tracked tables.

    Args:
        tables: list of table names to query; defaults to EXPECTED_DAILY_GROWTH keys
                plus any additional tables found in the schema.
    """
    _udb.ensure_schema()
    target = tables if tables is not None else list(EXPECTED_DAILY_GROWTH.keys())
    existing = set(_db_tables())
    result: dict[str, int] = {}
    for t in target:
        if t in existing:
            result[t] = _count_table(t)
        else:
            result[t] = 0
    return result


def get_table_stats(system_age_days: float = 7.0) -> list[TableStats]:
    """Return TableStats for all tracked tables."""
    counts = get_table_row_counts()
    now = datetime.now(timezone.utc)
    stats: list[TableStats] = []
    for table, count in counts.items():
        stats.append(
            TableStats(
                table=table,
                row_count=count,
                expected_daily_growth=EXPECTED_DAILY_GROWTH.get(table, 10.0),
                snapshot_at=now,
            )
        )
    return stats


def detect_growth_anomalies(
    system_age_days: float = 7.0,
    multiplier: float = ANOMALY_MULTIPLIER,
) -> list[GrowthAnomaly]:
    """Return anomalies for tables whose row counts exceed expected bounds.

    Args:
        system_age_days: age of the system in days (used to compute expected totals)
        multiplier: factor above expected that triggers a warning/critical alert
    """
    stats = get_table_stats(system_age_days)
    anomalies: list[GrowthAnomaly] = []

    for s in stats:
        score = s.growth_anomaly_score(system_age_days)
        if score <= 1.0:
            continue

        expected_max = s.expected_daily_growth * system_age_days * multiplier
        severity = "critical" if score >= 2.0 else "warning"
        message = (
            f"Table '{s.table}' has {s.row_count:,} rows — "
            f"{score:.1f}× the expected maximum ({expected_max:,.0f}) "
            f"for a {system_age_days:.1f}-day-old system."
        )
        anomalies.append(
            GrowthAnomaly(
                table=s.table,
                row_count=s.row_count,
                expected_max=expected_max,
                anomaly_score=score,
                severity=severity,
                message=message,
            )
        )

    # Sort most-anomalous first
    anomalies.sort(key=lambda a: a.anomaly_score, reverse=True)
    return anomalies


def get_health_dashboard(system_age_days: float = 7.0) -> HealthDashboard:
    """Return a full health dashboard covering all tracked tables.

    health_score: 1.0 = no anomalies, degrades proportionally with each anomaly
    """
    stats = get_table_stats(system_age_days)
    anomalies = detect_growth_anomalies(system_age_days)
    total_rows = sum(s.row_count for s in stats)

    # health_score: 1.0 when clean, -0.2 per warning, -0.4 per critical (floor 0)
    penalty = sum(0.4 if a.severity == "critical" else 0.2 for a in anomalies)
    health_score = max(0.0, 1.0 - penalty)

    return HealthDashboard(
        generated_at=datetime.now(timezone.utc),
        system_age_days=system_age_days,
        tables=stats,
        anomalies=anomalies,
        total_rows=total_rows,
        health_score=health_score,
    )


def format_db_status_report(system_age_days: float = 7.0) -> str:
    """Return a human-readable db-status report (for cc db-status equivalent)."""
    dashboard = get_health_dashboard(system_age_days)
    lines: list[str] = [
        f"=== DB Status Report ({dashboard.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}) ===",
        f"System age: {dashboard.system_age_days:.1f} days | "
        f"Status: {dashboard.status.upper()} | "
        f"Health: {dashboard.health_score:.0%}",
        f"Total rows across {len(dashboard.tables)} tables: {dashboard.total_rows:,}",
        "",
        f"{'Table':<45} {'Rows':>10} {'Expected/day':>15} {'Anomaly':>10}",
        "-" * 85,
    ]

    anomaly_map = {a.table: a for a in dashboard.anomalies}
    for s in sorted(dashboard.tables, key=lambda x: x.row_count, reverse=True):
        anomaly = anomaly_map.get(s.table)
        flag = f"[{anomaly.severity.upper()}]" if anomaly else ""
        lines.append(
            f"{s.table:<45} {s.row_count:>10,} {s.expected_daily_growth:>15.0f} {flag:>10}"
        )

    if dashboard.anomalies:
        lines += ["", "=== GROWTH ANOMALIES ==="]
        for a in dashboard.anomalies:
            lines.append(f"  [{a.severity.upper()}] {a.message}")

    return "\n".join(lines)
