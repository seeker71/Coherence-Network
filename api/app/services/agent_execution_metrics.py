"""Cost and output metric helpers for agent execution."""

from __future__ import annotations

from typing import Any

from app.services import agent_execution_service as execution_service


def resolve_cost_controls(
    task: dict[str, Any],
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> dict[str, float | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    context_max_cost = execution_service._normalize_positive_float(ctx.get("max_cost_usd")) or execution_service._normalize_positive_float(
        ctx.get("max_cost")
    )
    context_estimated_cost = execution_service._normalize_positive_float(ctx.get("estimated_cost_usd")) or execution_service._normalize_positive_float(
        ctx.get("estimated_cost")
    )
    context_slack = execution_service._normalize_ratio(ctx.get("cost_slack_ratio"), default=1.25)

    env_max_cost = execution_service._normalize_positive_float(execution_service.os.getenv("AGENT_TASK_MAX_COST_USD"))
    env_estimated_cost = execution_service._normalize_positive_float(execution_service.os.getenv("AGENT_TASK_ESTIMATED_COST_USD"))
    env_slack = execution_service._normalize_ratio(execution_service.os.getenv("AGENT_TASK_COST_SLACK_RATIO"), default=1.25)

    resolved_max_cost = execution_service._normalize_positive_float(max_cost_usd) or context_max_cost or env_max_cost
    resolved_estimated_cost = (
        execution_service._normalize_positive_float(estimated_cost_usd)
        or context_estimated_cost
        or env_estimated_cost
    )
    resolved_slack = execution_service._normalize_ratio(cost_slack_ratio, default=context_slack or env_slack or 1.25)

    if resolved_max_cost is None and resolved_estimated_cost is not None:
        resolved_max_cost = max(resolved_estimated_cost * resolved_slack, 0.0001)

    return {
        "max_cost_usd": resolved_max_cost,
        "estimated_cost_usd": resolved_estimated_cost,
        "cost_slack_ratio": resolved_slack,
    }


def _safe_parse_output_metrics(output: str) -> dict[str, Any]:
    try:
        parsed = execution_service.json.loads(output)
    except execution_service.json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _extract_output_metric(parsed: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in parsed:
            continue
        raw = parsed.get(key)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value < 0.0:
            continue
        return value
    return None


def attribution_values_from_output(output: str) -> dict[str, float | None]:
    parsed = _safe_parse_output_metrics(output)
    if not parsed:
        return {}

    return {
        "actual_value": _extract_output_metric(
            parsed, ("actual_value", "actual_value_to_whole", "actual_impact")
        ),
        "confidence": _extract_output_metric(parsed, ("confidence",)),
        "estimated_value": _extract_output_metric(
            parsed, ("estimated_value", "estimated_value_to_whole", "potential_value")
        ),
        "estimated_cost": _extract_output_metric(
            parsed, ("estimated_cost", "estimated_cost_usd", "estimated_budget", "cost_budget")
        ),
        "actual_cost": _extract_output_metric(parsed, ("actual_cost", "actual_cost_usd", "cost_actual")),
    }
