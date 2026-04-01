"""Path and config helpers for runtime telemetry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config_loader import get_float, get_str


def _default_events_path() -> Path:
    return Path(__file__).resolve().parents[3] / "logs" / "runtime_events.json"


def events_path() -> Path:
    configured = get_str("runtime", "events_path")
    return Path(configured) if configured else _default_events_path()


def _default_idea_map_path() -> Path:
    return Path(__file__).resolve().parents[3] / "logs" / "runtime_idea_map.json"


def idea_map_path() -> Path:
    configured = get_str("runtime", "idea_map_path")
    return Path(configured) if configured else _default_idea_map_path()


def logs_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "logs"


def agent_tasks_path() -> Path:
    configured = get_str("agent_tasks", "path")
    if configured:
        return Path(configured)
    return logs_dir() / "agent_tasks.json"


def monitor_issues_path() -> Path:
    return logs_dir() / "monitor_issues.json"


def status_report_path() -> Path:
    return logs_dir() / "pipeline_status_report.json"


def path_signature(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size": 0, "mtime_ns": 0}
    return {
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def runtime_cost_per_second() -> float:
    return get_float("agent_cost", "runtime_cost_per_second", 0.002)


def estimate_runtime_cost(runtime_ms: float) -> float:
    return round((max(0.0, float(runtime_ms)) / 1000.0) * runtime_cost_per_second(), 8)
