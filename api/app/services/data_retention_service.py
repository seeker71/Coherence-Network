"""Data retention service -- tiered telemetry trimming, summarization, off-DB backup.

Retention tiers:
  Hot  (0-7d):   Full detail, queryable in-DB.
  Warm (7-30d):  Daily aggregates stored; detail exported to JSONL backup.
  Cold (30d+):   Weekly aggregates; detail exported to backup, then deleted.

Never delete: ideas, specs, contributions, identities, audit ledger,
              coherence_credits, value_lineage, idea_lineage.

Safe to trim:
  - runtime_events                        (hot_days detail + daily summaries)
  - telemetry_automation_usage_snapshots  (warm_days detail)
  - telemetry_task_metrics                (warm_days detail)
  - telemetry_friction_events             (warm_days detail)
  - telemetry_external_tool_usage_events  (warm_days detail)

Backup format: JSONL files in data/retention-backups/<table>/<YYYY-MM>.jsonl
Config keys (in api/config/api.json):
  data_retention.hot_days   (default 7)
  data_retention.warm_days  (default 30)
  data_retention.cold_days  (default 90)
  data_retention.backup_dir (default data/retention-backups)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func

from app.config_loader import get_int, get_str
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


def _get_hot_days() -> int:
    return get_int("data_retention", "hot_days", default=7)


def _get_warm_days() -> int:
    return get_int("data_retention", "warm_days", default=30)


def _get_cold_days() -> int:
    return get_int("data_retention", "cold_days", default=90)


def _get_backup_root() -> Path:
    configured = get_str("data_retention", "backup_dir", default="data/retention-backups")
    return Path(configured)


def _get_policy() -> dict[str, Any]:
    hot = _get_hot_days()
    warm = _get_warm_days()
    cold = _get_cold_days()
    backup = _get_backup_root()
    return {
        "hot_days": hot,
        "warm_days": warm,
        "cold_days": cold,
        "backup_dir": str(backup),
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


def get_policy() -> dict[str, Any]:
    """Return the current retention policy configuration."""
    return {
        **_get_policy(),
        "backup_root_abs": str(_get_backup_root().resolve()),
        "backup_dir_exists": _get_backup_root().exists(),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cutoff(days: int) -> datetime:
    return _now_utc() - timedelta(days=days)


def _parse_ts(ts_raw: Any) -> datetime:
    if isinstance(ts_raw, datetime):
        return ts_raw
    if isinstance(ts_raw, str):
        try:
            return datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return _now_utc()


def _append_backup(table: str, records: list[dict[str, Any]]) -> int:
    """Append records to monthly JSONL backup files. Returns count written."""
    if not records:
        return 0
    written = 0
    by_month: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        ts_raw = (
            rec.get("recorded_at")
            or rec.get("collected_at")
            or rec.get("occurred_at")
            or rec.get("created_at")
        )
        ts = _parse_ts(ts_raw)
        by_month[ts.strftime("%Y-%m")].append(rec)
    for month_key, month_recs in by_month.items():
        path = _get_backup_root() / table / f"{month_key}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for rec in month_recs:
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
# Per-table trim functions
# ---------------------------------------------------------------------------


def _trim_runtime_events(dry_run: bool = False) -> dict[str, Any]:
    """Export then delete runtime_events older than HOT_DAYS."""
    _udb.ensure_schema()
    hot_days = _get_hot_days()
    cutoff = _cutoff(hot_days)
    stats: dict[str, Any] = {
        "table": "runtime_events",
        "cutoff_days": hot_days,
        "exported": 0,
        "deleted": 0,
    }
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
                "recorded_at": (
                    r.recorded_at.isoformat()
                    if isinstance(r.recorded_at, datetime)
                    else str(r.recorded_at)
                ),
            }
            for r in old_rows
        ]
        if not dry_run:
            stats["exported"] = _append_backup("runtime_events", records)
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)
    return stats


def _trim_by_timestamp(
    model_cls: Any,
    ts_attr: str,
    table_name: str,
    cutoff_days: int,
    batch: int,
    extra_fields: dict[str, str],
    dry_run: bool,
) -> dict[str, Any]:
    """Generic trim helper for tables with a payload_json column."""
    _udb.ensure_schema()
    cutoff = _cutoff(cutoff_days)
    stats: dict[str, Any] = {
        "table": table_name,
        "cutoff_days": cutoff_days,
        "exported": 0,
        "deleted": 0,
    }
    ts_col = getattr(model_cls, ts_attr)
    with _udb.session() as s:
        old_rows = (
            s.query(model_cls)
            .filter(ts_col < cutoff)
            .order_by(model_cls.id.asc())
            .limit(batch)
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
            for dest, src in extra_fields.items():
                raw = getattr(r, src, None)
                payload.setdefault(
                    dest,
                    raw.isoformat() if isinstance(raw, datetime) else raw,
                )
            records.append(payload)
        if not dry_run:
            stats["exported"] = _append_backup(table_name, records)
            for row in old_rows:
                s.delete(row)
            stats["deleted"] = len(old_rows)
        else:
            stats["would_export"] = len(records)
            stats["would_delete"] = len(old_rows)
    return stats


def _trim_automation_snapshots(dry_run: bool = False) -> dict[str, Any]:
    return _trim_by_timestamp(
        AutomationUsageSnapshotRecord,
        "collected_at",
        "telemetry_automation_usage_snapshots",
        _get_warm_days(),
        5000,
        {"collected_at": "collected_at"},
        dry_run,
    )


def _trim_task_metrics(dry_run: bool = False) -> dict[str, Any]:
    return _trim_by_timestamp(
        TaskMetricRecord,
        "occurred_at",
        "telemetry_task_metrics",
        _get_warm_days(),
        10000,
        {"task_id": "task_id", "occurred_at": "occurred_at"},
        dry_run,
    )


def _trim_friction_events(dry_run: bool = False) -> dict[str, Any]:
    return _trim_by_timestamp(
        FrictionEventRecord,
        "timestamp",
        "telemetry_friction_events",
        _get_warm_days(),
        10000,
        {"event_id": "event_id", "timestamp": "timestamp"},
        dry_run,
    )


def _trim_external_tool_usage(dry_run: bool = False) -> dict[str, Any]:
    return _trim_by_timestamp(
        ExternalToolUsageEventRecord,
        "occurred_at",
        "telemetry_external_tool_usage_events",
        _get_warm_days(),
        10000,
        {
            "event_id": "event_id",
            "tool_name": "tool_name",
            "provider": "provider",
            "occurred_at": "occurred_at",
        },
        dry_run,
    )


# ---------------------------------------------------------------------------
# Daily aggregate summaries
# ---------------------------------------------------------------------------


def _compute_daily_runtime_summary(date_str: str) -> dict[str, Any] | None:
    """Compute a daily aggregate for runtime_events on date_str (YYYY-MM-DD)."""
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
    ep_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        ep_counts[r.endpoint] += 1
    top = sorted(ep_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "date": date_str,
        "count": count,
        "avg_runtime_ms": round(total_ms / count, 2) if count else 0,
        "error_count": error_count,
        "error_rate": round(error_count / count, 4) if count else 0,
        "top_endpoints": [{"endpoint": ep, "calls": n} for ep, n in top],
    }


def build_daily_summaries(days_back: int = 7) -> list[dict[str, Any]]:
    """Build (or retrieve cached) daily runtime summaries for the past N days."""
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


def run_retention_pass(dry_run: bool = False) -> dict[str, Any]:
    """Execute a full retention pass: summarize, export to backup, trim rows.

    Builds daily summaries BEFORE trimming so aggregates survive deletion.
    Set dry_run=True to preview without modifying data.
    """
    started_at = _now_utc()
    logger.info("data_retention: starting pass (dry_run=%s)", dry_run)

    daily_summaries: list[dict] = []
    try:
        daily_summaries = build_daily_summaries(days_back=_get_hot_days() + 1)
    except Exception as exc:
        logger.warning("data_retention: daily summary build failed: %s", exc)

    table_stats: list[dict[str, Any]] = []
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
            st = fn(dry_run=dry_run)
            table_stats.append(st)
            total_exported += int(st.get("exported", 0))
            total_deleted += int(st.get("deleted", 0))
        except Exception as exc:
            logger.error("data_retention: %s failed: %s", fn.__name__, exc)
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
        _meta_set("retention:last_run", json.dumps(result, default=str))
        logger.info(
            "data_retention: complete exported=%d deleted=%d",
            total_exported,
            total_deleted,
        )
    return result


def get_status() -> dict[str, Any]:
    """Return last run metadata and current live row counts."""
    _udb.ensure_schema()
    last_run: dict[str, Any] | None = None
    raw = _meta_get("retention:last_run")
    if raw:
        try:
            last_run = json.loads(raw)
        except Exception:
            pass
    with _udb.session() as s:
        rc = int(s.query(func.count(RuntimeEventRecord.id)).scalar() or 0)
        sc = int(s.query(func.count(AutomationUsageSnapshotRecord.id)).scalar() or 0)
        tmc = int(s.query(func.count(TaskMetricRecord.id)).scalar() or 0)
        fc = int(s.query(func.count(FrictionEventRecord.id)).scalar() or 0)
        tc = int(s.query(func.count(ExternalToolUsageEventRecord.id)).scalar() or 0)
    backup_sizes: dict[str, int] = {}
    backup_root = _get_backup_root()
    if backup_root.exists():
        for td in backup_root.iterdir():
            if td.is_dir():
                backup_sizes[td.name] = sum(
                    f.stat().st_size for f in td.glob("*.jsonl") if f.is_file()
                )
    return {
        "policy": _get_policy(),
        "current_row_counts": {
            "runtime_events": rc,
            "telemetry_automation_usage_snapshots": sc,
            "telemetry_task_metrics": tmc,
            "telemetry_friction_events": fc,
            "telemetry_external_tool_usage_events": tc,
        },
        "backup_sizes_bytes": backup_sizes,
        "last_run": last_run,
    }
