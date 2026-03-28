"""Data hygiene: row counts, growth vs last sample, and anomaly alerts."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.services.unified_db import Base, session as db_session


class DataHygieneSampleRecord(Base):
    """Append-only samples for growth tracking (one row per table per capture)."""

    __tablename__ = "data_hygiene_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sql_table: Mapped[str] = mapped_column(String(128), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# (logical key, physical table name, operator note)
MONITORED: tuple[tuple[str, str, str], ...] = (
    ("runtime_events", "runtime_events", "Runtime API / tool telemetry"),
    ("telemetry_snapshots", "telemetry_automation_usage_snapshots", "Automation usage snapshots"),
    ("agent_tasks", "agent_tasks", "Agent orchestration tasks"),
    ("telemetry_task_metrics", "telemetry_task_metrics", "Per-task telemetry metrics"),
    ("measurements", "node_measurement_summaries", "Federation routing measurements"),
    ("contribution_ledger", "contribution_ledger", "Contribution ledger entries"),
)


def _float_env(name: str, default: str) -> float:
    raw = os.getenv(name, default).strip()
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _int_env(name: str, default: str) -> int:
    raw = os.getenv(name, default).strip()
    try:
        return int(raw)
    except ValueError:
        return int(default)


def count_rows_raw(sess, sql_table: str) -> int:
    """Return COUNT(*) for a table; 0 if the table is missing or query fails."""
    try:
        q = text(f'SELECT COUNT(*) AS c FROM "{sql_table}"')
        row = sess.execute(q).mappings().first()
        if row is None:
            return 0
        return int(row["c"])
    except Exception:
        try:
            q2 = text(f"SELECT COUNT(*) AS c FROM {sql_table}")
            row2 = sess.execute(q2).mappings().first()
            return int(row2["c"]) if row2 else 0
        except Exception:
            return 0


def _last_sample(sess, sql_table: str) -> DataHygieneSampleRecord | None:
    return sess.execute(
        select(DataHygieneSampleRecord)
        .where(DataHygieneSampleRecord.sql_table == sql_table)
        .order_by(DataHygieneSampleRecord.captured_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _alert_thresholds() -> dict[str, float | int]:
    return {
        "warn_pct": _float_env("DATA_HYGIENE_WARN_PCT", "25"),
        "warn_abs": _int_env("DATA_HYGIENE_WARN_ABS", "100"),
        "runtime_warn_pct": _float_env("DATA_HYGIENE_RUNTIME_WARN_PCT", "10"),
        "runtime_abs": _int_env("DATA_HYGIENE_RUNTIME_WARN_ABS", "200"),
        "critical_count": _int_env("DATA_HYGIENE_RUNTIME_CRITICAL_ROWS", "50000"),
    }


def build_alerts(
    table_key: str,
    *,
    count_now: int,
    prev: DataHygieneSampleRecord | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """Return alert dicts for one table based on growth vs last stored sample."""
    th = _alert_thresholds()
    out: list[dict[str, Any]] = []
    if prev is None:
        return out

    delta = count_now - int(prev.row_count)
    prev_at = prev.captured_at
    if prev_at.tzinfo is None:
        prev_at = prev_at.replace(tzinfo=timezone.utc)
    hours = max((now - prev_at).total_seconds() / 3600.0, 1e-9)
    pct = (delta / prev.row_count * 100.0) if prev.row_count > 0 else (100.0 if delta > 0 else 0.0)

    if table_key == "runtime_events" and count_now >= int(th["critical_count"]) and pct >= 5.0:
        out.append(
            {
                "severity": "critical",
                "table_key": table_key,
                "message": (
                    f"runtime_events row count {count_now} is very high "
                    f"({pct:.1f}% vs last sample, +{delta} rows)."
                ),
                "delta_rows": delta,
                "growth_pct_vs_previous": round(pct, 4),
            }
        )
        return out

    warn_pct = float(th["warn_pct"])
    warn_abs = int(th["warn_abs"])
    if table_key == "runtime_events":
        warn_pct = float(th["runtime_warn_pct"])
        warn_abs = int(th["runtime_abs"])

    if delta >= warn_abs and pct >= warn_pct:
        sev = "warning" if pct < 40.0 else "critical"
        out.append(
            {
                "severity": sev,
                "table_key": table_key,
                "message": (
                    f"{table_key} grew {pct:.1f}% since last sample (+{delta} rows, "
                    f"~{delta / hours:.1f} rows/h)."
                ),
                "delta_rows": delta,
                "growth_pct_vs_previous": round(pct, 4),
            }
        )
    return out


def build_status_payload(*, record_sample: bool) -> dict[str, Any]:
    """Compute row counts, optional new samples, growth, and alerts."""
    now = datetime.now(timezone.utc)
    tables_out: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    insufficient = True

    with db_session() as sess:
        sample_rows = sess.execute(
            select(func.count()).select_from(DataHygieneSampleRecord)
        ).scalar_one()
        sample_rows = int(sample_rows or 0)

        for key, sql_t, note in MONITORED:
            count_now = count_rows_raw(sess, sql_t)
            prev = _last_sample(sess, sql_t)
            if prev is not None:
                insufficient = False

            prev_count = int(prev.row_count) if prev else None
            prev_at = None
            delta_rows = None
            hours_elapsed = None
            growth_per_h = None
            pct_vs = None

            if prev is not None:
                p_at = prev.captured_at
                if p_at.tzinfo is None:
                    p_at = p_at.replace(tzinfo=timezone.utc)
                prev_at = p_at.isoformat()
                delta_rows = count_now - int(prev.row_count)
                hours_elapsed = max((now - p_at).total_seconds() / 3600.0, 1e-9)
                growth_per_h = round(delta_rows / hours_elapsed, 4)
                if prev.row_count > 0:
                    pct_vs = round(delta_rows / float(prev.row_count) * 100.0, 4)
                else:
                    pct_vs = 100.0 if count_now > 0 else 0.0

            alerts.extend(
                build_alerts(key, count_now=count_now, prev=prev, now=now),
            )

            row: dict[str, Any] = {
                "key": key,
                "sql_table": sql_t,
                "description": note,
                "row_count": count_now,
                "previous_count": prev_count,
                "previous_captured_at": prev_at,
                "delta_rows": delta_rows,
                "hours_since_previous": round(hours_elapsed, 6) if hours_elapsed is not None else None,
                "growth_rows_per_hour": growth_per_h,
                "growth_pct_vs_previous": pct_vs,
            }
            tables_out.append(row)

            if record_sample:
                sess.add(
                    DataHygieneSampleRecord(
                        table_key=key,
                        sql_table=sql_t,
                        row_count=count_now,
                        captured_at=now,
                    )
                )

    worst = "ok"
    for a in alerts:
        if a["severity"] == "critical":
            worst = "critical"
            break
        if a["severity"] == "warning":
            worst = "degraded"

    return {
        "captured_at": now.isoformat(),
        "tables": tables_out,
        "alerts": alerts,
        "meta": {
            "sample_history_rows": sample_rows + (len(MONITORED) if record_sample else 0),
            "insufficient_history": insufficient,
            "health": worst,
            "thresholds": {
                "warn_pct": _float_env("DATA_HYGIENE_WARN_PCT", "25"),
                "warn_abs": _int_env("DATA_HYGIENE_WARN_ABS", "100"),
                "runtime_warn_pct": _float_env("DATA_HYGIENE_RUNTIME_WARN_PCT", "10"),
                "runtime_warn_abs": _int_env("DATA_HYGIENE_RUNTIME_WARN_ABS", "200"),
            },
        },
    }
