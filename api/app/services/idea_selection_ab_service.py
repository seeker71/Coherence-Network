"""A/B tracking for idea selection methods.

Records which method was used, what it picked first, and the expected
cost/value so we can compare outcomes over time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).resolve().parents[3] / "api" / "logs" / "idea_selection_ab.json"


def record_selection(
    method: str,
    top_picks: list[dict[str, Any]],
    total_remaining_cost_cc: float,
    total_value_gap_cc: float,
    expected_roi: float,
) -> None:
    """Record an idea selection event for A/B comparison."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "top_picks": [
            {
                "idea_id": p.get("idea_id", ""),
                "score": round(p.get("score", 0.0), 4),
                "value_gap": round(p.get("value_gap", 0.0), 4),
                "remaining_cost": round(p.get("remaining_cost", 0.0), 4),
            }
            for p in top_picks[:5]
        ],
        "total_remaining_cost_cc": round(total_remaining_cost_cc, 4),
        "total_value_gap_cc": round(total_value_gap_cc, 4),
        "expected_roi": round(expected_roi, 4),
    }

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if _LOG_PATH.exists():
        try:
            with open(_LOG_PATH) as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError):
            records = []

    records.append(entry)

    with open(_LOG_PATH, "w") as f:
        json.dump(records, f, indent=2)


def get_comparison() -> dict[str, Any]:
    """Get A/B comparison stats."""
    if not _LOG_PATH.exists():
        return {"total_selections": 0, "by_method": {}}

    try:
        with open(_LOG_PATH) as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"total_selections": 0, "by_method": {}}

    by_method: dict[str, list] = {}
    for r in records:
        m = r.get("method", "unknown")
        by_method.setdefault(m, []).append(r)

    stats: dict[str, Any] = {
        "total_selections": len(records),
        "by_method": {},
    }

    for method, recs in by_method.items():
        rois = [r.get("expected_roi", 0) for r in recs]
        costs = [r.get("total_remaining_cost_cc", 0) for r in recs]
        gaps = [r.get("total_value_gap_cc", 0) for r in recs]
        stats["by_method"][method] = {
            "count": len(recs),
            "avg_expected_roi": round(sum(rois) / len(rois), 4) if rois else 0,
            "avg_remaining_cost_cc": round(sum(costs) / len(costs), 4) if costs else 0,
            "avg_value_gap_cc": round(sum(gaps) / len(gaps), 4) if gaps else 0,
        }

    return stats
