"""Breath Service — gas/water/ice phase distribution per idea.

Tracks the lifecycle breath of each super-idea by classifying its specs
into gas (exploratory), water (flowing), and ice (crystallized) phases.

Key metrics:
- rhythm: proportion of specs in each phase
- breath_health: Shannon entropy normalized to [0,1]
- state: breathing/inhaling/exhaling/holding
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _classify_spec(spec) -> str:
    """Classify a spec into gas, water, or ice phase.

    - gas (exploratory): no implementation_summary, or status looks active/early
    - water (flowing): has process_summary but not fully done
    - ice (crystallized): has actual_value > 0 and implementation_summary
    """
    impl = getattr(spec, "implementation_summary", None) or ""
    process = getattr(spec, "process_summary", None) or ""
    actual_value = getattr(spec, "actual_value", 0) or 0

    if actual_value > 0 and impl:
        return "ice"
    if process or impl:
        return "water"
    return "gas"


def _shannon_entropy_normalized(gas: int, water: int, ice: int) -> float:
    """Compute Shannon entropy normalized to [0,1] for three categories.

    Maximum entropy is ln(3) when all three phases are equally represented.
    Returns 0 when only one phase is present.
    """
    total = gas + water + ice
    if total == 0:
        return 0.0

    max_entropy = math.log(3)  # ln(3) for three categories
    entropy = 0.0
    for count in (gas, water, ice):
        if count > 0:
            p = count / total
            entropy -= p * math.log(p)

    return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0


def _determine_state(gas: int, water: int, ice: int) -> str:
    """Determine the breath state from phase counts.

    - breathing: all three phases > 0
    - inhaling: mostly gas (exploratory phase growing)
    - exhaling: mostly ice (crystallizing)
    - holding: only one phase represented (stuck)
    """
    non_zero = sum(1 for c in (gas, water, ice) if c > 0)
    if non_zero == 0:
        return "holding"
    if non_zero == 1:
        return "holding"
    if gas > 0 and water > 0 and ice > 0:
        return "breathing"

    total = gas + water + ice
    if total == 0:
        return "holding"

    # Two phases present
    if gas / total > 0.5:
        return "inhaling"
    if ice / total > 0.5:
        return "exhaling"
    return "breathing"


def compute_idea_breath(idea_id: str) -> dict:
    """Compute breath rhythm analysis for an idea.

    Returns gas/water/ice distribution, breath health, and state.
    """
    from app.services import spec_registry_service

    try:
        specs = spec_registry_service.list_specs_for_idea(idea_id)
    except Exception:
        log.debug("breath: could not load specs for idea %s", idea_id, exc_info=True)
        specs = []

    total = len(specs)
    gas_count = 0
    water_count = 0
    ice_count = 0

    for spec in specs:
        phase = _classify_spec(spec)
        if phase == "gas":
            gas_count += 1
        elif phase == "water":
            water_count += 1
        else:
            ice_count += 1

    rhythm = {
        "gas": round(gas_count / total, 4) if total > 0 else 0.0,
        "water": round(water_count / total, 4) if total > 0 else 0.0,
        "ice": round(ice_count / total, 4) if total > 0 else 0.0,
    }

    breath_health = _shannon_entropy_normalized(gas_count, water_count, ice_count)
    state = _determine_state(gas_count, water_count, ice_count)

    return {
        "idea_id": idea_id,
        "total_specs": total,
        "gas_count": gas_count,
        "water_count": water_count,
        "ice_count": ice_count,
        "rhythm": rhythm,
        "breath_health": breath_health,
        "state": state,
        "holding_days": None,  # Future: track days at same stage
    }


def compute_breath_overview() -> dict:
    """Compute breath analysis for all curated super-ideas.

    Returns individual idea breath data plus portfolio-level aggregates.
    """
    from app.services import idea_service

    try:
        portfolio = idea_service.list_ideas(limit=200, curated_only=True, read_only_guard=True)
        ideas = portfolio.ideas if hasattr(portfolio, "ideas") else []
    except Exception:
        log.debug("breath: could not load curated ideas", exc_info=True)
        ideas = []

    idea_breaths = []
    total_gas = 0
    total_water = 0
    total_ice = 0
    total_specs = 0

    for idea in ideas:
        idea_id = idea.id if hasattr(idea, "id") else idea.get("id", "")
        idea_name = idea.name if hasattr(idea, "name") else idea.get("name", idea_id)

        breath = compute_idea_breath(idea_id)
        idea_breaths.append({
            "idea_id": idea_id,
            "name": idea_name,
            "rhythm": breath["rhythm"],
            "breath_health": breath["breath_health"],
            "state": breath["state"],
            "total_specs": breath["total_specs"],
        })

        total_gas += breath["gas_count"]
        total_water += breath["water_count"]
        total_ice += breath["ice_count"]
        total_specs += breath["total_specs"]

    portfolio_rhythm = {
        "gas": round(total_gas / total_specs, 4) if total_specs > 0 else 0.0,
        "water": round(total_water / total_specs, 4) if total_specs > 0 else 0.0,
        "ice": round(total_ice / total_specs, 4) if total_specs > 0 else 0.0,
    }
    portfolio_breath_health = _shannon_entropy_normalized(total_gas, total_water, total_ice)

    return {
        "ideas": idea_breaths,
        "portfolio_rhythm": portfolio_rhythm,
        "portfolio_breath_health": portfolio_breath_health,
    }
