"""Friction actionability helpers (semantic domains + ROI heuristics)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable

from app.models.friction import FrictionEvent


def semantic_domain_for_entry(*, key: str, title: str, recommended_action: str) -> str:
    text = f"{key} {title} {recommended_action}".lower()
    if any(token in text for token in ("auth", "oauth", "token", "session")):
        return "auth_stability"
    if any(token in text for token in ("orphan", "runner", "heartbeat", "stale_running")):
        return "runner_stability"
    if any(
        token in text
        for token in ("provider", "readiness", "openrouter", "openai", "cursor", "railway", "quota", "limit")
    ):
        return "provider_readiness"
    if key.startswith("failed-tasks:") or "tool_failure" in text or "task_failure" in text:
        return "execution_quality"
    if any(token in text for token in ("spec", "backlog", "queue", "triage", "review")):
        return "spec_first_flow"
    if any(token in text for token in ("github-actions", "workflow", "ci")):
        return "ci_reliability"
    return "flow_friction"


def roi_calibration_by_domain(events: list[FrictionEvent], *, since: datetime) -> dict[str, float]:
    ratios_by_domain: dict[str, list[float]] = defaultdict(list)
    for event in events:
        if event.timestamp < since or str(event.status).strip().lower() != "resolved":
            continue
        estimated = max(0.0, float(event.energy_loss_estimate)) + max(0.0, float(event.cost_of_delay))
        measured = max(0.0, float(event.time_open_hours or 0.0))
        if estimated <= 0.0 or measured <= 0.0:
            continue
        domain = semantic_domain_for_entry(
            key=f"friction:{event.block_type}",
            title=f"Friction block: {event.block_type}",
            recommended_action=event.unblock_condition,
        )
        ratios_by_domain[domain].append(measured / estimated)
    calibrated: dict[str, float] = {}
    for domain, ratios in ratios_by_domain.items():
        if not ratios:
            continue
        mean_ratio = sum(ratios) / len(ratios)
        calibrated[domain] = round(max(0.2, min(mean_ratio, 5.0)), 4)
    return calibrated


def cheap_model_split_hint(*, domain: str, event_count: int, wasted_minutes: float) -> str:
    if event_count >= 5 or wasted_minutes >= 45.0:
        return (
            f"Split {domain} into small specs (detect, policy, verify) so a cheap model can execute each step deterministically."
        )
    return f"Keep {domain} as one scoped spec + one implementation card for cheap-model execution."


def potential_roi(*, event_count: int, energy_loss: float, cost_of_delay: float, wasted_minutes: float, calibration: float) -> float:
    impact = max(0.0, float(energy_loss)) + max(0.0, float(cost_of_delay)) + max(0.0, float(wasted_minutes))
    effort = max(1.0, 0.8 + (0.35 * max(1, int(event_count))))
    return round((impact / effort) * max(0.2, float(calibration or 1.0)), 4)


def build_actionability_fields(entry: dict[str, Any], *, calibration_by_domain: dict[str, float]) -> dict[str, Any]:
    key = str(entry.get("key") or "")
    title = str(entry.get("title") or "")
    recommended_action = str(entry.get("recommended_action") or "Investigate and resolve.")
    event_count = max(0, int(float(entry.get("event_count") or 0)))
    energy_loss = round(max(0.0, float(entry.get("energy_loss") or 0.0)), 4)
    cost_of_delay = round(max(0.0, float(entry.get("cost_of_delay") or 0.0)), 4)
    wasted_minutes = round(max(0.0, float(entry.get("wasted_minutes") or 0.0)), 4)
    domain = semantic_domain_for_entry(
        key=key,
        title=title,
        recommended_action=recommended_action,
    )
    calibration_ratio = calibration_by_domain.get(domain, 1.0)
    return {
        "key": key,
        "title": title,
        "event_count": event_count,
        "energy_loss": energy_loss,
        "cost_of_delay": cost_of_delay,
        "wasted_minutes": wasted_minutes,
        "recommended_action": recommended_action,
        "semantic_domain": domain,
        "potential_roi": potential_roi(
            event_count=event_count,
            energy_loss=energy_loss,
            cost_of_delay=cost_of_delay,
            wasted_minutes=wasted_minutes,
            calibration=calibration_ratio,
        ),
        "roi_estimator": "friction_energy_cost_minutes_v2",
        "roi_calibration_ratio": round(float(calibration_ratio), 4),
        "cheap_model_split_hint": cheap_model_split_hint(
            domain=domain,
            event_count=event_count,
            wasted_minutes=wasted_minutes,
        ),
    }


def default_gap_actionability() -> dict[str, Any]:
    return {
        "semantic_domain": "flow_friction",
        "potential_roi": 0.0,
        "roi_estimator": "friction_energy_cost_minutes_v2",
        "roi_calibration_ratio": 1.0,
        "cheap_model_split_hint": (
            "Create one setup spec (telemetry enablement) and one verification spec so a cheap model can run both."
        ),
    }


def entry_point_category(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        return "unknown"
    if ":" in normalized:
        return normalized.split(":", 1)[0].strip() or "unknown"
    return normalized


def new_category_rollup(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "_severity_rank": 0,
        "entry_point_count": 0,
        "open_entry_points": 0,
        "event_count": 0,
        "energy_loss": 0.0,
        "cost_of_delay": 0.0,
        "wasted_minutes": 0.0,
        "top_entry_keys": [],
        "recommended_actions": [],
    }


def merge_category_rollup(
    category: dict[str, Any],
    row: dict[str, Any],
    *,
    safe_int: Callable[[Any], int],
    safe_float: Callable[[Any], float],
    severity_rank: Callable[[str], int],
) -> None:
    rank = severity_rank(str(row.get("severity") or ""))
    category["_severity_rank"] = max(int(category.get("_severity_rank") or 0), rank)
    category["entry_point_count"] = safe_int(category.get("entry_point_count")) + 1
    if str(row.get("status") or "").strip().lower() == "open":
        category["open_entry_points"] = safe_int(category.get("open_entry_points")) + 1
    category["event_count"] = safe_int(category.get("event_count")) + safe_int(row.get("event_count"))
    category["energy_loss"] = safe_float(category.get("energy_loss")) + safe_float(row.get("energy_loss"))
    category["cost_of_delay"] = safe_float(category.get("cost_of_delay")) + safe_float(row.get("cost_of_delay"))
    category["wasted_minutes"] = safe_float(category.get("wasted_minutes")) + safe_float(row.get("wasted_minutes"))

    entry_key = str(row.get("key") or "").strip()
    if entry_key:
        keys = list(category.get("top_entry_keys") or [])
        if entry_key not in keys:
            keys.append(entry_key)
        category["top_entry_keys"] = keys[:5]

    action = str(row.get("recommended_action") or "").strip()
    if action:
        actions = list(category.get("recommended_actions") or [])
        if action not in actions:
            actions.append(action)
        category["recommended_actions"] = actions[:4]


def render_sorted_category_rows(
    categories: dict[str, dict[str, Any]],
    *,
    safe_int: Callable[[Any], int],
    safe_float: Callable[[Any], float],
    severity_from_rank: Callable[[int], str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in categories.values():
        severity_rank = int(row.get("_severity_rank") or 0)
        rows.append(
            {
                "key": str(row.get("key") or "unknown"),
                "severity": severity_from_rank(severity_rank),
                "entry_point_count": safe_int(row.get("entry_point_count")),
                "open_entry_points": safe_int(row.get("open_entry_points")),
                "event_count": safe_int(row.get("event_count")),
                "energy_loss": round(safe_float(row.get("energy_loss")), 4),
                "cost_of_delay": round(safe_float(row.get("cost_of_delay")), 4),
                "wasted_minutes": round(safe_float(row.get("wasted_minutes")), 4),
                "top_entry_keys": [str(item) for item in (row.get("top_entry_keys") or [])],
                "recommended_actions": [str(item) for item in (row.get("recommended_actions") or [])],
                "_severity_rank": severity_rank,
            }
        )

    rows.sort(
        key=lambda item: (
            int(item.get("_severity_rank") or 0),
            safe_float(item.get("wasted_minutes"))
            + safe_float(item.get("energy_loss"))
            + safe_float(item.get("cost_of_delay")),
            safe_int(item.get("event_count")),
        ),
        reverse=True,
    )
    for row in rows:
        row.pop("_severity_rank", None)
    return rows


def build_category_rows(
    entry_points: list[dict[str, Any]],
    *,
    safe_int: Callable[[Any], int],
    safe_float: Callable[[Any], float],
    severity_rank: Callable[[str], int],
    severity_from_rank: Callable[[int], str],
) -> list[dict[str, Any]]:
    categories: dict[str, dict[str, Any]] = {}
    for row in entry_points:
        key = entry_point_category(str(row.get("key") or ""))
        category = categories.setdefault(key, new_category_rollup(key))
        merge_category_rollup(
            category,
            row,
            safe_int=safe_int,
            safe_float=safe_float,
            severity_rank=severity_rank,
        )
    return render_sorted_category_rows(
        categories,
        safe_int=safe_int,
        safe_float=safe_float,
        severity_from_rank=severity_from_rank,
    )
