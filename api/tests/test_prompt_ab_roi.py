"""Tests for prompt A/B ROI measurement service (spec 112).

All tests use real service logic with deterministic seeds where randomness is involved.
No mocks, no fallback paths — every assertion verifies the primary code path.
"""

from __future__ import annotations

import random
from pathlib import Path

from app.services import prompt_ab_roi_service


def _store(tmp_path: Path) -> Path:
    return tmp_path / "measurements.json"


def test_record_and_retrieve_measurement(tmp_path) -> None:
    sp = _store(tmp_path)
    m1 = prompt_ab_roi_service.record_prompt_outcome(
        "v1", "impl", value_score=0.7, resource_cost=1.0, store_path=sp,
    )
    m2 = prompt_ab_roi_service.record_prompt_outcome(
        "v1", "review", value_score=0.5, resource_cost=2.0, store_path=sp,
    )
    # Verify returned records have correct fields
    assert m1["variant_id"] == "v1"
    assert m1["task_type"] == "impl"
    assert m1["value_score"] == 0.7
    assert "timestamp" in m1

    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    assert stats["variants"]["v1"]["sample_count"] == 2
    assert stats["total_measurements"] == 2


def test_roi_computation_exact_values(tmp_path) -> None:
    """Verify ROI = sum(value) / sum(cost) with exact values, not just relative order."""
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome(
        "variant_a", "impl", value_score=0.8, resource_cost=2.0, store_path=sp,
    )
    prompt_ab_roi_service.record_prompt_outcome(
        "variant_b", "impl", value_score=0.6, resource_cost=1.0, store_path=sp,
    )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)

    va = stats["variants"]["variant_a"]
    assert va["roi"] == 0.4  # 0.8 / 2.0
    assert va["mean_value"] == 0.8
    assert va["mean_cost"] == 2.0
    assert va["sample_count"] == 1
    assert va["blocked"] is False

    vb = stats["variants"]["variant_b"]
    assert vb["roi"] == 0.6  # 0.6 / 1.0
    assert vb["mean_value"] == 0.6
    assert vb["mean_cost"] == 1.0


def test_roi_computation_multiple_samples(tmp_path) -> None:
    """Verify ROI aggregation across multiple measurements for the same variant."""
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome("v1", "impl", value_score=0.8, resource_cost=1.0, store_path=sp)
    prompt_ab_roi_service.record_prompt_outcome("v1", "impl", value_score=0.4, resource_cost=2.0, store_path=sp)
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)

    v = stats["variants"]["v1"]
    assert v["sample_count"] == 2
    assert abs(v["roi"] - 0.4) < 1e-9  # (0.8 + 0.4) / (1.0 + 2.0) = 1.2 / 3.0 = 0.4
    assert abs(v["mean_value"] - 0.6) < 1e-9  # (0.8 + 0.4) / 2
    assert v["mean_cost"] == 1.5  # (1.0 + 2.0) / 2


def test_variant_blocked_after_three_zeros(tmp_path) -> None:
    sp = _store(tmp_path)
    for _ in range(3):
        prompt_ab_roi_service.record_prompt_outcome(
            "bad_variant", "impl", value_score=0.0, resource_cost=1.0, store_path=sp,
        )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    assert stats["variants"]["bad_variant"]["blocked"] is True
    assert stats["blocked_variants"] == 1
    assert stats["active_variants"] == 0

    # When only blocked variants available, select_variant still returns one
    # (probe weight) — blocked slots get retried periodically, not permanently excluded
    result = prompt_ab_roi_service.select_variant(
        "impl", ["bad_variant"], store_path=sp,
    )
    assert result == "bad_variant"  # only option, gets probe weight

    # With a good variant, blocked variant is rarely selected (probe weight ~2%)
    for _ in range(5):
        prompt_ab_roi_service.record_prompt_outcome(
            "good_variant", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
        )
    choices = []
    for _ in range(100):
        chosen = prompt_ab_roi_service.select_variant(
            "impl", ["bad_variant", "good_variant"], store_path=sp,
        )
        choices.append(chosen)
    good_pct = choices.count("good_variant") / len(choices)
    # Good variant should dominate (>85%), blocked gets tiny probe weight
    assert good_pct > 0.85, f"good_variant selected only {good_pct:.0%} of the time"


