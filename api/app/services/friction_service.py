"""Friction ledger service for API and scripts."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config_loader import get_bool, get_str
from app.models.friction import FrictionEvent
from app.services import metrics_service, telemetry_persistence_service

logger = logging.getLogger(__name__)


def _default_path() -> Path:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    return logs_dir / "friction_events.jsonl"


def friction_file_path() -> Path:
    configured = get_str("friction", "events_path")
    return Path(configured) if configured else _default_path()


def report_window_limit_days() -> int:
    """Return the safe report horizon for the current friction event backend."""
    if get_str("friction", "events_path"):
        return 365
    return 90


def _use_db_events() -> bool:
    if get_str("friction", "events_path"):
        return False
    return get_bool("friction", "use_db", True)


def monitor_issues_file_path() -> Path:
    configured = get_str("monitor", "issues_path")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "monitor_issues.json"


def github_actions_health_file_path() -> Path:
    configured = get_str("github_actions", "health_path")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "github_actions_health.json"


def _parse_iso_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_events(path: Path | None = None) -> tuple[list[FrictionEvent], int]:
    if _use_db_events():
        telemetry_persistence_service.ensure_schema()
        legacy_path = friction_file_path()
        report = telemetry_persistence_service.import_friction_events_from_file(legacy_path)
        if int(report.get("imported") or 0) > 0:
            purge_raw = get_str("friction", "purge_imported_files", default="1").strip().lower()
            if purge_raw not in {"0", "false", "no", "off"}:
                try:
                    legacy_path.unlink(missing_ok=True)
                except OSError:
                    pass
        events: list[FrictionEvent] = []
        ignored = 0
        for payload in telemetry_persistence_service.list_friction_events(limit=10000):
            try:
                events.append(FrictionEvent(**payload))
            except Exception:
                ignored += 1
                continue
        events.sort(key=lambda e: e.timestamp, reverse=True)
        if ignored > 0:
            logger.warning("Ignored %d FrictionEvent deserialization failures from DB events", ignored)
        return events, ignored
    path = path or friction_file_path()
    if not path.exists():
        return [], 0
    events: list[FrictionEvent] = []
    ignored = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                ignored += 1
                continue
            events.append(FrictionEvent(**payload))
        except Exception:
            ignored += 1
            continue
    events.sort(key=lambda e: e.timestamp, reverse=True)
    if ignored > 0:
        logger.warning("Ignored %d FrictionEvent deserialization failures from %s", ignored, path)
    return events, ignored


def append_event(event: FrictionEvent, path: Path | None = None) -> None:
    if _use_db_events():
        telemetry_persistence_service.append_friction_event(event.model_dump(mode="json"))
        return
    path = path or friction_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(event.model_dump(mode="json"))
    with path.open("a", encoding="utf-8") as f:
        f.write(serialized + "\n")


def summarize(events: list[FrictionEvent], window_days: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
    in_window = [e for e in events if e.timestamp >= since]
    open_events = [e for e in in_window if e.status == "open"]

    by_block_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0, "cost_of_delay": 0.0}
    )
    by_stage: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0}
    )

    for event in in_window:
        bt = by_block_type[event.block_type]
        bt["count"] += 1
        bt["energy_loss"] += event.energy_loss_estimate
        bt["cost_of_delay"] += event.cost_of_delay

        st = by_stage[event.stage]
        st["count"] += 1
        st["energy_loss"] += event.energy_loss_estimate

    top_block_types = sorted(
        (
            {
                "key": block_type,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
                "cost_of_delay": round(float(vals["cost_of_delay"]), 4),
            }
            for block_type, vals in by_block_type.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    top_stages = sorted(
        (
            {
                "key": stage,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
            }
            for stage, vals in by_stage.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    return {
        "window_days": max(1, window_days),
        "from": _parse_iso_utc(since.isoformat()).isoformat().replace("+00:00", "Z"),
        "to": _parse_iso_utc(now.isoformat()).isoformat().replace("+00:00", "Z"),
        "total_events": len(in_window),
        "open_events": len(open_events),
        "total_energy_loss": round(sum(e.energy_loss_estimate for e in in_window), 4),
        "total_cost_of_delay": round(sum(e.cost_of_delay for e in in_window), 4),
        "top_block_types": top_block_types,
        "top_stages": top_stages,
    }



# Public API re-exports — entry points and category rollups live in
# friction_entry_points_service to keep this module focused on event I/O
# and below the modularity threshold (#163).
def friction_entry_points(window_days: int = 7, limit: int = 20) -> dict[str, Any]:
    from app.services.friction_entry_points_service import friction_entry_points as _impl
    return _impl(window_days=window_days, limit=limit)


def friction_categories(window_days: int = 7, limit: int = 20) -> dict[str, Any]:
    from app.services.friction_entry_points_service import friction_categories as _impl
    return _impl(window_days=window_days, limit=limit)
