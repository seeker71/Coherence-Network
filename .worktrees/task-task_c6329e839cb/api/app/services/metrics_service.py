"""Task metrics: persistence and aggregation. Spec 026 Phase 1."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List

from app.config_loader import get_bool, get_int, get_str
from app.services import telemetry_persistence_service
from app.services.config_service import get_database_url

logger = logging.getLogger(__name__)

_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
METRICS_FILE = os.path.join(_api_dir, "logs", "metrics.jsonl")
WINDOW_DAYS = 7


def _default_metrics_file() -> str:
    return METRICS_FILE


def _metrics_file_path() -> Path:
    configured = get_str("metrics", "file_path")
    if configured:
        return Path(configured)
    return Path(_default_metrics_file())


def _is_postgres_backend() -> bool:
    url = get_database_url()
    return "postgres" in url.lower()


def _use_db_metrics() -> bool:
    override = get_str("metrics", "use_db")
    if override:
        override = override.strip().lower()
        if override in {"1", "true", "yes", "on"}:
            return True
        if override in {"0", "false", "no", "off"}:
            return False
    return _is_postgres_backend()


def _purge_legacy_metrics_file_if_enabled(imported_from_file: bool) -> None:
    if not imported_from_file:
        return
    if not get_bool("metrics", "purge_legacy_file", True):
        return
    path = _metrics_file_path()
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError:
        return


def _bootstrap_db_metrics_if_needed() -> None:
    telemetry_persistence_service.ensure_schema()
    imported_from_file = False
    legacy = _metrics_file_path()
    if legacy.exists():
        report = telemetry_persistence_service.import_task_metrics_from_file(legacy)
        imported_from_file = int(report.get("imported") or 0) > 0
    _purge_legacy_metrics_file_if_enabled(imported_from_file)


def _empty_aggregates() -> dict[str, Any]:
    """Return empty structure for GET /api/agent/metrics when no data or on error."""
    return {
        "success_rate": {"completed": 0, "failed": 0, "total": 0, "rate": 0.0},
        "execution_time": {"p50_seconds": 0, "p95_seconds": 0},
        "by_task_type": {},
        "by_model": {},
    }


def record_task(
    task_id: str,
    task_type: str,
    model: str,
    duration_seconds: float,
    status: str,
    executor: str = "",
    prompt_variant: str | None = None,
    skill_version: str | None = None,
) -> None:
    """Append one task metric (JSONL). Call from agent_runner or PATCH /api/agent/tasks when status is completed/failed."""
    record: dict[str, Any] = {
        "task_id": task_id,
        "task_type": task_type,
        "model": model,
        "duration_seconds": duration_seconds,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if executor:
        record["executor"] = executor
    if prompt_variant:
        record["prompt_variant"] = prompt_variant
    if skill_version:
        record["skill_version"] = skill_version

    if _use_db_metrics():
        _bootstrap_db_metrics_if_needed()
        max_rows = get_int("metrics", "max_rows", 50000)
        telemetry_persistence_service.append_task_metric(record, max_rows=max_rows)
        return

    file_path = _metrics_file_path()
    os.makedirs(str(file_path.parent), exist_ok=True)
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _load_records() -> List[dict]:
    """Load all records from JSONL file."""
    if _use_db_metrics():
        _bootstrap_db_metrics_if_needed()
        return telemetry_persistence_service.list_task_metrics(limit=100000)

    file_path = _metrics_file_path()
    if not file_path.is_file():
        return []
    records = []
    with file_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_aggregates(window_days: int | None = None) -> dict[str, Any]:
    """Aggregate metrics for GET /api/agent/metrics. Rolling window (default 7d). Returns empty structure on error."""
    days = window_days if window_days is not None and 1 <= window_days <= 90 else WINDOW_DAYS
    try:
        records = _load_records()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        windowed = []
        for r in records:
            try:
                ts = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                if ts >= cutoff:
                    windowed.append(r)
            except (ValueError, KeyError):
                continue

        completed = sum(1 for r in windowed if r.get("status") == "completed")
        failed = sum(1 for r in windowed if r.get("status") == "failed")
        total = completed + failed
        rate = completed / total if total > 0 else 0.0

        durations = [r["duration_seconds"] for r in windowed if isinstance(r.get("duration_seconds"), (int, float))]
        durations.sort()
        n = len(durations)
        p50 = durations[n // 2] if n > 0 else 0
        p95 = durations[int(n * 0.95)] if n > 1 else (durations[0] if n == 1 else 0)
        p50_seconds = int(round(p50))
        p95_seconds = int(round(p95))

        by_task_type: dict[str, dict[str, Any]] = {}
        for r in windowed:
            tt = r.get("task_type", "unknown")
            if tt not in by_task_type:
                by_task_type[tt] = {"count": 0, "completed": 0, "failed": 0}
            by_task_type[tt]["count"] += 1
            if r.get("status") == "completed":
                by_task_type[tt]["completed"] += 1
            elif r.get("status") == "failed":
                by_task_type[tt]["failed"] += 1
        for tt, v in by_task_type.items():
            t = v["completed"] + v["failed"]
            v["success_rate"] = round(v["completed"] / t, 2) if t > 0 else 0.0

        by_model: dict[str, dict[str, Any]] = {}
        for r in windowed:
            m = r.get("model", "unknown")
            if m not in by_model:
                by_model[m] = {"count": 0, "durations": []}
            by_model[m]["count"] += 1
            if isinstance(r.get("duration_seconds"), (int, float)):
                by_model[m]["durations"].append(r["duration_seconds"])
        for m, v in by_model.items():
            ds = v.pop("durations", [])
            v["avg_duration"] = round(sum(ds) / len(ds), 1) if ds else 0

        # Phase 2: aggregate by prompt_variant when present
        by_prompt_variant: dict[str, dict[str, Any]] = {}
        for r in windowed:
            pv = r.get("prompt_variant")
            if not pv:
                continue
            if pv not in by_prompt_variant:
                by_prompt_variant[pv] = {"count": 0, "completed": 0, "failed": 0, "durations": []}
            by_prompt_variant[pv]["count"] += 1
            if r.get("status") == "completed":
                by_prompt_variant[pv]["completed"] += 1
            elif r.get("status") == "failed":
                by_prompt_variant[pv]["failed"] += 1
            if isinstance(r.get("duration_seconds"), (int, float)):
                by_prompt_variant[pv]["durations"].append(r["duration_seconds"])
        for pv, v in by_prompt_variant.items():
            ds = v.pop("durations", [])
            v["avg_duration"] = round(sum(ds) / len(ds), 1) if ds else 0
            t = v["completed"] + v["failed"]
            v["success_rate"] = round(v["completed"] / t, 2) if t > 0 else 0.0

        out = {
            "success_rate": {"completed": completed, "failed": failed, "total": total, "rate": float(round(rate, 2))},
            "execution_time": {"p50_seconds": p50_seconds, "p95_seconds": p95_seconds},
            "by_task_type": by_task_type,
            "by_model": by_model,
        }
        if by_prompt_variant:
            out["by_prompt_variant"] = by_prompt_variant
        if window_days is not None and 1 <= window_days <= 90:
            out["window_days"] = days
        return out
    except Exception:
        logger.warning("Metrics aggregation failed", exc_info=True)
        return _empty_aggregates()