def test_exploration_boost_with_measured_data(tmp_path) -> None:
    """New variants with < 5 measurements get exploration weight 0.2.

    This test ensures the exploration path (not the no-data fallback) is exercised.
    Both variants have measurements, but "exploring" has fewer than 5.
    """
    sp = _store(tmp_path)

    # Established variant: 10 measurements, high value
    for _ in range(10):
        prompt_ab_roi_service.record_prompt_outcome(
            "established", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
        )
    # Exploring variant: 2 measurements (< 5 threshold), also has data
    for _ in range(2):
        prompt_ab_roi_service.record_prompt_outcome(
            "exploring", "impl", value_score=0.5, resource_cost=1.0, store_path=sp,
        )

    # Seed randomness for deterministic test
    state = random.getstate()
    random.seed(42)
    try:
        selections = [
            prompt_ab_roi_service.select_variant(
                "impl", ["established", "exploring"], store_path=sp,
            )
            for _ in range(100)
        ]
    finally:
        random.setstate(state)

    exploring_count = selections.count("exploring")
    # With weight 0.2 for exploring vs Thompson sample (~0.85+) for established,
    # exploring should get roughly 15-25% of selections
    assert exploring_count >= 5, f"exploring selected only {exploring_count}/100 times"
    assert exploring_count <= 50, f"exploring selected {exploring_count}/100 — too many, exploration weight broken"
    # Established must dominate
    assert selections.count("established") > selections.count("exploring")


def test_selection_deterministic_with_seed(tmp_path) -> None:
    """Thompson Sampling selection is deterministic when seeded.

    Verifies the REAL Thompson Sampling path (>= 5 samples), not fallback.
    """
    sp = _store(tmp_path)
    for _ in range(10):
        prompt_ab_roi_service.record_prompt_outcome(
            "high_roi", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
        )
        prompt_ab_roi_service.record_prompt_outcome(
            "low_roi", "impl", value_score=0.1, resource_cost=1.0, store_path=sp,
        )

    # Run with fixed seed for deterministic result
    state = random.getstate()
    random.seed(123)
    try:
        selections = [
            prompt_ab_roi_service.select_variant(
                "impl", ["high_roi", "low_roi"], store_path=sp,
            )
            for _ in range(100)
        ]
    finally:
        random.setstate(state)

    high_count = selections.count("high_roi")
    # With seed 123 and 10 samples each (high=0.9, low=0.1), high_roi must dominate
    assert high_count > 60, f"high_roi selected only {high_count}/100 times"

    # Verify determinism: same seed → same result
    random.seed(123)
    try:
        selections2 = [
            prompt_ab_roi_service.select_variant(
                "impl", ["high_roi", "low_roi"], store_path=sp,
            )
            for _ in range(100)
        ]
    finally:
        random.setstate(state)

    assert selections == selections2, "Same seed must produce identical selections"


def test_stats_endpoint_shape(tmp_path) -> None:
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome(
        "v1", "impl", value_score=0.5, resource_cost=1.0, store_path=sp,
    )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)

    # Top-level keys
    assert stats["total_measurements"] == 1
    assert stats["active_variants"] == 1
    assert stats["blocked_variants"] == 0

    # Per-variant exact values
    v = stats["variants"]["v1"]
    assert v["sample_count"] == 1
    assert v["mean_value"] == 0.5
    assert v["mean_cost"] == 1.0
    assert v["roi"] == 0.5
    assert v["blocked"] is False
    assert isinstance(v["selection_probability"], float)


def test_task_type_filtering(tmp_path) -> None:
    """get_variant_stats and select_variant filter by task_type."""
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome("v1", "spec", value_score=1.0, resource_cost=1.0, store_path=sp)
    prompt_ab_roi_service.record_prompt_outcome("v1", "impl", value_score=0.3, resource_cost=2.0, store_path=sp)

    # Unfiltered: both measurements
    stats_all = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    assert stats_all["total_measurements"] == 2

    # Filtered to spec: only the spec measurement
    stats_spec = prompt_ab_roi_service.get_variant_stats(store_path=sp, task_type="spec")
    assert stats_spec["total_measurements"] == 1
    assert stats_spec["variants"]["v1"]["roi"] == 1.0

    # Filtered to impl: only the impl measurement
    stats_impl = prompt_ab_roi_service.get_variant_stats(store_path=sp, task_type="impl")
    assert stats_impl["total_measurements"] == 1
    assert stats_impl["variants"]["v1"]["roi"] == 0.15  # 0.3 / 2.0


def test_input_validation(tmp_path) -> None:
    """Verify service rejects invalid inputs."""
    sp = _store(tmp_path)
    import pytest

    with pytest.raises(ValueError, match="value_score"):
        prompt_ab_roi_service.record_prompt_outcome("v1", "impl", value_score=1.5, resource_cost=1.0, store_path=sp)

    with pytest.raises(ValueError, match="resource_cost"):
        prompt_ab_roi_service.record_prompt_outcome("v1", "impl", value_score=0.5, resource_cost=-1.0, store_path=sp)

    with pytest.raises(ValueError, match="available_variants"):
        prompt_ab_roi_service.select_variant("impl", [], store_path=sp)
