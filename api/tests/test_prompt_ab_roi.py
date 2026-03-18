from __future__ import annotations

from pathlib import Path

from app.services import prompt_ab_roi_service


def _store(tmp_path: Path) -> Path:
    return tmp_path / "measurements.json"


def test_record_and_retrieve_measurement(tmp_path) -> None:
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome(
        "v1", "impl", value_score=0.7, resource_cost=1.0, store_path=sp,
    )
    prompt_ab_roi_service.record_prompt_outcome(
        "v1", "review", value_score=0.5, resource_cost=2.0, store_path=sp,
    )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    assert stats["variants"]["v1"]["sample_count"] == 2


def test_roi_computation(tmp_path) -> None:
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome(
        "variant_a", "impl", value_score=0.8, resource_cost=2.0, store_path=sp,
    )
    prompt_ab_roi_service.record_prompt_outcome(
        "variant_b", "impl", value_score=0.6, resource_cost=1.0, store_path=sp,
    )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    roi_a = stats["variants"]["variant_a"]["roi"]
    roi_b = stats["variants"]["variant_b"]["roi"]
    # ROI = value / cost => 0.4 vs 0.6
    assert roi_b > roi_a


def test_variant_blocked_after_three_zeros(tmp_path) -> None:
    sp = _store(tmp_path)
    for _ in range(3):
        prompt_ab_roi_service.record_prompt_outcome(
            "bad_variant", "impl", value_score=0.0, resource_cost=1.0, store_path=sp,
        )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
    assert stats["variants"]["bad_variant"]["blocked"] is True

    # When only blocked variants available, select_variant returns None
    result = prompt_ab_roi_service.select_variant(
        "impl", ["bad_variant"], store_path=sp,
    )
    assert result is None

    # With a good variant available, blocked variant is never selected
    prompt_ab_roi_service.record_prompt_outcome(
        "good_variant", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
    )
    for _ in range(50):
        chosen = prompt_ab_roi_service.select_variant(
            "impl", ["bad_variant", "good_variant"], store_path=sp,
        )
        assert chosen != "bad_variant"


def test_new_variant_exploration_priority(tmp_path) -> None:
    sp = _store(tmp_path)
    for _ in range(20):
        prompt_ab_roi_service.record_prompt_outcome(
            "established", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
        )
    # "new_variant" has 0 measurements — exploration boost should kick in.
    selections = [
        prompt_ab_roi_service.select_variant(
            "impl", ["established", "new_variant"], store_path=sp,
        )
        for _ in range(50)
    ]
    new_count = selections.count("new_variant")
    assert new_count >= 5, f"new_variant selected only {new_count}/50 times"


def test_selection_favors_high_roi(tmp_path) -> None:
    sp = _store(tmp_path)
    for _ in range(10):
        prompt_ab_roi_service.record_prompt_outcome(
            "high_roi", "impl", value_score=0.9, resource_cost=1.0, store_path=sp,
        )
        prompt_ab_roi_service.record_prompt_outcome(
            "low_roi", "impl", value_score=0.1, resource_cost=1.0, store_path=sp,
        )
    selections = [
        prompt_ab_roi_service.select_variant(
            "impl", ["high_roi", "low_roi"], store_path=sp,
        )
        for _ in range(100)
    ]
    high_count = selections.count("high_roi")
    assert high_count > 60, f"high_roi selected only {high_count}/100 times"


def test_stats_endpoint_shape(tmp_path) -> None:
    sp = _store(tmp_path)
    prompt_ab_roi_service.record_prompt_outcome(
        "v1", "impl", value_score=0.5, resource_cost=1.0, store_path=sp,
    )
    stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)

    # Top-level keys.
    for key in ("variants", "total_measurements", "active_variants", "blocked_variants"):
        assert key in stats, f"missing top-level key: {key}"

    # Per-variant entry keys.
    variant_entry = stats["variants"]["v1"]
    for key in (
        "sample_count",
        "mean_value",
        "mean_cost",
        "roi",
        "blocked",
        "selection_probability",
    ):
        assert key in variant_entry, f"missing variant key: {key}"
