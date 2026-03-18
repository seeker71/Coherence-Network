"""Grounded cost & value measurement for prompt A/B ROI (spec 115).

Computes cost and value from observable signals — not self-reported scores.

COST is fully grounded:
  actual_cost_usd (provider billing) or runtime_cost_estimate (elapsed × rate).

VALUE has two layers:
  1. Execution quality: did the task complete? how many retries?
  2. Economic value: does the idea this task serves have real-world value signals?
     - Usage revenue: API calls × fee per request
     - Adoption: endpoint hit count for the idea
     - Value gap closure: Idea.actual_value rising toward potential_value
     - Friction reduction: cost_of_delay saved

Every measurement stores raw signals so the formula can be recalibrated
without recollecting data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services import prompt_ab_roi_service

_log = logging.getLogger(__name__)

# Quality multiplier by retry count — first attempt is full value,
# retries degrade it because rework consumed resources.
_QUALITY_BY_RETRIES: dict[int, float] = {
    0: 1.0,
    1: 0.7,
    2: 0.4,
}
_QUALITY_MAX_RETRIES = 0.2  # 3+ retries

# Revenue per API request from ECONOMIC_MODEL.md
_REVENUE_PER_REQUEST: float = 0.001  # USD


def compute_grounded_cost(
    actual_cost_usd: float | None,
    runtime_cost_estimate: float,
) -> float:
    """Return real cost from provider billing, falling back to infra cost.

    Both inputs are measured values — no estimation or self-reporting.
    actual_cost_usd: from provider billing response (may be None for free tier).
    runtime_cost_estimate: elapsed_ms * rate_per_second (always available).
    """
    if actual_cost_usd is not None and actual_cost_usd > 0:
        return actual_cost_usd
    # runtime_cost_estimate is always computed from real elapsed_ms
    if runtime_cost_estimate > 0:
        return runtime_cost_estimate
    # Absolute floor — cost is never zero (CPU time was spent)
    return 0.0001


def compute_grounded_value(
    status: str,
    retry_count: int = 0,
    heal_attempt: bool = False,
    heal_succeeded: bool | None = None,
    confidence: float | None = None,
) -> tuple[float, dict[str, float]]:
    """Compute execution quality score from observable task outcomes.

    This is layer 1 of value: did the task execute well?
    Returns (quality_score, breakdown) where quality_score is 0.0-1.0.
    """
    # Outcome signal: binary pass/fail
    outcome_signal = 1.0 if status == "completed" else 0.0

    # Quality multiplier: penalize retries
    if retry_count in _QUALITY_BY_RETRIES:
        quality_multiplier = _QUALITY_BY_RETRIES[retry_count]
    else:
        quality_multiplier = _QUALITY_MAX_RETRIES

    # If healed but heal also failed, value is zero
    if heal_attempt and heal_succeeded is False:
        quality_multiplier = 0.0

    # Confidence weight: from task output, clamped to [0.1, 1.0]
    # Default 1.0 when not available (don't penalize tasks that don't report it)
    if confidence is not None:
        confidence_weight = max(0.1, min(1.0, confidence))
    else:
        confidence_weight = 1.0

    value_score = outcome_signal * quality_multiplier * confidence_weight

    breakdown = {
        "outcome_signal": outcome_signal,
        "quality_multiplier": quality_multiplier,
        "confidence_weight": confidence_weight,
    }
    return value_score, breakdown


# ---------------------------------------------------------------------------
# Layer 2: Economic value from idea-level observable signals
# ---------------------------------------------------------------------------


def collect_idea_value_signals(idea_id: str | None) -> dict[str, Any]:
    """Collect real economic value signals for an idea.

    Returns a dict of observable signals with their sources.
    Every value here is either directly measured or derived from
    measured data — nothing is self-reported.

    If idea_id is None or services are unavailable, returns empty
    signals (no value attribution possible).
    """
    signals: dict[str, Any] = {
        "idea_id": idea_id,
        "usage_event_count": 0,
        "usage_revenue_usd": 0.0,
        "actual_value_usd": 0.0,
        "potential_value_usd": 0.0,
        "value_gap_usd": 0.0,
        "value_realization_pct": 0.0,
        "friction_cost_of_delay_usd": 0.0,
        "sources": [],
    }

    if not idea_id:
        return signals

    # Source 1: Idea model — actual_value and potential_value
    try:
        from app.services import idea_service
        idea = idea_service.get_idea(idea_id)
        if idea:
            signals["actual_value_usd"] = idea.get("actual_value", 0.0) if isinstance(idea, dict) else getattr(idea, "actual_value", 0.0)
            signals["potential_value_usd"] = idea.get("potential_value", 0.0) if isinstance(idea, dict) else getattr(idea, "potential_value", 0.0)
            signals["value_gap_usd"] = max(0.0, signals["potential_value_usd"] - signals["actual_value_usd"])
            if signals["potential_value_usd"] > 0:
                signals["value_realization_pct"] = round(
                    signals["actual_value_usd"] / signals["potential_value_usd"], 4
                )
            signals["sources"].append("idea_model")
    except Exception:
        _log.debug("idea_service unavailable for value signals", exc_info=True)

    # Source 2: Runtime events — API call count for this idea = usage volume
    try:
        from app.services import runtime_service
        summary = runtime_service.get_idea_runtime_summary(idea_id)
        if summary:
            event_count = summary.get("event_count", 0) if isinstance(summary, dict) else getattr(summary, "event_count", 0)
            signals["usage_event_count"] = event_count
            signals["usage_revenue_usd"] = round(event_count * _REVENUE_PER_REQUEST, 6)
            signals["sources"].append("runtime_events")
    except Exception:
        _log.debug("runtime_service unavailable for usage signals", exc_info=True)

    # Source 3: Value lineage — measured_value_total from usage events
    try:
        from app.services import value_lineage_service
        valuations = value_lineage_service.get_valuations_for_idea(idea_id)
        if valuations:
            total_measured = sum(
                v.get("measured_value_total", 0.0) if isinstance(v, dict) else getattr(v, "measured_value_total", 0.0)
                for v in valuations
            )
            if total_measured > 0:
                signals["lineage_measured_value_usd"] = total_measured
                signals["sources"].append("value_lineage")
    except Exception:
        _log.debug("value_lineage_service unavailable", exc_info=True)

    # Source 4: Friction — cost_of_delay for unresolved friction on this idea
    try:
        from app.services import friction_service
        friction_events = friction_service.get_friction_events_for_idea(idea_id)
        if friction_events:
            total_cost_of_delay = sum(
                f.get("cost_of_delay", 0.0) if isinstance(f, dict) else getattr(f, "cost_of_delay", 0.0)
                for f in friction_events
            )
            signals["friction_cost_of_delay_usd"] = round(total_cost_of_delay, 4)
            signals["sources"].append("friction_events")
    except Exception:
        _log.debug("friction_service unavailable for cost_of_delay", exc_info=True)

    return signals


def compute_economic_value_score(
    execution_quality: float,
    idea_signals: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Combine execution quality with economic signals into a final value score.

    The formula weights real economic signals when available, falling back
    to execution quality alone when no idea-level data exists.

    Returns (value_score, breakdown) clamped to [0.0, 1.0].
    """
    sources = idea_signals.get("sources", [])

    if not sources:
        # No idea-level data — execution quality is all we have.
        # This is honest: we don't inflate value when we can't measure it.
        return execution_quality, {
            "execution_quality": execution_quality,
            "economic_weight": 0.0,
            "has_idea_signals": False,
        }

    # When we have idea-level signals, blend them with execution quality.
    # Execution quality gates the value: a failed task produces nothing
    # regardless of how valuable the idea is.
    if execution_quality == 0.0:
        return 0.0, {
            "execution_quality": 0.0,
            "economic_weight": 0.0,
            "has_idea_signals": True,
            "gated_by_failure": True,
        }

    # Economic signals — each contributes evidence of real value.
    # We normalize to 0-1 range and take the strongest signal.
    economic_evidence: list[tuple[str, float]] = []

    # Usage adoption: >0 API calls = someone uses this feature
    usage_count = idea_signals.get("usage_event_count", 0)
    if usage_count > 0:
        # Log scale: 1 call = 0.1, 10 calls = 0.5, 100+ calls = 0.9+
        import math
        adoption_score = min(1.0, 0.1 + 0.4 * math.log10(max(1, usage_count)))
        economic_evidence.append(("adoption", adoption_score))

    # Value realization: how much of potential_value has been realized
    realization = idea_signals.get("value_realization_pct", 0.0)
    if realization > 0:
        economic_evidence.append(("value_realization", min(1.0, realization)))

    # Revenue signal: actual dollars earned
    revenue = idea_signals.get("usage_revenue_usd", 0.0)
    lineage_value = idea_signals.get("lineage_measured_value_usd", 0.0)
    total_revenue = revenue + lineage_value
    if total_revenue > 0:
        # Normalize: $0.01 = 0.2, $0.10 = 0.5, $1.00 = 0.8, $10+ = 1.0
        import math
        revenue_score = min(1.0, 0.2 + 0.3 * math.log10(max(0.01, total_revenue * 100)))
        economic_evidence.append(("revenue", revenue_score))

    # Friction cost avoidance: high cost_of_delay = high urgency = high value if fixed
    friction_cost = idea_signals.get("friction_cost_of_delay_usd", 0.0)
    if friction_cost > 0:
        import math
        # $1 delay = 0.2, $10 = 0.5, $100+ = 0.9
        friction_value = min(1.0, 0.2 + 0.3 * math.log10(max(1, friction_cost)))
        economic_evidence.append(("friction_avoidance", friction_value))

    if not economic_evidence:
        # Idea exists but no measurable economic signal yet.
        # Slight boost over bare execution quality to credit idea linkage.
        return execution_quality, {
            "execution_quality": execution_quality,
            "economic_weight": 0.0,
            "has_idea_signals": True,
            "no_economic_evidence": True,
        }

    # Take the strongest economic signal (max, not average — one strong
    # signal is sufficient evidence of real value)
    strongest_name, strongest_score = max(economic_evidence, key=lambda x: x[1])

    # Blend: execution quality gates, economic signal amplifies
    # Formula: exec_quality * (0.4 + 0.6 * economic_signal)
    # This means:
    #   - Perfect execution + zero economic signal = 0.4 (base credit for completing work)
    #   - Perfect execution + strong economic signal = 1.0 (full value)
    #   - Failed execution = always 0.0
    blended = execution_quality * (0.4 + 0.6 * strongest_score)
    final = min(1.0, max(0.0, blended))

    breakdown = {
        "execution_quality": execution_quality,
        "economic_weight": strongest_score,
        "economic_signal_source": strongest_name,
        "has_idea_signals": True,
        "all_evidence": {name: score for name, score in economic_evidence},
    }

    return final, breakdown


