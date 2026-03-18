from __future__ import annotations

import fcntl
import json
import random
from datetime import datetime, timezone
from pathlib import Path


def _default_store_path() -> Path:
    """Return default path for measurement storage."""
    return Path(__file__).resolve().parents[2] / "logs" / "prompt_ab_measurements.json"


def _load_measurements(store_path: Path) -> list[dict]:
    """Load measurements from JSON file."""
    if not store_path.exists():
        return []
    with open(store_path, "r") as f:
        return json.load(f)


def record_prompt_outcome(
    variant_id: str,
    task_type: str,
    value_score: float,
    resource_cost: float,
    *,
    store_path: Path | None = None,
) -> dict:
    """Record a single prompt outcome measurement."""
    if not (0.0 <= value_score <= 1.0):
        raise ValueError(f"value_score must be in [0.0, 1.0], got {value_score}")
    if resource_cost <= 0:
        raise ValueError(f"resource_cost must be > 0, got {resource_cost}")

    store = store_path or _default_store_path()
    store.parent.mkdir(parents=True, exist_ok=True)

    measurement = {
        "variant_id": variant_id,
        "task_type": task_type,
        "value_score": value_score,
        "resource_cost": resource_cost,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with open(store, "a+" if store.exists() else "w+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            measurements: list[dict] = json.loads(content) if content else []
            measurements.append(measurement)
            f.seek(0)
            f.truncate()
            json.dump(measurements, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    return measurement


def get_variant_stats(
    store_path: Path | None = None,
    task_type: str | None = None,
) -> dict:
    """Compute per-variant statistics with Thompson Sampling probabilities."""
    store = store_path or _default_store_path()
    measurements = _load_measurements(store)
    if task_type:
        measurements = [m for m in measurements if m.get("task_type") == task_type]

    # Group by variant_id
    variant_data: dict[str, list[dict]] = {}
    for m in measurements:
        vid = m["variant_id"]
        variant_data.setdefault(vid, []).append(m)

    variants: dict[str, dict] = {}
    blocked_count = 0

    for vid, records in variant_data.items():
        n = len(records)
        total_value = sum(r["value_score"] for r in records)
        total_cost = sum(r["resource_cost"] for r in records)
        mean_value = total_value / n if n > 0 else 0.0
        mean_cost = total_cost / n if n > 0 else 0.0
        roi = total_value / total_cost if total_cost > 0 else 0.0

        # Blocked: first 3 measurements all have value_score == 0.0
        blocked = False
        if n >= 3:
            first_three = records[:3]
            if all(r["value_score"] == 0.0 for r in first_three):
                blocked = True

        if blocked:
            blocked_count += 1

        variants[vid] = {
            "sample_count": n,
            "mean_value": mean_value,
            "mean_cost": mean_cost,
            "roi": roi,
            "blocked": blocked,
            "selection_probability": 0.0,
        }

    # Compute Thompson Sampling weights for non-blocked variants
    active_variants = {k: v for k, v in variants.items() if not v["blocked"]}

    if active_variants:
        weights: dict[str, float] = {}
        for vid, stats in active_variants.items():
            n = stats["sample_count"]
            if n < 5:
                weights[vid] = 0.2
            else:
                total_value = stats["mean_value"] * n
                alpha = 1.0 + total_value
                beta = 1.0 + (n - total_value)
                weights[vid] = random.betavariate(alpha, beta)

        total_weight = sum(weights.values())
        if total_weight > 0:
            for vid in active_variants:
                variants[vid]["selection_probability"] = weights[vid] / total_weight

    return {
        "variants": variants,
        "total_measurements": len(measurements),
        "active_variants": len(active_variants),
        "blocked_variants": blocked_count,
    }


def select_variant(
    task_type: str,
    available_variants: list[str],
    *,
    store_path: Path | None = None,
) -> str | None:
    """Select a variant using Thompson Sampling with exploration boost.

    Returns None if all available variants are blocked.
    """
    if not available_variants:
        raise ValueError("available_variants must not be empty")

    store = store_path or _default_store_path()
    measurements = _load_measurements(store)
    # Filter by task_type for scoped selection
    measurements = [m for m in measurements if m.get("task_type") == task_type]

    # Group by variant_id
    variant_data: dict[str, list[dict]] = {}
    for m in measurements:
        vid = m["variant_id"]
        variant_data.setdefault(vid, []).append(m)

    # Fallback: no measurements for any available variant
    has_any = any(v in variant_data for v in available_variants)
    if not has_any:
        return random.choice(available_variants)

    # Compute weights
    weights: dict[str, float] = {}
    for vid in available_variants:
        records = variant_data.get(vid, [])
        n = len(records)

        # Blocked check: first 3 measurements all zero
        if n >= 3:
            first_three = records[:3]
            if all(r["value_score"] == 0.0 for r in first_three):
                continue  # skip blocked

        if n < 5:
            weights[vid] = 0.2
        else:
            total_value = sum(r["value_score"] for r in records)
            alpha = 1.0 + total_value
            beta = 1.0 + (n - total_value)
            weights[vid] = random.betavariate(alpha, beta)

    # If all blocked, return None — caller must handle
    if not weights:
        return None

    # Weighted selection
    variant_ids = list(weights.keys())
    variant_weights = [weights[v] for v in variant_ids]
    total = sum(variant_weights)
    probabilities = [w / total for w in variant_weights]

    r = random.random()
    cumulative = 0.0
    for vid, p in zip(variant_ids, probabilities):
        cumulative += p
        if r <= cumulative:
            return vid
    return variant_ids[-1]
