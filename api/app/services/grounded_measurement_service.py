"""Grounded cost & value measurement for prompt A/B ROI (spec 115).

Computes cost and value from observable task signals — not self-reported scores.
Every measurement stores raw signals so the scoring formula can be recalibrated
without recollecting data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services import prompt_ab_roi_service

# Quality multiplier by retry count — first attempt is full value,
# retries degrade it because rework consumed resources.
_QUALITY_BY_RETRIES: dict[int, float] = {
    0: 1.0,
    1: 0.7,
    2: 0.4,
}
_QUALITY_MAX_RETRIES = 0.2  # 3+ retries


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
    """Compute value score from observable task outcomes.

    Returns (value_score, breakdown) where breakdown contains the
    individual signal components for auditability.
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

    # Compute grounded cost
    cost = compute_grounded_cost(actual_cost_usd, runtime_cost_estimate)

    # Compute grounded value
    value, breakdown = compute_grounded_value(
        status=status,
        retry_count=retry_count,
        heal_attempt=heal_attempt,
        heal_succeeded=heal_succeeded,
        confidence=confidence,
    )

    # Build raw signals for future recalibration
    raw_signals = {
        "status": status,
        "actual_cost_usd": actual_cost_usd,
        "runtime_cost_estimate": runtime_cost_estimate,
        "runtime_ms": elapsed_ms,
        "confidence": confidence,
        "retry_count": retry_count,
        "heal_attempt": heal_attempt,
        "heal_succeeded": heal_succeeded,
        "outcome_signal": breakdown["outcome_signal"],
        "quality_multiplier": breakdown["quality_multiplier"],
        "confidence_weight": breakdown["confidence_weight"],
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
