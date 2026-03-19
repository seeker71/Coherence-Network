"""Grounded idea portfolio metrics — replace hand-typed numbers with real data.

Spec 116: Computes actual_cost, actual_value, and confidence for each idea
from observable data already flowing through the system:
- spec_registry_service: per-spec actual_cost, actual_value, estimated_cost
- runtime_service: usage adoption counts, runtime cost per idea
- value_lineage_service: measured value from usage events
- telemetry_persistence_service: friction cost_of_delay
- commit_evidence_service: commit-level cost evidence
"""

from __future__ import annotations

import math
from typing import Any

# Revenue per API request from ECONOMIC_MODEL.md
_REVENUE_PER_REQUEST = 0.001

# Confidence weights for data coverage scoring
_WEIGHT_SPECS = 0.30
_WEIGHT_RUNTIME = 0.25
_WEIGHT_LINEAGE = 0.25
_WEIGHT_COMMITS = 0.10
_WEIGHT_FRICTION = 0.10


def compute_idea_metrics(
    idea_id: str,
    *,
    specs: list[Any] | None = None,
    runtime_summaries: list[Any] | None = None,
    lineage_links: list[Any] | None = None,
    lineage_valuations: dict[str, Any] | None = None,
    commit_records: list[dict[str, Any]] | None = None,
    friction_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute grounded metrics for a single idea from real data sources.

    All inputs are pre-fetched data from existing services. This function is a
    pure computation — no I/O, no service calls, no side effects.

    Args:
        idea_id: The idea to compute metrics for.
        specs: SpecRegistryEntry objects (or dicts with actual_cost, actual_value, etc.)
        runtime_summaries: IdeaRuntimeSummary objects (or dicts with event_count, runtime_cost_estimate)
        lineage_links: LineageLink objects (or dicts with idea_id, id, estimated_cost)
        lineage_valuations: Dict mapping lineage_id -> LineageValuation (or dict with measured_value_total)
        commit_records: Dicts with idea_ids list, change_files, lines_added
        friction_events: Dicts with idea_id, cost_of_delay fields
    """
    specs = specs or []
    runtime_summaries = runtime_summaries or []
    lineage_links = lineage_links or []
    lineage_valuations = lineage_valuations or {}
    commit_records = commit_records or []
    friction_events = friction_events or []

    # --- Filter to this idea ---
    idea_specs = _filter_by_idea_id(specs, idea_id)
    idea_runtime = _find_runtime_summary(runtime_summaries, idea_id)
    idea_links = _filter_by_idea_id(lineage_links, idea_id)
    idea_commits = _filter_commits_by_idea(commit_records, idea_id)
    idea_friction = _filter_by_idea_id(friction_events, idea_id)

    # --- Compute actual cost (grounded) ---
    spec_actual_cost_sum = sum(_safe_float(s, "actual_cost") for s in idea_specs)
    spec_estimated_cost_sum = sum(_safe_float(s, "estimated_cost") for s in idea_specs)
    runtime_cost = _safe_float(idea_runtime, "runtime_cost_estimate") if idea_runtime else 0.0
    commit_cost_sum = _estimate_commit_cost_sum(idea_commits)
    lineage_estimated_cost = sum(_safe_float(l, "estimated_cost") for l in idea_links)

    computed_actual_cost = spec_actual_cost_sum + runtime_cost + commit_cost_sum

    # --- Compute actual value (grounded — strongest signal wins) ---
    spec_actual_value_sum = sum(_safe_float(s, "actual_value") for s in idea_specs)

    runtime_event_count = 0
    if idea_runtime:
        runtime_event_count = _safe_int(idea_runtime, "event_count")
    usage_revenue = runtime_event_count * _REVENUE_PER_REQUEST

    lineage_measured_value = 0.0
    lineage_event_count = 0
    for link in idea_links:
        link_id = _safe_str(link, "id")
        val = lineage_valuations.get(link_id)
        if val:
            lineage_measured_value += _safe_float(val, "measured_value_total")
            lineage_event_count += _safe_int(val, "event_count")

    friction_cost_of_delay = sum(
        _safe_float(e, "cost_of_delay") for e in idea_friction
    )

    # Strongest signal determines actual value
    computed_actual_value = max(
        lineage_measured_value,
        usage_revenue,
        spec_actual_value_sum,
    )

    # --- Compute estimated cost (grounded where possible) ---
    computed_estimated_cost = max(spec_estimated_cost_sum, lineage_estimated_cost)

    # --- Compute value realization ---
    spec_potential_value_sum = sum(_safe_float(s, "potential_value") for s in idea_specs)
    value_realization_pct = 0.0
    if spec_potential_value_sum > 0:
        value_realization_pct = min(computed_actual_value / spec_potential_value_sum, 1.0)

    # --- Compute confidence (data coverage) ---
    has_specs_with_data = 1.0 if any(
        _safe_float(s, "actual_cost") > 0 or _safe_float(s, "actual_value") > 0
        for s in idea_specs
    ) else (0.5 if len(idea_specs) > 0 else 0.0)

    has_runtime_data = min(1.0, runtime_event_count / 10.0) if runtime_event_count > 0 else 0.0
    has_lineage = 1.0 if lineage_measured_value > 0 else (0.5 if len(idea_links) > 0 else 0.0)
    has_commits = min(1.0, len(idea_commits) / 5.0) if idea_commits else 0.0
    has_friction = 1.0 if friction_cost_of_delay > 0 else (0.3 if idea_friction else 0.0)

    computed_confidence = (
        has_specs_with_data * _WEIGHT_SPECS
        + has_runtime_data * _WEIGHT_RUNTIME
        + has_lineage * _WEIGHT_LINEAGE
        + has_commits * _WEIGHT_COMMITS
        + has_friction * _WEIGHT_FRICTION
    )
    # Clamp to [0.05, 0.95] — never fully certain, never zero
    computed_confidence = max(0.05, min(0.95, computed_confidence))

    return {
        "idea_id": idea_id,
        "computed_actual_cost": round(computed_actual_cost, 4),
        "computed_actual_value": round(computed_actual_value, 4),
        "computed_estimated_cost": round(computed_estimated_cost, 4),
        "computed_confidence": round(computed_confidence, 4),
        "value_realization_pct": round(value_realization_pct, 4),
        "grounding_sources": {
            "spec_count": len(idea_specs),
            "spec_actual_cost_sum": round(spec_actual_cost_sum, 4),
            "spec_actual_value_sum": round(spec_actual_value_sum, 4),
            "spec_estimated_cost_sum": round(spec_estimated_cost_sum, 4),
            "spec_potential_value_sum": round(spec_potential_value_sum, 4),
            "runtime_event_count": runtime_event_count,
            "runtime_cost_estimate": round(runtime_cost, 4),
            "usage_revenue_usd": round(usage_revenue, 4),
            "lineage_measured_value": round(lineage_measured_value, 4),
            "lineage_link_count": len(idea_links),
            "lineage_event_count": lineage_event_count,
            "commit_count": len(idea_commits),
            "commit_cost_sum": round(commit_cost_sum, 4),
            "friction_cost_of_delay": round(friction_cost_of_delay, 4),
            "friction_event_count": len(idea_friction),
        },
    }


def compute_all_idea_metrics(
    idea_ids: list[str],
    *,
    specs: list[Any] | None = None,
    runtime_summaries: list[Any] | None = None,
    lineage_links: list[Any] | None = None,
    lineage_valuations: dict[str, Any] | None = None,
    commit_records: list[dict[str, Any]] | None = None,
    friction_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compute grounded metrics for all ideas in a single pass.

    Data is fetched once and shared across all idea computations.
    """
    return [
        compute_idea_metrics(
            idea_id,
            specs=specs,
            runtime_summaries=runtime_summaries,
            lineage_links=lineage_links,
            lineage_valuations=lineage_valuations,
            commit_records=commit_records,
            friction_events=friction_events,
        )
        for idea_id in idea_ids
    ]


def collect_all_data() -> dict[str, Any]:
    """Collect all data from upstream services for metric computation.

    This is the only function that performs I/O. It calls existing service APIs
    and returns raw data for compute_idea_metrics to process.

    Returns dict with keys: specs, runtime_summaries, lineage_links,
    lineage_valuations, commit_records, friction_events.
    """
    data: dict[str, Any] = {
        "specs": [],
        "runtime_summaries": [],
        "lineage_links": [],
        "lineage_valuations": {},
        "commit_records": [],
        "friction_events": [],
    }

    # Source 1: Spec registry
    try:
        from app.services import spec_registry_service
        data["specs"] = spec_registry_service.list_specs(limit=1000)
    except Exception:
        pass

    # Source 2: Runtime telemetry (last 24 hours)
    try:
        from app.services import runtime_service
        data["runtime_summaries"] = runtime_service.summarize_by_idea(seconds=86400)
    except Exception:
        pass

    # Source 3: Value lineage
    try:
        from app.services import value_lineage_service
        links = value_lineage_service.list_links(limit=500)
        data["lineage_links"] = links
        valuations: dict[str, Any] = {}
        for link in links:
            link_id = _safe_str(link, "id")
            if link_id:
                try:
                    val = value_lineage_service.valuation(link_id)
                    if val:
                        valuations[link_id] = val
                except Exception:
                    pass
        data["lineage_valuations"] = valuations
    except Exception:
        pass

    # Source 4: Commit evidence
    try:
        from app.services import commit_evidence_service
        data["commit_records"] = commit_evidence_service.list_records(limit=2000)
    except Exception:
        pass

    # Source 5: Friction events
    try:
        from app.services import telemetry_persistence_service
        data["friction_events"] = telemetry_persistence_service.list_friction_events(
            limit=1000
        )
    except Exception:
        pass

    return data


# --- Internal helpers ---

def _safe_float(obj: Any, field: str) -> float:
    """Extract a float field from an object or dict, defaulting to 0.0."""
    if obj is None:
        return 0.0
    if isinstance(obj, dict):
        val = obj.get(field, 0.0)
    else:
        val = getattr(obj, field, 0.0)
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(obj: Any, field: str) -> int:
    """Extract an int field from an object or dict, defaulting to 0."""
    if obj is None:
        return 0
    if isinstance(obj, dict):
        val = obj.get(field, 0)
    else:
        val = getattr(obj, field, 0)
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_str(obj: Any, field: str) -> str:
    """Extract a string field from an object or dict, defaulting to ''."""
    if obj is None:
        return ""
    if isinstance(obj, dict):
        val = obj.get(field, "")
    else:
        val = getattr(obj, field, "")
    return str(val) if val is not None else ""


def _filter_by_idea_id(items: list[Any], idea_id: str) -> list[Any]:
    """Filter items that have idea_id matching the target."""
    result = []
    for item in items:
        item_idea = _safe_str(item, "idea_id")
        if item_idea == idea_id:
            result.append(item)
    return result


def _find_runtime_summary(summaries: list[Any], idea_id: str) -> Any | None:
    """Find the runtime summary for a specific idea."""
    for s in summaries:
        if _safe_str(s, "idea_id") == idea_id:
            return s
    return None


def _filter_commits_by_idea(records: list[dict[str, Any]], idea_id: str) -> list[dict[str, Any]]:
    """Filter commit evidence records that reference the target idea.

    Commit records have idea_ids as a list field.
    """
    result = []
    for rec in records:
        # Records may be raw dicts with idea_ids list, or have payload with idea_ids
        idea_ids = rec.get("idea_ids", [])
        if not idea_ids and "payload" in rec:
            payload = rec["payload"]
            if isinstance(payload, dict):
                idea_ids = payload.get("idea_ids", [])
        if isinstance(idea_ids, list) and idea_id in idea_ids:
            result.append(rec)
    return result


def _estimate_commit_cost_sum(commits: list[dict[str, Any]]) -> float:
    """Estimate total cost from commit evidence records.

    Uses contribution_cost_service formula: BASE + files*0.15 + lines*0.002
    but as a pure function to avoid import overhead.
    """
    BASE_COST = 0.10
    PER_FILE = 0.15
    PER_LINE = 0.002
    MIN_COST = 0.05
    MAX_COST = 10.0

    total = 0.0
    for rec in commits:
        files = rec.get("change_files", 0) or 0
        lines = rec.get("lines_added", 0) or 0
        # Also check payload for nested structure
        if files == 0 and "payload" in rec:
            payload = rec["payload"] if isinstance(rec.get("payload"), dict) else {}
            files = payload.get("change_files", 0) or 0
            lines = payload.get("lines_added", 0) or 0
        try:
            files = max(0, int(files))
            lines = max(0, int(lines))
        except (TypeError, ValueError):
            files, lines = 0, 0

        cost = BASE_COST + files * PER_FILE + lines * PER_LINE
        cost = max(MIN_COST, min(MAX_COST, cost))
        total += cost
    return total
