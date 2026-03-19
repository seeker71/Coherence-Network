"""Tests for grounded cost & value measurement service (spec 115).

Every test verifies exact computed values from known inputs.
No mocks, no self-reported scores — all values derive from observable signals.

The economic value layer (compute_economic_value_score) is tested as a pure
function with explicit signal dicts — no service mocks needed because the
function takes already-collected signals as input.

Service API contract tests verify that the methods called by
collect_idea_value_signals() actually exist with correct signatures.
"""

from __future__ import annotations

import inspect
import json
import math
from pathlib import Path

from app.services.grounded_measurement_service import (
    collect_idea_value_signals,
    compute_economic_value_score,
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
        cost = compute_grounded_cost(actual_cost_usd=0.0, runtime_cost_estimate=0.0018)
        assert cost == 0.0018

    def test_floor_when_both_zero(self) -> None:
        cost = compute_grounded_cost(actual_cost_usd=None, runtime_cost_estimate=0.0)
        assert cost == 0.0001

    def test_negative_actual_cost_ignored(self) -> None:
        cost = compute_grounded_cost(actual_cost_usd=-0.001, runtime_cost_estimate=0.005)
        assert cost == 0.005


# ---------------------------------------------------------------------------
# compute_grounded_value: execution quality from observable outcomes
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

    def test_retry_3_plus_minimal_value(self) -> None:
        value, _ = compute_grounded_value(status="completed", retry_count=3)
        assert value == 0.2

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
        assert value == 0.1

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

    def test_combined_retry_and_confidence(self) -> None:
        value, _ = compute_grounded_value(
            status="completed", retry_count=1, confidence=0.8,
        )
        assert abs(value - 0.56) < 1e-9  # 1.0 * 0.7 * 0.8

    def test_failed_ignores_confidence_and_retries(self) -> None:
        value, _ = compute_grounded_value(
            status="failed", retry_count=0, confidence=0.9,
        )
        assert value == 0.0


# ---------------------------------------------------------------------------
# compute_economic_value_score: pure function, explicit signal inputs
# ---------------------------------------------------------------------------


class TestEconomicValueScore:
    """Tests the economic value blending as a pure function.

    No services called — we pass explicit signal dicts.
    """

    def test_no_idea_signals_returns_execution_quality(self) -> None:
        """Without idea data, value = execution quality. Honest: no inflation."""
        value, breakdown = compute_economic_value_score(
            execution_quality=0.7,
            idea_signals={"sources": []},
        )
        assert value == 0.7
        assert breakdown["has_idea_signals"] is False

    def test_failed_task_always_zero_regardless_of_idea_value(self) -> None:
        """A failed task produces zero value even for a high-value idea."""
        signals = {
            "sources": ["idea_model", "runtime_events"],
            "usage_event_count": 500,
            "usage_revenue_usd": 0.5,
            "actual_value_usd": 100.0,
            "potential_value_usd": 200.0,
            "value_realization_pct": 0.5,
        }
        value, breakdown = compute_economic_value_score(0.0, signals)
        assert value == 0.0
        assert breakdown["gated_by_failure"] is True

    def test_adoption_signal_from_usage_count(self) -> None:
        """100 API calls = strong adoption signal → high value."""
        signals = {
            "sources": ["runtime_events"],
            "usage_event_count": 100,
            "usage_revenue_usd": 0.1,
            "actual_value_usd": 0.0,
            "potential_value_usd": 0.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 0.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)

        # adoption_score = min(1.0, 0.1 + 0.4 * log10(100)) = 0.1 + 0.4*2 = 0.9
        expected_adoption = min(1.0, 0.1 + 0.4 * math.log10(100))
        assert abs(expected_adoption - 0.9) < 1e-9

        # value = 1.0 * (0.4 + 0.6 * 0.9) = 1.0 * 0.94 = 0.94
        expected_value = 1.0 * (0.4 + 0.6 * expected_adoption)
        assert abs(value - expected_value) < 1e-9
        assert breakdown["economic_signal_source"] == "adoption"

    def test_single_api_call_minimal_adoption(self) -> None:
        """1 API call = minimal adoption signal."""
        signals = {
            "sources": ["runtime_events"],
            "usage_event_count": 1,
            "usage_revenue_usd": 0.001,
            "actual_value_usd": 0.0,
            "potential_value_usd": 0.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 0.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # adoption_score = 0.1 + 0.4 * log10(1) = 0.1 + 0 = 0.1
        # value = 1.0 * (0.4 + 0.6 * 0.1) = 0.46
        expected = 1.0 * (0.4 + 0.6 * 0.1)
        assert abs(value - expected) < 1e-9

    def test_revenue_signal(self) -> None:
        """Direct revenue from usage events."""
        signals = {
            "sources": ["value_lineage"],
            "usage_event_count": 0,
            "usage_revenue_usd": 0.0,
            "lineage_measured_value_usd": 1.0,  # $1 measured value
            "actual_value_usd": 0.0,
            "potential_value_usd": 0.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 0.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # revenue = $1.0, revenue_score = min(1.0, 0.2 + 0.3 * log10(100)) = 0.2 + 0.6 = 0.8
        expected_rev_score = min(1.0, 0.2 + 0.3 * math.log10(max(0.01, 1.0 * 100)))
        expected_value = 1.0 * (0.4 + 0.6 * expected_rev_score)
        assert abs(value - expected_value) < 1e-9
        assert breakdown["economic_signal_source"] == "revenue"

    def test_value_realization_signal(self) -> None:
        """Idea with 80% value realization."""
        signals = {
            "sources": ["idea_model"],
            "usage_event_count": 0,
            "usage_revenue_usd": 0.0,
            "actual_value_usd": 80.0,
            "potential_value_usd": 100.0,
            "value_realization_pct": 0.8,
            "friction_cost_of_delay_usd": 0.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # value_realization = 0.8, value = 1.0 * (0.4 + 0.6 * 0.8) = 0.88
        expected = 1.0 * (0.4 + 0.6 * 0.8)
        assert abs(value - expected) < 1e-9
        assert breakdown["economic_signal_source"] == "value_realization"

    def test_friction_cost_avoidance_signal(self) -> None:
        """$50 friction cost_of_delay = strong urgency signal."""
        signals = {
            "sources": ["friction_events"],
            "usage_event_count": 0,
            "usage_revenue_usd": 0.0,
            "actual_value_usd": 0.0,
            "potential_value_usd": 0.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 50.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # friction_value = min(1.0, 0.2 + 0.3 * log10(50)) = 0.2 + 0.3*1.699 ≈ 0.71
        expected_friction = min(1.0, 0.2 + 0.3 * math.log10(50))
        expected_value = 1.0 * (0.4 + 0.6 * expected_friction)
        assert abs(value - expected_value) < 1e-6
        assert breakdown["economic_signal_source"] == "friction_avoidance"

    def test_strongest_signal_wins(self) -> None:
        """When multiple signals present, strongest one drives the score."""
        signals = {
            "sources": ["idea_model", "runtime_events", "friction_events"],
            "usage_event_count": 10,   # adoption = 0.1 + 0.4*1 = 0.5
            "usage_revenue_usd": 0.01,
            "actual_value_usd": 90.0,
            "potential_value_usd": 100.0,
            "value_realization_pct": 0.9,  # realization = 0.9 (strongest)
            "friction_cost_of_delay_usd": 5.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # value_realization (0.9) > adoption (0.5) > friction (~0.41)
        assert breakdown["economic_signal_source"] == "value_realization"
        # value = 1.0 * (0.4 + 0.6 * 0.9) = 0.94
        expected = 1.0 * (0.4 + 0.6 * 0.9)
        assert abs(value - expected) < 1e-9

    def test_execution_quality_degrades_economic_value(self) -> None:
        """Retried task gets economic value scaled down by execution quality."""
        signals = {
            "sources": ["runtime_events"],
            "usage_event_count": 100,
            "usage_revenue_usd": 0.1,
            "actual_value_usd": 0.0,
            "potential_value_usd": 0.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 0.0,
        }
        # Execution quality = 0.4 (2 retries)
        value, _ = compute_economic_value_score(0.4, signals)
        # adoption = 0.9, value = 0.4 * (0.4 + 0.6 * 0.9) = 0.4 * 0.94 = 0.376
        expected = 0.4 * (0.4 + 0.6 * 0.9)
        assert abs(value - expected) < 1e-9

    def test_idea_linked_but_no_economic_evidence_yet(self) -> None:
        """Idea exists but has no usage, no revenue, no friction yet."""
        signals = {
            "sources": ["idea_model"],
            "usage_event_count": 0,
            "usage_revenue_usd": 0.0,
            "actual_value_usd": 0.0,
            "potential_value_usd": 50.0,
            "value_realization_pct": 0.0,
            "friction_cost_of_delay_usd": 0.0,
        }
        value, breakdown = compute_economic_value_score(1.0, signals)
        # No economic evidence → returns execution quality
        assert value == 1.0
        assert breakdown.get("no_economic_evidence") is True


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

    def test_records_with_real_signals_no_idea(self, tmp_path) -> None:
        """Task with prompt_variant but no idea_id → execution quality only."""
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
        assert result["resource_cost"] == 0.0034

        # No idea_id → value = execution quality = 1.0 * 1.0 * 0.85 = 0.85
        assert result["value_score"] == 0.85

        # Raw signals contain economic breakdown
        raw = result["raw_signals"]
        assert raw["execution_quality"] == 0.85
        assert raw["idea_id"] is None
        assert raw["economic_breakdown"]["has_idea_signals"] is False

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
        assert result["resource_cost"] == 0.002

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
        # No idea_id → value = execution quality = 0.4
        assert result["value_score"] == 0.4
        assert result["resource_cost"] == 0.008

    def test_raw_signals_persisted_to_store(self, tmp_path) -> None:
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

        stored = json.loads(sp.read_text())
        assert len(stored) == 1
        record = stored[0]
        assert "raw_signals" in record
        assert record["raw_signals"]["actual_cost_usd"] is None
        assert record["raw_signals"]["runtime_cost_estimate"] == 0.0004
        assert record["raw_signals"]["runtime_ms"] == 2000
        assert record["task_id"] == "task-persist"
        assert record["resource_cost"] == 0.0004

        # Economic signals persisted for recalibration
        assert "idea_signals" in record["raw_signals"]
        assert "economic_breakdown" in record["raw_signals"]

    def test_feeds_into_roi_service_correctly(self, tmp_path) -> None:
        from app.services import prompt_ab_roi_service

        sp = _store(tmp_path)
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

        fast = stats["variants"]["fast_prompt"]
        assert fast["roi"] == 1000.0  # 1.0 / 0.001
        thorough = stats["variants"]["thorough_prompt"]
        assert thorough["roi"] == 125.0  # 1.0 / 0.008
        assert fast["roi"] > thorough["roi"]


# ---------------------------------------------------------------------------
# Service API contract tests: verify the methods we call actually exist
# ---------------------------------------------------------------------------


class TestServiceAPIContracts:
    """Verify that collect_idea_value_signals calls real service methods.

    These are NOT mock tests. They import the real service modules and check
    that the methods exist with the expected signatures. If a service method
    is renamed or removed, these tests fail — preventing silent degradation.
    """

    def test_idea_service_get_idea_exists(self) -> None:
        from app.services import idea_service
        assert hasattr(idea_service, "get_idea"), "idea_service.get_idea() must exist"
        sig = inspect.signature(idea_service.get_idea)
        params = list(sig.parameters.keys())
        assert "idea_id" in params, f"get_idea must accept idea_id, got params: {params}"

    def test_runtime_service_summarize_by_idea_exists(self) -> None:
        from app.services import runtime_service
        assert hasattr(runtime_service, "summarize_by_idea"), (
            "runtime_service.summarize_by_idea() must exist"
        )
        sig = inspect.signature(runtime_service.summarize_by_idea)
        params = list(sig.parameters.keys())
        assert "seconds" in params, f"summarize_by_idea must accept seconds, got: {params}"

    def test_value_lineage_service_list_links_exists(self) -> None:
        from app.services import value_lineage_service
        assert hasattr(value_lineage_service, "list_links"), (
            "value_lineage_service.list_links() must exist"
        )
        assert hasattr(value_lineage_service, "valuation"), (
            "value_lineage_service.valuation() must exist"
        )
        sig_links = inspect.signature(value_lineage_service.list_links)
        assert "limit" in list(sig_links.parameters.keys())
        sig_val = inspect.signature(value_lineage_service.valuation)
        assert "lineage_id" in list(sig_val.parameters.keys())

    def test_telemetry_persistence_list_friction_events_exists(self) -> None:
        from app.services import telemetry_persistence_service
        assert hasattr(telemetry_persistence_service, "list_friction_events"), (
            "telemetry_persistence_service.list_friction_events() must exist"
        )
        sig = inspect.signature(telemetry_persistence_service.list_friction_events)
        params = list(sig.parameters.keys())
        assert "limit" in params, f"list_friction_events must accept limit, got: {params}"

    def test_collect_signals_returns_empty_for_none_idea(self) -> None:
        """No idea_id → empty signals, no service calls."""
        signals = collect_idea_value_signals(None)
        assert signals["idea_id"] is None
        assert signals["sources"] == []
        assert signals["usage_event_count"] == 0

    def test_collect_signals_returns_empty_for_empty_idea(self) -> None:
        signals = collect_idea_value_signals("")
        assert signals["sources"] == []
