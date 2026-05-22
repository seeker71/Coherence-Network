"""Tests for grounded cost & value measurement (spec: grounded-cost-value-measurement).

The spec's seven named requirements covered here:

  1. compute_grounded_cost returns actual_cost_usd when present, else
     runtime_cost_estimate (with a floor when both are zero/null).
  2. compute_grounded_value returns 0.0 for failed tasks regardless of
     retry count, heal state, or confidence.
  3. Quality multiplier degrades with retries: 1.0 / 0.7 / 0.4 / 0.2.
  4. Raw signals are stored alongside computed scores in every
     record_grounded_measurement output.
  5. Economic value layer takes max-of-three (adoption / revenue /
     lineage / friction) — strongest signal wins, not average.
  6. compute_idea_metrics chooses strongest of
     (lineage_measured_value, usage_revenue, spec_actual_value_sum).
  7. Tasks without prompt_variant in context are not recorded
     (record_grounded_measurement returns None).

Strange-edge tests where they cover the most boundary in the simplest
expression: e.g. one assertion exercises the heal-failed clamp AND the
status-failed gate by varying only one field at a time.
"""
from __future__ import annotations

from pathlib import Path

from app.services.grounded_idea_metrics_service import compute_idea_metrics
from app.services.grounded_measurement_service import (
    compute_economic_value_score,
    compute_grounded_cost,
    compute_grounded_value,
    record_grounded_measurement,
)


# ---------------------------------------------------------------------------
# Requirement: cost falls back actual -> runtime -> floor
# ---------------------------------------------------------------------------

def test_grounded_cost_prefers_actual_over_estimate() -> None:
    assert compute_grounded_cost(0.0034, 0.0018) == 0.0034


def test_grounded_cost_falls_back_to_runtime_when_actual_missing() -> None:
    assert compute_grounded_cost(None, 0.0018) == 0.0018


def test_grounded_cost_falls_back_to_runtime_when_actual_zero() -> None:
    # actual_cost_usd == 0.0 (free tier) is treated as "no billing signal"
    # and the runtime estimate carries the cost.
    assert compute_grounded_cost(0.0, 0.0042) == 0.0042


def test_grounded_cost_floor_when_both_zero() -> None:
    # Floor protects ROI service (requires cost > 0). CPU time was spent.
    assert compute_grounded_cost(None, 0.0) == 0.0001
    assert compute_grounded_cost(0.0, 0.0) == 0.0001


# ---------------------------------------------------------------------------
# Requirement: failed task -> 0.0 value
# ---------------------------------------------------------------------------

def test_failed_task_value_is_zero_regardless_of_other_signals() -> None:
    # The strangest edge: a failed task with perfect retries, perfect
    # confidence, and no heal — should still be 0.0 because outcome gates.
    value, breakdown = compute_grounded_value(
        status="failed",
        retry_count=0,
        heal_attempt=False,
        heal_succeeded=None,
        confidence=1.0,
    )
    assert value == 0.0
    assert breakdown["outcome_signal"] == 0.0


# ---------------------------------------------------------------------------
# Requirement: quality multiplier branches 1.0 / 0.7 / 0.4 / 0.2
# ---------------------------------------------------------------------------

def test_quality_multiplier_branches() -> None:
    # All four named branches in one tight cluster. Use status=completed
    # with confidence=None so value_score equals quality_multiplier.
    cases = [
        (0, 1.0),
        (1, 0.7),
        (2, 0.4),
        (3, 0.2),   # 3+ branch
        (10, 0.2),  # still 0.2 — the saturation branch
    ]
    for retries, expected in cases:
        value, breakdown = compute_grounded_value(
            status="completed",
            retry_count=retries,
        )
        assert value == expected, f"retries={retries} expected {expected}, got {value}"
        assert breakdown["quality_multiplier"] == expected


def test_heal_failed_zeroes_quality_even_on_completed_status() -> None:
    # Strange edge: status says "completed" but the heal attempt failed.
    # The quality multiplier is forced to 0.0 — sane because a failed heal
    # means the surface looked green but the underlying work didn't land.
    value, breakdown = compute_grounded_value(
        status="completed",
        retry_count=0,
        heal_attempt=True,
        heal_succeeded=False,
    )
    assert value == 0.0
    assert breakdown["quality_multiplier"] == 0.0


def test_confidence_clamped_to_floor() -> None:
    # confidence=0.05 should clamp to 0.1, not drag value to near-zero.
    value, breakdown = compute_grounded_value(
        status="completed",
        retry_count=0,
        confidence=0.05,
    )
    assert breakdown["confidence_weight"] == 0.1
    assert value == 0.1


# ---------------------------------------------------------------------------
# Requirement: max-of-N economic signal (strongest wins, not average)
# ---------------------------------------------------------------------------

def test_economic_value_takes_max_not_average() -> None:
    # Mix one strong signal (revenue) with one weak (single adoption call).
    # Average would be ~0.45; max should pick revenue.
    idea_signals = {
        "usage_event_count": 1,            # adoption ~ 0.1
        "usage_revenue_usd": 0.0,
        "lineage_measured_value_usd": 5.0, # strong revenue path
        "sources": ["idea_model", "value_lineage"],
    }
    value, breakdown = compute_economic_value_score(1.0, idea_signals)
    assert breakdown["economic_signal_source"] == "revenue"
    # Sanity: blended is execution_quality * (0.4 + 0.6 * strongest)
    # With strongest > 0.5, blended must clear 0.7.
    assert value > 0.7


