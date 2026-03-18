"""Tests for grounded cost & value measurement service (spec 115).

Every test verifies exact computed values from known inputs.
No mocks, no self-reported scores — all values derive from observable signals.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.grounded_measurement_service import (
    compute_grounded_cost,
    compute_grounded_value,
    record_grounded_measurement,
)


def _store(tmp_path: Path) -> Path:
    return tmp_path / "grounded_measurements.json"


# ---------------------------------------------------------------------------
# compute_grounded_cost: exact values from real signals
# ---------------------------------------------------------------------------


class TestGroundedCost:
    def test_prefers_actual_cost_when_available(self) -> None:
        cost = compute_grounded_cost(actual_cost_usd=0.0034, runtime_cost_estimate=0.0018)
        assert cost == 0.0034

    def test_falls_back_to_runtime_estimate_when_no_actual(self) -> None:
        cost = compute_grounded_cost(actual_cost_usd=None, runtime_cost_estimate=0.0018)
        assert cost == 0.0018

    def test_falls_back_to_runtime_estimate_when_actual_is_zero(self) -> None:
        # Free-tier provider returns 0.0 — use infra cost instead
        cost = compute_grounded_cost(actual_cost_usd=0.0, runtime_cost_estimate=0.0018)
        assert cost == 0.0018

    def test_floor_when_both_zero(self) -> None:
        # Edge case: both zero (should never happen but handle it)
        cost = compute_grounded_cost(actual_cost_usd=None, runtime_cost_estimate=0.0)
        assert cost == 0.0001

    def test_negative_actual_cost_ignored(self) -> None:
        # Defensive: negative cost from provider is not real
        cost = compute_grounded_cost(actual_cost_usd=-0.001, runtime_cost_estimate=0.005)
        assert cost == 0.005


# ---------------------------------------------------------------------------
# compute_grounded_value: exact values from observable outcomes
# ---------------------------------------------------------------------------


class TestGroundedValue:
    def test_completed_first_attempt_full_value(self) -> None:
        value, breakdown = compute_grounded_value(status="completed", retry_count=0)
        assert value == 1.0
        assert breakdown["outcome_signal"] == 1.0
        assert breakdown["quality_multiplier"] == 1.0
        assert breakdown["confidence_weight"] == 1.0

    def test_failed_always_zero(self) -> None:
        value, breakdown = compute_grounded_value(status="failed", retry_count=0)
        assert value == 0.0
        assert breakdown["outcome_signal"] == 0.0

    def test_retry_1_degrades_value(self) -> None:
        value, breakdown = compute_grounded_value(status="completed", retry_count=1)
        assert value == 0.7
        assert breakdown["quality_multiplier"] == 0.7

    def test_retry_2_degrades_further(self) -> None:
        value, breakdown = compute_grounded_value(status="completed", retry_count=2)
        assert value == 0.4
        assert breakdown["quality_multiplier"] == 0.4

    def test_retry_3_plus_minimal_value(self) -> None:
        value, _ = compute_grounded_value(status="completed", retry_count=3)
        assert value == 0.2
        value5, _ = compute_grounded_value(status="completed", retry_count=5)
        assert value5 == 0.2

    def test_heal_failed_zero_value(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=0,
            heal_attempt=True, heal_succeeded=False,
        )
        assert value == 0.0
        assert breakdown["quality_multiplier"] == 0.0

    def test_heal_succeeded_keeps_value(self) -> None:
        value, _ = compute_grounded_value(
            status="completed", retry_count=0,
            heal_attempt=True, heal_succeeded=True,
        )
        assert value == 1.0

    def test_confidence_scales_value(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=0, confidence=0.5,
        )
        assert value == 0.5
        assert breakdown["confidence_weight"] == 0.5

    def test_confidence_clamped_low(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=0, confidence=0.01,
        )
        assert breakdown["confidence_weight"] == 0.1
        assert value == 0.1  # 1.0 * 1.0 * 0.1

    def test_confidence_clamped_high(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=0, confidence=1.5,
        )
        assert breakdown["confidence_weight"] == 1.0
        assert value == 1.0

    def test_confidence_none_defaults_to_one(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=0, confidence=None,
        )
        assert breakdown["confidence_weight"] == 1.0
        assert value == 1.0

    def test_combined_retry_and_confidence(self) -> None:
        value, breakdown = compute_grounded_value(
            status="completed", retry_count=1, confidence=0.8,
        )
        # 1.0 * 0.7 * 0.8 = 0.56
        assert abs(value - 0.56) < 1e-9
        assert breakdown["outcome_signal"] == 1.0
        assert breakdown["quality_multiplier"] == 0.7
        assert breakdown["confidence_weight"] == 0.8

    def test_failed_ignores_confidence_and_retries(self) -> None:
        value, _ = compute_grounded_value(
            status="failed", retry_count=0, confidence=0.9,
        )
        assert value == 0.0


# ---------------------------------------------------------------------------
# record_grounded_measurement: end-to-end with raw signal persistence
# ---------------------------------------------------------------------------


class TestRecordGroundedMeasurement:
    def test_skips_task_without_prompt_variant(self, tmp_path) -> None:
        task = {"id": "task-1", "task_type": "impl", "context": {}}
        result = record_grounded_measurement(
            task_id="task-1", task=task, status="completed",
            elapsed_ms=5000, actual_cost_usd=0.003,
            runtime_cost_estimate=0.001, store_path=_store(tmp_path),
        )
        assert result is None

    def test_records_with_real_signals(self, tmp_path) -> None:
        sp = _store(tmp_path)
        task = {
            "id": "task-abc",
            "task_type": "impl",
            "context": {"prompt_variant": "v2", "retry_count": 0},
        }
        result = record_grounded_measurement(
            task_id="task-abc", task=task, status="completed",
            elapsed_ms=9200, actual_cost_usd=0.0034,
            runtime_cost_estimate=0.0018,
            output_metrics={"confidence": 0.85},
            store_path=sp,
        )
        assert result is not None
        assert result["variant_id"] == "v2"
        assert result["task_type"] == "impl"
        assert result["task_id"] == "task-abc"

        # Verify cost is actual provider cost, not infra estimate
        assert result["resource_cost"] == 0.0034

        # Verify value = 1.0 * 1.0 * 0.85 = 0.85
        assert result["value_score"] == 0.85

        # Verify raw signals are persisted
        raw = result["raw_signals"]
        assert raw["status"] == "completed"
        assert raw["actual_cost_usd"] == 0.0034
        assert raw["runtime_cost_estimate"] == 0.0018
        assert raw["runtime_ms"] == 9200
        assert raw["confidence"] == 0.85
        assert raw["retry_count"] == 0
        assert raw["outcome_signal"] == 1.0
        assert raw["quality_multiplier"] == 1.0
        assert raw["confidence_weight"] == 0.85

    def test_failed_task_records_zero_value_with_real_cost(self, tmp_path) -> None:
        sp = _store(tmp_path)
        task = {
            "id": "task-fail",
            "task_type": "review",
            "context": {"prompt_variant": "v1"},
        }
        result = record_grounded_measurement(
            task_id="task-fail", task=task, status="failed",
            elapsed_ms=3000, actual_cost_usd=0.002,
            runtime_cost_estimate=0.0006, store_path=sp,
        )
        assert result is not None
        assert result["value_score"] == 0.0
        assert result["resource_cost"] == 0.002  # Still charged real cost

    def test_retried_task_degrades_value(self, tmp_path) -> None:
        sp = _store(tmp_path)
        task = {
            "id": "task-retry",
            "task_type": "impl",
            "context": {"prompt_variant": "v3", "retry_count": 2},
        }
        result = record_grounded_measurement(
            task_id="task-retry", task=task, status="completed",
            elapsed_ms=15000, actual_cost_usd=0.008,
            runtime_cost_estimate=0.003, store_path=sp,
        )
        assert result is not None
        assert result["value_score"] == 0.4  # quality_multiplier for 2 retries
        assert result["resource_cost"] == 0.008

    def test_raw_signals_persisted_to_store(self, tmp_path) -> None:
        """Verify the JSON store contains raw_signals for recalibration."""
        sp = _store(tmp_path)
        task = {
            "id": "task-persist",
            "task_type": "spec",
            "context": {"prompt_variant": "v1"},
        }
        record_grounded_measurement(
            task_id="task-persist", task=task, status="completed",
            elapsed_ms=2000, actual_cost_usd=None,
            runtime_cost_estimate=0.0004, store_path=sp,
        )

        # Read the store directly and verify raw_signals are there
        stored = json.loads(sp.read_text())
        assert len(stored) == 1
        record = stored[0]
        assert "raw_signals" in record
        assert record["raw_signals"]["actual_cost_usd"] is None
        assert record["raw_signals"]["runtime_cost_estimate"] == 0.0004
        assert record["raw_signals"]["runtime_ms"] == 2000
        assert record["task_id"] == "task-persist"
        # Cost falls back to runtime_cost_estimate
        assert record["resource_cost"] == 0.0004

    def test_feeds_into_roi_service_correctly(self, tmp_path) -> None:
        """Verify grounded measurements are usable by get_variant_stats."""
        from app.services import prompt_ab_roi_service

        sp = _store(tmp_path)
        # Record two grounded measurements for different variants
        task_a = {"id": "t1", "task_type": "impl", "context": {"prompt_variant": "fast_prompt"}}
        task_b = {"id": "t2", "task_type": "impl", "context": {"prompt_variant": "thorough_prompt"}}

        record_grounded_measurement(
            task_id="t1", task=task_a, status="completed",
            elapsed_ms=3000, actual_cost_usd=0.001,
            runtime_cost_estimate=0.0006, store_path=sp,
        )
        record_grounded_measurement(
            task_id="t2", task=task_b, status="completed",
            elapsed_ms=15000, actual_cost_usd=0.008,
            runtime_cost_estimate=0.003, store_path=sp,
        )

        stats = prompt_ab_roi_service.get_variant_stats(store_path=sp)
        assert stats["total_measurements"] == 2

        # fast_prompt: value=1.0, cost=0.001 → ROI=1000
        fast = stats["variants"]["fast_prompt"]
        assert fast["roi"] == 1000.0  # 1.0 / 0.001
        assert fast["mean_cost"] == 0.001

        # thorough_prompt: value=1.0, cost=0.008 → ROI=125
        thorough = stats["variants"]["thorough_prompt"]
        assert thorough["roi"] == 125.0  # 1.0 / 0.008
        assert thorough["mean_cost"] == 0.008

        # fast_prompt has higher ROI
        assert fast["roi"] > thorough["roi"]
