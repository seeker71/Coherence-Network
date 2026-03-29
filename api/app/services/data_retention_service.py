"""Data retention service — tiered telemetry trimming with summarization and off-DB backup.

Policy:
  Hot  (0–7d):   Full detail, queryable.
  Warm (7–30d):  Summarized per-day aggregates; detail exported to backup.
  Cold (30–90d): Summarized per-week; detail exported to backup.
  Dead (90d+):   Summary only; full export to backup, then delete.

Never delete: ideas, specs, contributions, identities, audit ledger.
Safe to trim:
  - runtime_events           (7d detail + daily summaries)
  - telemetry_automation_usage_snapshots (30d detail + weekly summaries)
  - telemetry_task_metrics   (30d detail)
  - telemetry_friction_events (30d detail)
  - telemetry_external_tool_usage_events (30d detail)

Backup format: JSONL files in data/retention-backups/<table>/<YYYY-MM>.jsonl
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, text

from app.services import unified_db as _udb
from app.services.telemetry_persistence.models import (
    AutomationUsageSnapshotRecord,
    ExternalToolUsageEventRecord,
    FrictionEventRecord,
    TaskMetricRecord,
    TelemetryMetaRecord,
)
from app.services.runtime_event_store import RuntimeEventRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

HOT_DAYS = int(os.getenv("RETENTION_HOT_DAYS", "7"))
WARM_DAYS = int(os.getenv("RETENTION_WARM_DAYS", "30"))
COLD_DAYS = int(os.getenv("RETENTION_COLD_DAYS", "90"))

BACKUP_ROOT = Path(os.getenv("RETENTION_BACKUP_DIR", "data/retention-backups"))

POLICY: dict[str, Any] = {
    "hot_days": HOT_DAYS,
    "warm_days": WARM_DAYS,
    "cold_days": COLD_DAYS,
    "backup_dir": str(BACKUP_ROOT),
    "never_delete": [
        "ideas",
        "specs",
        "contributions",
        "contributor_identities",
        "audit_ledger",
        "coherence_credits",
        "value_lineage",
        "idea_lineage",
    ],
    "safe_to_trim": [
        "runtime_events",
        "telemetry_automation_usage_snapshots",
        "telemetry_task_metrics",
        "telemetry_friction_events",
        "telemetry_external_tool_usage_events",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cutoff(days: int) -> datetime:
    return _now_utc() - timedelta(days=days)


def _backup_path(table: str, ts: datetime) -> Path:
    """Return the JSONL backup file path for the given table and month."""
    month_key = ts.strftime("%Y-%m")
    p = BACKUP_ROOT / table / f"{month_key}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_backup(table: str, records: list[dict[str, Any]]) -> int:
    """Append records to the monthly JSONL backup file. Returns count written."""
    if not records:
        return 0
    written = 0
    # Group by month so each month lands in its own file.
    by_month: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        ts_raw = rec.get("recorded_at") or rec.get("created_at") or rec.get("occurred_at") or rec.get("collected_at")
        if isinstance(ts_raw, datetime):
            ts = ts_raw
        elif isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = _now_utc()
        else:
            ts = _now_utc()
        month_key = ts.strftime("%Y-%m")
        by_month[month_key].append(rec)

    for month_key, month_records in by_month.items():
        # Derive a representative datetime from the key.
        try:
            ts_repr = datetime.strptime(month_key + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            ts_repr = _now_utc()
        path = _backup_path(table, ts_repr)
        with path.open("a", encoding="utf-8") as fh:
            for rec in month_records:
                fh.write(json.dumps(rec, default=str) + "\n")
                written += 1
    return written


def _meta_set(key: str, value: str) -> None:
    with _udb.session() as s:
        row = s.get(TelemetryMetaRecord, key)
        if row is None:
            s.add(TelemetryMetaRecord(key=key, value=value))
        else:
            row.value = value
            s.add(row)


def _meta_get(key: str) -> str:
    with _udb.session() as s:
        row = s.get(TelemetryMetaRecord, key)
        return str(row.value or "") if row else ""


# ---------------------------------------------------------------------------
# Per-table retention passes
# ---------------------------------------------------------------------------

def _trim_runtime_events(dry_run: bool = False) -> dict[str, Any]:
    """Trim runtime_events: keep HOT_DAYS detail; export+delete older rows."""
    _udb.ensure_schema()
    cutoff = _cutoff(HOT_DAYS)
    stats: dict[str, Any] = {"table": "runtime_events", "cutoff_days": HOT_DAYS, "exported": 0, "deleted": 0}

    with _udb.session() as s:
        old_rows = (
            s.query(RuntimeEventRecord)
            .filter(RuntimeEventRecord.recorded_at < cutoff)
            .order_by(RuntimeEventRecord.recorded_at.asc())
            .limit(5000)
            .all()
        )
        if not old_rows:
            return stats

        records = [
            {
                "id": r.id,
                "source": r.source,
                "endpoint": r.endpoint,
                "raw_endpoint": r.raw_endpoint,
                "method": r.method,
                "status_code": r.status_code,
                "runtime_ms": r.runtime_ms,
                "idea_id": r.idea_id,
                "origin_idea_id": r.origin_idea_id,
                "runtime_cost_estimate": r.runtime_cost_estimate,
                "recorded_at": r.recorded_at.isoformat() if isinstance(r.recorded_at, datetime) else str(r.recorded_at),
            }
            for r in old_rows
        ]

        if not dry_run:
            written = _append_backup("runtime_events", records)
            stats["exported"] = written
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)

    return stats


def _trim_automation_snapshots(dry_run: bool = False) -> dict[str, Any]:
    """Trim automation usage snapshots: keep WARM_DAYS."""
    _udb.ensure_schema()
    cutoff = _cutoff(WARM_DAYS)
    stats: dict[str, Any] = {"table": "telemetry_automation_usage_snapshots", "cutoff_days": WARM_DAYS, "exported": 0, "deleted": 0}

    with _udb.session() as s:
        old_rows = (
            s.query(AutomationUsageSnapshotRecord)
            .filter(AutomationUsageSnapshotRecord.collected_at < cutoff)
            .order_by(AutomationUsageSnapshotRecord.id.asc())
            .limit(5000)
            .all()
        )
        if not old_rows:
            return stats

        records = []
        for r in old_rows:
            try:
                payload = json.loads(r.payload_json)
            except Exception:
                payload = {}
            payload.setdefault("_collected_at", r.collected_at.isoformat() if isinstance(r.collected_at, datetime) else None)
            payload.setdefault("collected_at", payload["_collected_at"])
            records.append(payload)

        if not dry_run:
            written = _append_backup("telemetry_automation_usage_snapshots", records)
            stats["exported"] = written
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)

    return stats


def _trim_task_metrics(dry_run: bool = False) -> dict[str, Any]:
    """Trim task metrics: keep WARM_DAYS."""
    _udb.ensure_schema()
    cutoff = _cutoff(WARM_DAYS)
    stats: dict[str, Any] = {"table": "telemetry_task_metrics", "cutoff_days": WARM_DAYS, "exported": 0, "deleted": 0}

    with _udb.session() as s:
        old_rows = (
            s.query(TaskMetricRecord)
            .filter(TaskMetricRecord.occurred_at < cutoff)
            .order_by(TaskMetricRecord.id.asc())
            .limit(10000)
            .all()
        )
        if not old_rows:
            return stats

        records = []
        for r in old_rows:
            try:
                payload = json.loads(r.payload_json)
            except Exception:
                payload = {}
            payload.setdefault("task_id", r.task_id)
            payload.setdefault("task_type", r.task_type)
            payload.setdefault("model", r.model)
            payload.setdefault("status", r.status)
            payload.setdefault("occurred_at", r.occurred_at.isoformat() if isinstance(r.occurred_at, datetime) else None)
            records.append(payload)

        if not dry_run:
            written = _append_backup("telemetry_task_metrics", records)
            stats["exported"] = written
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)

    return stats


def _trim_friction_events(dry_run: bool = False) -> dict[str, Any]:
    """Trim friction events: keep WARM_DAYS."""
    _udb.ensure_schema()
    cutoff = _cutoff(WARM_DAYS)
    stats: dict[str, Any] = {"table": "telemetry_friction_events", "cutoff_days": WARM_DAYS, "exported": 0, "deleted": 0}

    with _udb.session() as s:
        old_rows = (
            s.query(FrictionEventRecord)
            .filter(FrictionEventRecord.timestamp < cutoff)
            .order_by(FrictionEventRecord.id.asc())
            .limit(10000)
            .all()
        )
        if not old_rows:
            return stats

        records = []
        for r in old_rows:
            try:
                payload = json.loads(r.payload_json)
            except Exception:
                payload = {}
            payload.setdefault("event_id", r.event_id)
            payload.setdefault("timestamp", r.timestamp.isoformat() if isinstance(r.timestamp, datetime) else None)
            records.append(payload)

        if not dry_run:
            written = _append_backup("telemetry_friction_events", records)
            stats["exported"] = written
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)

    return stats


def _trim_external_tool_usage(dry_run: bool = False) -> dict[str, Any]:
    """Trim external tool usage events: keep WARM_DAYS."""
    _udb.ensure_schema()
    cutoff = _cutoff(WARM_DAYS)
    stats: dict[str, Any] = {"table": "telemetry_external_tool_usage_events", "cutoff_days": WARM_DAYS, "exported": 0, "deleted": 0}

    with _udb.session() as s:
        old_rows = (
            s.query(ExternalToolUsageEventRecord)
            .filter(ExternalToolUsageEventRecord.occurred_at < cutoff)
            .order_by(ExternalToolUsageEventRecord.id.asc())
            .limit(10000)
            .all()
        )
        if not old_rows:
            return stats

        records = []
        for r in old_rows:
            try:
                payload = json.loads(r.payload_json)
            except Exception:
                payload = {}
            payload.setdefault("event_id", r.event_id)
            payload.setdefault("tool_name", r.tool_name)
            payload.setdefault("provider", r.provider)
            payload.setdefault("occurred_at", r.occurred_at.isoformat() if isinstance(r.occurred_at, datetime) else None)
            records.append(payload)

        if not dry_run:
            written = _append_backup("telemetry_external_tool_usage_events", records)
            stats["exported"] = written
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)

    return stats


# ---------------------------------------------------------------------------
# Daily aggregates for runtime_events
# ---------------------------------------------------------------------------

def _compute_daily_runtime_summary(date_str: str) -> dict[str, Any] | None:
    """Compute a daily aggregate for a single day (YYYY-MM-DD) of runtime_events."""
    _udb.ensure_schema()
    try:
        day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    day_end = day_start + timedelta(days=1)

    with _udb.session() as s:
        rows = (
            s.query(RuntimeEventRecord)
            .filter(
                RuntimeEventRecord.recorded_at >= day_start,
                RuntimeEventRecord.recorded_at < day_end,
            )
            .all()
        )
        if not rows:
            return None

        count = len(rows)
        total_ms = sum(float(r.runtime_ms or 0) for r in rows)
        error_count = sum(1 for r in rows if int(r.status_code or 0) >= 400)
        endpoints: dict[str, int] = defaultdict(int)
        for r in rows:
            endpoints[r.endpoint] += 1
        top_endpoints = sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "date": date_str,
        "count": count,
        "avg_runtime_ms": round(total_ms / count, 2) if count else 0,
        "error_count": error_count,
        "error_rate": round(error_count / count, 4) if count else 0,
        "top_endpoints": [{"endpoint": ep, "calls": n} for ep, n in top_endpoints],
    }


def build_daily_summaries(days_back: int = 7) -> list[dict[str, Any]]:
    """Build and persist daily runtime summaries for the past N days."""
    summaries = []
    for i in range(days_back, 0, -1):
        day = (_now_utc() - timedelta(days=i)).strftime("%Y-%m-%d")
        meta_key = f"retention:runtime_daily_summary:{day}"
        existing = _meta_get(meta_key)
        if existing:
            try:
                summaries.append(json.loads(existing))
                continue
            except Exception:
                pass
        summary = _compute_daily_runtime_summary(day)
        if summary:
            _meta_set(meta_key, json.dumps(summary, default=str))
            summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_policy() -> dict[str, Any]:
    """Return the current retention policy."""
    return {
        **POLICY,
        "backup_root_abs": str(BACKUP_ROOT.resolve()),
        "backup_dir_exists": BACKUP_ROOT.exists(),
    }


def run_retention_pass(dry_run: bool = False) -> dict[str, Any]:
    """Execute a full retention pass across all safe-to-trim tables.

    Args:
        dry_run: If True, count rows that would be affected but do not delete.

    Returns:
        Summary dict with per-table stats and overall totals.
    """
    started_at = _now_utc()
    logger.info("data_retention: starting pass (dry_run=%s)", dry_run)

    # Build daily summaries before trimming so we capture pre-trim data.
    daily_summaries = []
    try:
        daily_summaries = build_daily_summaries(days_back=HOT_DAYS + 1)
    except Exception as exc:
        logger.warning("data_retention: daily summary build failed: %s", exc)

    table_stats = []
    total_exported = 0
    total_deleted = 0

    for fn in [
        _trim_runtime_events,
        _trim_automation_snapshots,
        _trim_task_metrics,
        _trim_friction_events,
        _trim_external_tool_usage,
    ]:
        try:
            stats = fn(dry_run=dry_run)
            table_stats.append(stats)
            total_exported += int(stats.get("exported", 0))
            total_deleted += int(stats.get("deleted", 0))
        except Exception as exc:
            logger.error("data_retention: table pass failed (%s): %s", fn.__name__, exc)
            table_stats.append({"fn": fn.__name__, "error": str(exc)})

    finished_at = _now_utc()
    result: dict[str, Any] = {
        "dry_run": dry_run,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "total_exported": total_exported,
        "total_deleted": total_deleted,
        "tables": table_stats,
        "daily_summaries_built": len(daily_summaries),
    }

    if not dry_run:
        # Persist last-run metadata.
        _meta_set("retention:last_run", json.dumps(result, default=str))
        logger.info(
            "data_retention: pass complete — exported=%d deleted=%d",
            total_exported,
            total_deleted,
        )

    return result


def get_status() -> dict[str, Any]:
    """Return status of the last retention run and current row counts."""
    _udb.ensure_schema()

    last_run_raw = _meta_get("retention:last_run")
    last_run: dict[str, Any] | None = None
    if last_run_raw:
        try:
            last_run = json.loads(last_run_raw)
        except Exception:
            pass

    with _udb.session() as s:
        runtime_count = int(s.query(func.count(RuntimeEventRecord.id)).scalar() or 0)
        snapshot_count = int(s.query(func.count(AutomationUsageSnapshotRecord.id)).scalar() or 0)
        task_metric_count = int(s.query(func.count(TaskMetricRecord.id)).scalar() or 0)
        friction_count = int(s.query(func.count(FrictionEventRecord.id)).scalar() or 0)
        tool_count = int(s.query(func.count(ExternalToolUsageEventRecord.id)).scalar() or 0)

    backup_sizes: dict[str, int] = {}
    if BACKUP_ROOT.exists():
        for table_dir in BACKUP_ROOT.iterdir():
            if table_dir.is_dir():
                total_bytes = sum(f.stat().st_size for f in table_dir.glob("*.jsonl") if f.is_file())
                backup_sizes[table_dir.name] = total_bytes

    return {
        "policy": get_policy(),
        "current_row_counts": {
            "runtime_events": runtime_count,
            "telemetry_automation_usage_snapshots": snapshot_count,
            "telemetry_task_metrics": task_metric_count,
            "telemetry_friction_events": friction_count,
            "telemetry_external_tool_usage_events": tool_count,
        },
        "backup_sizes_bytes": backup_sizes,
        "last_run": last_run,
    }
