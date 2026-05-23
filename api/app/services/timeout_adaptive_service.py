"""Data-driven task timeout samples and recommendations.

The service keeps the timeout contract small and file-backed: task runs append
JSONL samples, and recommendations activate only after enough comparable
samples exist for a provider/task-type pair.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles
from typing import Any

from app.config_loader import get_float, get_int, get_str


_DEFAULT_BASELINE_SECONDS_BY_TYPE: dict[str, int] = {
    "spec": 1200,
    "impl": 2400,
    "test": 1800,
    "review": 1200,
    "heal": 1200,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _samples_path() -> Path:
    configured = get_str("agent_tasks", "timeout_samples_path", "")
    path = Path(configured) if configured else _repo_root() / "api" / "logs" / "timeout_samples.jsonl"
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _min_samples() -> int:
    return max(1, get_int("agent_tasks", "adaptive_timeout_min_samples", default=5))


def _multiplier() -> float:
    return max(1.0, get_float("agent_tasks", "adaptive_timeout_p90_multiplier", default=1.5))


def _baseline_seconds(task_type: str, default: int | None = None) -> int:
    if default is not None:
        return max(1, int(default))
    key = f"timeout_{task_type}_seconds"
    configured = get_int("agent_tasks", key, default=0)
    if configured > 0:
        return configured
    return _DEFAULT_BASELINE_SECONDS_BY_TYPE.get(task_type, 1200)


def _p90(values: list[int]) -> int:
    if len(values) < 2:
        return values[0]
    return int(quantiles(values, n=10, method="inclusive")[8])


def record_timeout_sample(sample: dict[str, Any]) -> dict[str, Any]:
    task_type = str(sample.get("task_type") or "").strip().lower()
    provider = str(sample.get("provider") or "").strip().lower()
    elapsed_ms = int(sample.get("elapsed_ms") or 0)
    outcome = str(sample.get("outcome") or "").strip().lower()
    if not task_type:
        raise ValueError("task_type is required")
    if not provider:
        raise ValueError("provider is required")
    if elapsed_ms <= 0:
        raise ValueError("elapsed_ms must be positive")
    if outcome not in {"completed", "failed", "timed_out"}:
        raise ValueError("outcome must be completed, failed, or timed_out")

    row = {
        "provider": provider,
        "task_type": task_type,
        "elapsed_ms": elapsed_ms,
        "completed_at": sample.get("completed_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "outcome": outcome,
        "task_id": str(sample.get("task_id") or ""),
        "idea_id": sample.get("idea_id"),
    }
    path = _samples_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def list_timeout_samples() -> list[dict[str, Any]]:
    path = _samples_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def timeout_recommendation(
    task_type: str,
    provider: str,
    *,
    baseline_seconds: int | None = None,
) -> dict[str, Any]:
    task_type = task_type.strip().lower()
    provider = provider.strip().lower()
    baseline = _baseline_seconds(task_type, baseline_seconds)
    comparable = [
        int(row["elapsed_ms"])
        for row in list_timeout_samples()
        if str(row.get("task_type") or "").lower() == task_type
        and str(row.get("provider") or "").lower() == provider
        and int(row.get("elapsed_ms") or 0) > 0
    ]
    if len(comparable) < _min_samples():
        return {
            "task_type": task_type,
            "provider": provider,
            "timeout_seconds": baseline,
            "mode": "fixed",
            "samples": len(comparable),
            "min_samples": _min_samples(),
            "derivation": "fewer_than_min_samples",
        }
    p90_ms = _p90(sorted(comparable))
    recommended = int((p90_ms / 1000.0) * _multiplier())
    recommended = max(baseline, min(recommended, baseline * 3))
    return {
        "task_type": task_type,
        "provider": provider,
        "timeout_seconds": recommended,
        "mode": "adaptive",
        "samples": len(comparable),
        "min_samples": _min_samples(),
        "p90_ms": p90_ms,
        "baseline_seconds": baseline,
        "upper_clamp_seconds": baseline * 3,
        "derivation": "p90_times_multiplier_clamped",
    }


def timeout_metrics() -> dict[str, Any]:
    rows = list_timeout_samples()
    completed = [r for r in rows if r.get("outcome") == "completed"]
    timed_out = [r for r in rows if r.get("outcome") == "timed_out"]
    by_provider: dict[str, dict[str, Any]] = {}
    for row in rows:
        provider = str(row.get("provider") or "unknown")
        bucket = by_provider.setdefault(provider, {"samples": 0, "completed": 0, "timed_out": 0})
        bucket["samples"] += 1
        if row.get("outcome") == "completed":
            bucket["completed"] += 1
        if row.get("outcome") == "timed_out":
            bucket["timed_out"] += 1
    total = len(rows)
    return {
        "samples": total,
        "completed": len(completed),
        "timed_out": len(timed_out),
        "efficiency_ratio": round(len(completed) / total, 4) if total else 0.0,
        "providers": by_provider,
    }
