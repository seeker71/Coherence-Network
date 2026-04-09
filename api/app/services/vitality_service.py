"""Vitality service — living-system health metrics for a workspace.

Computes biological-metaphor health signals: diversity, resonance density,
flow rate, breath rhythm, connection strength, activity pulse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import graph_service
from app.services import activity_service

log = logging.getLogger(__name__)

# Weights for overall vitality score
_WEIGHTS = {
    "diversity_index": 0.15,
    "resonance_density": 0.15,
    "flow_rate": 0.20,
    "breath_rhythm": 0.15,
    "connection_strength": 0.15,
    "activity_pulse": 0.20,
}


def _simpson_diversity(counts: list[int]) -> float:
    """Simpson's diversity index: 1 - sum(p_i^2).

    Returns 0.0 for no diversity, approaches 1.0 for high diversity.
    """
    total = sum(counts)
    if total <= 0:
        return 0.0
    return 1.0 - sum((c / total) ** 2 for c in counts)


def _breath_balance(gas: int, water: int, ice: int) -> float:
    """Score [0.0, 1.0] for how balanced the three phase states are.

    Perfect balance (equal thirds) = 1.0. All in one phase = 0.0.
    Uses normalized entropy: H / H_max.
    """
    import math

    total = gas + water + ice
    if total == 0:
        return 0.0
    proportions = [gas / total, water / total, ice / total]
    # Shannon entropy
    h = -sum(p * math.log(p) for p in proportions if p > 0)
    h_max = math.log(3)  # max entropy for 3 categories
    return h / h_max if h_max > 0 else 0.0


def compute_vitality(workspace_id: str = "coherence-network") -> dict[str, Any]:
    """Compute workspace vitality — a living-system health score.

    Signals:
    1. diversity_index — Simpson's index over contributor worldview axes
    2. resonance_density — average edge strength across idea edges
    3. flow_rate — fraction of ideas that advanced stage in last 30 days
    4. breath_rhythm — distribution across gas/water/ice phases
    5. connection_strength — average edges per node
    6. activity_pulse — recent activity events (last 7 days)
    7. vitality_score — weighted average of all signals
    """
    now = datetime.now(timezone.utc)

    # ── 1. Diversity index ──
    contributor_result = graph_service.list_nodes(type="contributor", limit=200)
    contributors = contributor_result.get("items", [])

    axis_counts: dict[str, int] = {}
    for c in contributors:
        props = c.get("properties") or c
        axes = props.get("worldview_axes") or {}
        if axes:
            # Find dominant axis
            dominant = max(axes, key=lambda k: float(axes[k]))
            axis_counts[dominant] = axis_counts.get(dominant, 0) + 1
        else:
            axis_counts["_none"] = axis_counts.get("_none", 0) + 1

    diversity_index = _simpson_diversity(list(axis_counts.values())) if axis_counts else 0.0

    # ── 2. Resonance density ──
    edge_result = graph_service.list_edges(limit=200)
    all_edges = edge_result.get("items", [])

    # Average strength of edges
    if all_edges:
        total_strength = sum(float(e.get("strength", 1.0)) for e in all_edges)
        resonance_density = min(1.0, total_strength / len(all_edges))
    else:
        resonance_density = 0.0

    # ── 3. Flow rate ──
    idea_result = graph_service.list_nodes(type="idea", limit=500)
    ideas = idea_result.get("items", [])
    total_ideas = len(ideas)

    # Count ideas updated in last 30 days as proxy for "advanced stage"
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    advanced = 0
    for idea in ideas:
        updated = idea.get("updated_at", "")
        if isinstance(updated, str) and updated >= cutoff_30d:
            advanced += 1

    flow_rate = advanced / total_ideas if total_ideas > 0 else 0.0
    flow_rate = min(1.0, flow_rate)

    # ── 4. Breath rhythm ──
    gas_count = 0
    water_count = 0
    ice_count = 0
    for idea in ideas:
        phase = idea.get("phase", "gas")
        lifecycle = idea.get("lifecycle_state", phase)
        state = lifecycle or phase or "gas"
        if state == "gas":
            gas_count += 1
        elif state == "water":
            water_count += 1
        elif state == "ice":
            ice_count += 1
        else:
            gas_count += 1  # default unknown to gas (exploratory)

    breath_total = gas_count + water_count + ice_count
    breath_rhythm = {
        "gas": round(gas_count / breath_total, 4) if breath_total > 0 else 0.0,
        "water": round(water_count / breath_total, 4) if breath_total > 0 else 0.0,
        "ice": round(ice_count / breath_total, 4) if breath_total > 0 else 0.0,
    }
    breath_score = _breath_balance(gas_count, water_count, ice_count)

    # ── 5. Connection strength ──
    # Average edges per node across all node types
    node_count_result = graph_service.count_nodes()
    total_node_count = node_count_result.get("total", 0)
    total_edge_count = len(all_edges)

    if total_node_count > 0:
        avg_edges = total_edge_count / total_node_count
        connection_strength = min(1.0, avg_edges / 5.0)  # normalize: 5 edges/node = 1.0
    else:
        connection_strength = 0.0

    # ── 6. Activity pulse ──
    events_7d = activity_service.list_events(
        workspace_id=workspace_id,
        limit=500,
        offset=0,
    )
    # Filter to last 7 days
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    recent_events = [
        e for e in events_7d
        if isinstance(e.get("created_at", ""), str) and e.get("created_at", "") >= cutoff_7d
    ]
    event_count = len(recent_events)
    # Normalize: 20 events in 7 days = pulse of 1.0
    activity_pulse = min(1.0, event_count / 20.0)

    # ── 7. Overall vitality score ──
    vitality_score = (
        _WEIGHTS["diversity_index"] * diversity_index
        + _WEIGHTS["resonance_density"] * resonance_density
        + _WEIGHTS["flow_rate"] * flow_rate
        + _WEIGHTS["breath_rhythm"] * breath_score
        + _WEIGHTS["connection_strength"] * connection_strength
        + _WEIGHTS["activity_pulse"] * activity_pulse
    )
    vitality_score = round(min(1.0, max(0.0, vitality_score)), 4)

    # ── Health description ──
    if vitality_score >= 0.7:
        health_description = (
            "Thriving — diverse contributors, flowing ideas, strong connections"
        )
    elif vitality_score >= 0.4:
        health_description = (
            "Growing — some areas active, others dormant. "
            "Needs more diverse contributors or flowing ideas."
        )
    else:
        health_description = (
            "Germinating — early stage. "
            "Plant seeds by creating ideas and inviting contributors."
        )

    return {
        "workspace_id": workspace_id,
        "vitality_score": vitality_score,
        "signals": {
            "diversity_index": round(diversity_index, 4),
            "resonance_density": round(resonance_density, 4),
            "flow_rate": round(flow_rate, 4),
            "breath_rhythm": breath_rhythm,
            "connection_strength": round(connection_strength, 4),
            "activity_pulse": round(activity_pulse, 4),
        },
        "health_description": health_description,
        "generated_at": now.isoformat(),
    }