def test_economic_value_no_idea_signals_returns_execution_quality() -> None:
    # No sources -> honest: don't inflate.
    value, breakdown = compute_economic_value_score(0.7, {"sources": []})
    assert value == 0.7
    assert breakdown["has_idea_signals"] is False


def test_economic_value_gated_by_zero_execution_quality() -> None:
    # Even a unicorn idea with strong signals cannot rescue a 0.0 execution.
    idea_signals = {
        "usage_event_count": 1000,
        "usage_revenue_usd": 100.0,
        "sources": ["idea_model", "runtime_events"],
    }
    value, breakdown = compute_economic_value_score(0.0, idea_signals)
    assert value == 0.0
    assert breakdown["gated_by_failure"] is True


# ---------------------------------------------------------------------------
# Requirement: compute_idea_metrics — strongest of lineage / revenue / spec
# ---------------------------------------------------------------------------

def test_idea_metrics_actual_value_picks_strongest_signal() -> None:
    # Three signals, lineage strongest -> wins.
    specs = [{"idea_id": "idea-x", "actual_value": 2.0, "actual_cost": 0.5}]
    runtime = [{"idea_id": "idea-x", "event_count": 100, "runtime_cost_estimate": 0.10}]
    links = [{"id": "lin-1", "idea_id": "idea-x"}]
    valuations = {"lin-1": {"measured_value_total": 50.0, "event_count": 200}}

    result = compute_idea_metrics(
        "idea-x",
        specs=specs,
        runtime_summaries=runtime,
        lineage_links=links,
        lineage_valuations=valuations,
    )

    # usage_revenue = 100 * 0.001 = 0.10; spec sum = 2.0; lineage = 50.0
    # max => 50.0 wins
    assert result["computed_actual_value"] == 50.0
    assert result["grounding_sources"]["lineage_measured_value"] == 50.0
    assert result["grounding_sources"]["usage_revenue_usd"] == 0.1
    assert result["grounding_sources"]["spec_actual_value_sum"] == 2.0


def test_idea_metrics_zero_when_no_data() -> None:
    # Strangest edge: an idea no service knows about. All zeros, confidence
    # is floored to 0.05 (never zero) — that's the documented clamp.
    result = compute_idea_metrics("idea-ghost")
    assert result["computed_actual_cost"] == 0.0
    assert result["computed_actual_value"] == 0.0
    assert result["computed_confidence"] == 0.05


# ---------------------------------------------------------------------------
# Requirement: prompt_variant gates recording + raw signals stored
# ---------------------------------------------------------------------------

def test_record_skipped_when_no_prompt_variant(tmp_path: Path) -> None:
    task = {"context": {}, "task_type": "impl"}
    result = record_grounded_measurement(
        task_id="task-1",
        task=task,
        status="completed",
        elapsed_ms=100,
        actual_cost_usd=0.001,
        runtime_cost_estimate=0.0005,
        store_path=tmp_path / "ab.json",
    )
    assert result is None


def test_record_skipped_when_context_missing(tmp_path: Path) -> None:
    # Task with no context dict at all -> also skipped.
    task = {"task_type": "impl"}
    result = record_grounded_measurement(
        task_id="task-2",
        task=task,
        status="completed",
        elapsed_ms=100,
        actual_cost_usd=0.001,
        runtime_cost_estimate=0.0005,
        store_path=tmp_path / "ab.json",
    )
    assert result is None


def test_record_stores_raw_signals_alongside_score(tmp_path: Path) -> None:
    # A measurement that DOES get recorded carries the full raw_signals
    # block (req 4). One retry -> quality_multiplier=0.7 should appear.
    task = {
        "context": {
            "prompt_variant": "prompt-v2",
            "retry_count": 1,
            # no idea_id -> economic layer collapses to execution quality
        },
        "task_type": "impl",
    }
    store = tmp_path / "ab.json"
    result = record_grounded_measurement(
        task_id="task-abc",
        task=task,
        status="completed",
        elapsed_ms=9200,
        actual_cost_usd=0.0034,
        runtime_cost_estimate=0.0018,
        output_metrics={"confidence": 0.9},
        store_path=store,
    )
    assert result is not None
    assert result["variant_id"] == "prompt-v2"
    assert result["task_type"] == "impl"
    # Cost: actual present and > 0 -> wins over estimate
    assert result["resource_cost"] == 0.0034
    # Value: 1.0 outcome * 0.7 quality * 0.9 confidence = 0.63
    assert abs(result["value_score"] - 0.63) < 1e-9
    raw = result["raw_signals"]
    # Every documented raw_signals key must be present
    for key in (
        "status",
        "actual_cost_usd",
        "runtime_cost_estimate",
        "runtime_ms",
        "confidence",
        "retry_count",
        "heal_attempt",
        "outcome_signal",
        "quality_multiplier",
        "confidence_weight",
        "execution_quality",
        "idea_id",
        "idea_signals",
        "economic_breakdown",
    ):
        assert key in raw, f"raw_signals missing key {key}"
    assert raw["quality_multiplier"] == 0.7
    assert raw["confidence_weight"] == 0.9
    assert raw["status"] == "completed"
