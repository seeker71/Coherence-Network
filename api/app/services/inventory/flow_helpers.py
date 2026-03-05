"""Flow unblock helpers: fingerprint, direction, interdependencies."""

from __future__ import annotations

import hashlib
from typing import Any

from app.models.agent import TaskType

from app.services.inventory.constants import (
    _FLOW_STAGE_ESTIMATED_COST,
    _FLOW_STAGE_ORDER,
    _FLOW_STAGE_TASK_TYPE,
    _question_roi,
)


def _flow_unblock_fingerprint(idea_id: str, blocking_stage: str) -> str:
    payload = f"flow-unblock::{idea_id.strip().lower()}::{blocking_stage.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clamp_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(numeric, 1.0))


def _build_unblock_direction(
    idea_id: str,
    idea_name: str,
    blocking_stage: str,
    blocked_stages: list[str],
    spec_ids: list[str],
) -> str:
    blocked_text = ", ".join(blocked_stages) if blocked_stages else "flow completion"
    if blocking_stage == "spec":
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by adding/updating spec coverage. "
            f"This unlocks: {blocked_text}. Define acceptance checks and link to process and implementation."
        )
    if blocking_stage == "process":
        spec_hint = ", ".join(spec_ids[:5]) if spec_ids else "linked spec"
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by defining process and pseudocode grounded in {spec_hint}. "
            f"This unlocks: {blocked_text}."
        )
    if blocking_stage == "implementation":
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by implementing the tracked spec/process artifacts "
            f"and linking code references. This unlocks: {blocked_text}."
        )
    return (
        f"Unblock idea '{idea_id}' ({idea_name}) by validating the current implementation "
        "with local, CI, deploy, and e2e evidence updates."
    )


def _build_flow_interdependencies(
    *,
    idea_id: str,
    idea_name: str,
    spec_tracked: bool,
    process_tracked: bool,
    implementation_tracked: bool,
    validation_tracked: bool,
    spec_ids: list[str],
    idea_value_gap: float,
    idea_confidence: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    stage_tracked = {
        "spec": bool(spec_tracked),
        "process": bool(process_tracked),
        "implementation": bool(implementation_tracked),
        "validation": bool(validation_tracked),
    }
    missing = [stage for stage in _FLOW_STAGE_ORDER if not stage_tracked[stage]]
    if not missing:
        return (
            {
                "blocked": False,
                "blocking_stage": None,
                "upstream_required": [],
                "downstream_blocked": [],
                "estimated_unblock_cost": 0.0,
                "estimated_unblock_value": 0.0,
                "unblock_priority_score": 0.0,
                "task_fingerprint": None,
                "next_unblock_task": None,
            },
            None,
        )
    blocking_stage = missing[0]
    stage_index = _FLOW_STAGE_ORDER.index(blocking_stage)
    upstream_required = list(_FLOW_STAGE_ORDER[:stage_index])
    downstream_blocked = [stage for stage in _FLOW_STAGE_ORDER[stage_index + 1 :] if not stage_tracked[stage]]
    stage_cost = float(_FLOW_STAGE_ESTIMATED_COST.get(blocking_stage, 1.0))
    confidence = _clamp_confidence(idea_confidence)
    value_gap = max(float(idea_value_gap), 0.0)
    unlock_multiplier = (len(downstream_blocked) + 1) / max(1.0, float(len(_FLOW_STAGE_ORDER)))
    unlock_value = round(value_gap * confidence * unlock_multiplier, 4)
    priority_score = _question_roi(unlock_value, stage_cost)
    fingerprint = _flow_unblock_fingerprint(idea_id, blocking_stage)
    direction = _build_unblock_direction(
        idea_id=idea_id,
        idea_name=idea_name,
        blocking_stage=blocking_stage,
        blocked_stages=downstream_blocked,
        spec_ids=spec_ids,
    )
    task_type = _FLOW_STAGE_TASK_TYPE.get(blocking_stage, TaskType.IMPL)
    candidate = {
        "idea_id": idea_id,
        "idea_name": idea_name,
        "blocking_stage": blocking_stage,
        "upstream_required": upstream_required,
        "downstream_blocked": downstream_blocked,
        "estimated_unblock_cost": stage_cost,
        "estimated_unblock_value": unlock_value,
        "unblock_priority_score": priority_score,
        "task_fingerprint": fingerprint,
        "task_type": task_type.value,
        "direction": direction,
    }
    return (
        {
            "blocked": True,
            "blocking_stage": blocking_stage,
            "upstream_required": upstream_required,
            "downstream_blocked": downstream_blocked,
            "estimated_unblock_cost": stage_cost,
            "estimated_unblock_value": unlock_value,
            "unblock_priority_score": priority_score,
            "task_fingerprint": fingerprint,
            "next_unblock_task": {
                "task_type": task_type.value,
                "direction": direction,
            },
        },
        candidate,
    )