def record_grounded_measurement(
    task_id: str,
    task: dict[str, Any],
    status: str,
    elapsed_ms: int,
    actual_cost_usd: float | None,
    runtime_cost_estimate: float,
    output_metrics: dict[str, float | None] | None = None,
    *,
    store_path: Path | None = None,
) -> dict | None:
    """Record a grounded A/B measurement from real task execution signals.

    Returns the measurement dict, or None if the task has no prompt_variant
    (not part of an A/B test).
    """
    context = task.get("context") if isinstance(task.get("context"), dict) else {}

    # Only record if this task is part of an A/B test
    variant_id = context.get("prompt_variant")
    if not variant_id:
        return None

    task_type = task.get("task_type", "unknown")
    if hasattr(task_type, "value"):
        task_type = task_type.value

    # Extract signals from context and output
    retry_count = int(context.get("retry_count", 0))
    heal_attempt = bool(context.get("heal_task_id"))
    heal_succeeded = context.get("heal_succeeded")  # None if no heal
    confidence = None
    if output_metrics:
        conf_raw = output_metrics.get("confidence")
        if conf_raw is not None:
            try:
                confidence = float(conf_raw)
            except (TypeError, ValueError):
                pass

    # --- Layer 1: Grounded cost ---
    cost = compute_grounded_cost(actual_cost_usd, runtime_cost_estimate)

    # --- Layer 2: Execution quality ---
    exec_quality, exec_breakdown = compute_grounded_value(
        status=status,
        retry_count=retry_count,
        heal_attempt=heal_attempt,
        heal_succeeded=heal_succeeded,
        confidence=confidence,
    )

    # --- Layer 3: Economic value from idea signals ---
    idea_id = context.get("idea_id")
    idea_signals = collect_idea_value_signals(idea_id)
    value, econ_breakdown = compute_economic_value_score(exec_quality, idea_signals)

    # Build raw signals for future recalibration
    raw_signals = {
        # Execution signals
        "status": status,
        "actual_cost_usd": actual_cost_usd,
        "runtime_cost_estimate": runtime_cost_estimate,
        "runtime_ms": elapsed_ms,
        "confidence": confidence,
        "retry_count": retry_count,
        "heal_attempt": heal_attempt,
        "heal_succeeded": heal_succeeded,
        # Execution quality breakdown
        "outcome_signal": exec_breakdown["outcome_signal"],
        "quality_multiplier": exec_breakdown["quality_multiplier"],
        "confidence_weight": exec_breakdown["confidence_weight"],
        "execution_quality": exec_quality,
        # Economic signals
        "idea_id": idea_id,
        "idea_signals": idea_signals,
        "economic_breakdown": econ_breakdown,
    }

    # Record through the existing ROI service with real numbers + raw signals
    kwargs: dict[str, Any] = {}
    if store_path:
        kwargs["store_path"] = store_path

    measurement = prompt_ab_roi_service.record_prompt_outcome(
        variant_id=variant_id,
        task_type=task_type,
        value_score=value,
        resource_cost=cost,
        task_id=task_id,
        raw_signals=raw_signals,
        **kwargs,
    )

    return measurement
