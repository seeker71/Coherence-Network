"""Provider measurement stats endpoint.

Exposes per-provider performance data from SlotSelector for the web frontend.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter

from app.services import federation_service
from app.services.slot_selection_service import SlotSelector

router = APIRouter(prefix="/api/providers", tags=["providers"])
logger = logging.getLogger(__name__)

_TASK_TYPES = ["spec", "impl", "test", "review", "heal"]
_STORE_DIR = Path(__file__).resolve().parents[2] / "logs" / "slot_measurements"
_ATTENTION_THRESHOLD = 0.5


def _load_raw_measurements(task_type: str) -> list[dict]:
    """Load raw measurements for a provider_{task_type} decision point."""
    path = _STORE_DIR / f"provider_{task_type}.json"
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _last_n(records: list[dict], n: int = 5) -> list[dict]:
    """Return the last n records sorted by timestamp."""
    return records[-n:]


def _success_rate(records: list[dict]) -> float:
    if not records:
        return 0.0
    successes = sum(1 for r in records if r.get("value_score", 0) > 0)
    return round(successes / len(records), 4)


def _avg_duration(records: list[dict]) -> float:
    durations = [r["duration_s"] for r in records if "duration_s" in r]
    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 1)


def _error_breakdown(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        ec = r.get("error_class")
        if ec:
            counts[ec] = counts.get(ec, 0) + 1
    return counts


@router.get("/stats")
async def get_provider_stats() -> dict:
    """Per-provider stats across all task types."""
    # Collect all measurements grouped by provider
    provider_all: dict[str, list[dict]] = {}
    task_type_data: dict[str, dict[str, list[dict]]] = {}

    for task_type in _TASK_TYPES:
        measurements = _load_raw_measurements(task_type)
        per_provider: dict[str, list[dict]] = {}
        for m in measurements:
            sid = m.get("slot_id", "unknown")
            # Tag with task_type for last_5_runs display
            m_tagged = {**m, "task_type": task_type}
            provider_all.setdefault(sid, []).append(m_tagged)
            per_provider.setdefault(sid, []).append(m_tagged)
        task_type_data[task_type] = per_provider

    # Get selection probabilities from SlotSelector.stats()
    selection_probs: dict[str, float] = {}
    for task_type in _TASK_TYPES:
        try:
            selector = SlotSelector(f"provider_{task_type}", store_dir=_STORE_DIR)
            stats = selector.stats()
            for sid, slot_info in stats.get("slots", {}).items():
                # Accumulate probabilities across task types (will average later)
                current = selection_probs.get(sid, [])
                if not isinstance(current, list):
                    current = []
                current.append(slot_info.get("selection_probability", 0.0))
                selection_probs[sid] = current
        except Exception:
            logger.debug("Failed to get stats for provider_%s", task_type, exc_info=True)

    # Average selection probabilities across task types
    avg_probs: dict[str, float] = {}
    for sid, probs in selection_probs.items():
        if isinstance(probs, list) and probs:
            avg_probs[sid] = round(sum(probs) / len(probs), 4)

    # Build per-provider response
    providers: dict[str, dict] = {}
    alerts: list[dict] = []
    attention_count = 0

    for sid, records in sorted(provider_all.items()):
        total_runs = len(records)
        successes = sum(1 for r in records if r.get("value_score", 0) > 0)
        failures = total_runs - successes
        overall_rate = _success_rate(records)

        last_5 = _last_n(records, 5)
        last_5_rate = _success_rate(last_5)

        last_5_runs = [
            {
                "success": r.get("value_score", 0) > 0,
                "duration_s": r.get("duration_s", 0.0),
                "task_type": r.get("task_type", ""),
                "timestamp": r.get("timestamp", ""),
            }
            for r in last_5
        ]

        blocked = SlotSelector._is_blocked(records)
        needs_attention = last_5_rate < _ATTENTION_THRESHOLD
        if needs_attention:
            attention_count += 1
            alerts.append({
                "provider": sid,
                "metric": "last_5_rate",
                "value": last_5_rate,
                "threshold": _ATTENTION_THRESHOLD,
                "message": f"{sid} last-5 success rate {int(last_5_rate * 100)}% < {int(_ATTENTION_THRESHOLD * 100)}% threshold",
            })

        # Duration percentiles for data-driven timeouts
        durations = sorted([r["duration_s"] for r in records if "duration_s" in r])
        p90_dur = durations[int(len(durations) * 0.9)] if durations else 0.0
        max_dur = durations[-1] if durations else 0.0
        suggested_timeout = max(60.0, min(600.0, p90_dur * 2.5)) if p90_dur > 0 else 300.0

        providers[sid] = {
            "total_runs": total_runs,
            "successes": successes,
            "failures": failures,
            "success_rate": overall_rate,
            "last_5_rate": last_5_rate,
            "last_5_runs": last_5_runs,
            "avg_duration_s": _avg_duration(records),
            "p90_duration_s": round(p90_dur, 1),
            "max_duration_s": round(max_dur, 1),
            "suggested_timeout_s": round(suggested_timeout, 0),
            "selection_probability": avg_probs.get(sid, 0.0),
            "blocked": blocked,
            "needs_attention": needs_attention,
            "error_breakdown": _error_breakdown(records),
        }

    # Build per-task-type breakdown
    task_types: dict[str, dict] = {}
    for task_type in _TASK_TYPES:
        per_provider = task_type_data.get(task_type, {})
        if not per_provider:
            continue
        tt_providers: dict[str, dict] = {}
        for sid, records in sorted(per_provider.items()):
            successes = sum(1 for r in records if r.get("value_score", 0) > 0)
            failures = len(records) - successes
            last_5 = _last_n(records, 5)
            tt_providers[sid] = {
                "successes": successes,
                "failures": failures,
                "success_rate": _success_rate(records),
                "last_5_rate": _success_rate(last_5),
                "avg_duration_s": _avg_duration(records),
            }
        task_types[task_type] = {"providers": tt_providers}

    total_measurements = sum(len(r) for r in provider_all.values())
    healthy_count = len(providers) - attention_count

    return {
        "providers": providers,
        "task_types": task_types,
        "alerts": alerts,
        "summary": {
            "total_providers": len(providers),
            "healthy_providers": healthy_count,
            "attention_needed": attention_count,
            "total_measurements": total_measurements,
        },
    }


@router.get("/stats/network")
async def get_network_provider_stats(window_days: int = 7) -> dict:
    """Network-wide provider stats from federation nodes.

    Shaped to be compatible with /api/providers/stats response plus a `nodes` field.
    """
    agg = federation_service.get_aggregated_node_stats(window_days=window_days)

    # Reshape providers to match /api/providers/stats format
    providers: dict[str, dict] = {}
    attention_count = 0
    alerts = agg.get("alerts", [])

    for sid, pdata in agg.get("providers", {}).items():
        needs_attention = pdata["overall_success_rate"] < _ATTENTION_THRESHOLD
        if needs_attention:
            attention_count += 1
        providers[sid] = {
            "total_runs": pdata["total_samples"],
            "successes": pdata["total_successes"],
            "failures": pdata["total_failures"],
            "success_rate": pdata["overall_success_rate"],
            "avg_duration_s": pdata["avg_duration_s"],
            "node_count": pdata["node_count"],
            "per_node": pdata["per_node"],
            "needs_attention": needs_attention,
        }

    total_measurements = agg.get("total_measurements", 0)
    healthy_count = len(providers) - attention_count

    return {
        "providers": providers,
        "task_types": agg.get("task_types", {}),
        "alerts": alerts,
        "summary": {
            "total_providers": len(providers),
            "healthy_providers": healthy_count,
            "attention_needed": attention_count,
            "total_measurements": total_measurements,
        },
        "nodes": agg.get("nodes", {}),
        "window_days": agg.get("window_days", window_days),
    }
