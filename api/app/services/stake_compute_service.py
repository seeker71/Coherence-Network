"""Stake-to-compute service: when CC is staked on an idea, determine and create tasks.

Bridges the staking action to the agent task pipeline. When a contributor stakes CC
on an idea, this service determines what work the idea needs next and creates
tasks for it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.agent import AgentTaskCreate, TaskType
from app.models.idea import IdeaStage
from app.services import agent_service, idea_service, contribution_ledger_service, spec_registry_service

logger = logging.getLogger(__name__)

# Maps idea stage to the task type needed at that stage
_STAGE_TO_TASK_TYPE: dict[str, TaskType] = {
    IdeaStage.NONE.value: TaskType.SPEC,
    IdeaStage.SPECCED.value: TaskType.IMPL,
    IdeaStage.IMPLEMENTING.value: TaskType.TEST,
    IdeaStage.TESTING.value: TaskType.REVIEW,
    IdeaStage.REVIEWING.value: TaskType.REVIEW,
}


def _specs_for_idea(idea_id: str) -> list[Any]:
    """Return specs linked to an idea."""
    all_specs = spec_registry_service.list_specs(limit=1000)
    return [s for s in all_specs if s.idea_id == idea_id]


def _tasks_for_idea(idea_id: str) -> dict[str, Any]:
    """Return tasks grouped by type for an idea."""
    return agent_service.list_tasks_for_idea(idea_id)


def _task_type_value(tt: Any) -> str:
    return tt.value if hasattr(tt, "value") else str(tt)


def compute_next_tasks_for_idea(idea_id: str) -> list[dict]:
    """Determine what tasks an idea needs based on its current stage."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return []

    stage = idea.stage if hasattr(idea, "stage") else IdeaStage.NONE.value
    stage_val = stage.value if hasattr(stage, "value") else str(stage or "none")

    # If idea is complete, no more tasks
    if stage_val == IdeaStage.COMPLETE.value:
        return []

    tasks_response = _tasks_for_idea(idea_id)
    existing_groups = tasks_response.get("groups", []) if isinstance(tasks_response, dict) else []

    # Build a set of existing task types
    existing_types: set[str] = set()
    for group in existing_groups:
        tt = group.get("task_type", "")
        if group.get("count", 0) > 0:
            existing_types.add(tt)

    needed: list[dict] = []

    if stage_val == IdeaStage.NONE.value:
        # Needs spec tasks
        specs = _specs_for_idea(idea_id)
        if not specs and "spec" not in existing_types:
            needed.append({
                "task_type": TaskType.SPEC,
                "direction": f"[idea:{idea_id}] Create a specification for idea '{idea.name}': {idea.description}",
            })
    elif stage_val == IdeaStage.SPECCED.value:
        # Needs impl tasks (one per spec)
        specs = _specs_for_idea(idea_id)
        if "impl" not in existing_types:
            if specs:
                for spec in specs:
                    needed.append({
                        "task_type": TaskType.IMPL,
                        "direction": f"[idea:{idea_id}] Implement spec '{spec.spec_id}': {spec.title}",
                    })
            else:
                needed.append({
                    "task_type": TaskType.IMPL,
                    "direction": f"[idea:{idea_id}] Implement idea '{idea.name}': {idea.description}",
                })
    elif stage_val == IdeaStage.IMPLEMENTING.value:
        # Needs test tasks
        if "test" not in existing_types:
            needed.append({
                "task_type": TaskType.TEST,
                "direction": f"[idea:{idea_id}] Create tests for idea '{idea.name}': {idea.description}",
            })
    elif stage_val in (IdeaStage.TESTING.value, IdeaStage.REVIEWING.value):
        # Needs review tasks
        if "review" not in existing_types:
            needed.append({
                "task_type": TaskType.REVIEW,
                "direction": f"[idea:{idea_id}] Review idea '{idea.name}': {idea.description}",
            })

    return needed


def execute_stake(idea_id: str, staker_id: str, amount_cc: float, rationale: str | None = None) -> dict:
    """Stake CC on an idea and trigger compute.

    Returns: {stake_recorded, tasks_created, idea_stage, next_actions, message}
    """
    # 1. Call existing stake_on_idea
    stake_result = idea_service.stake_on_idea(
        idea_id=idea_id,
        contributor_id=staker_id,
        amount_cc=amount_cc,
        rationale=rationale,
    )

    # 2. Determine what tasks are needed
    needed_tasks = compute_next_tasks_for_idea(idea_id)

    # 3. Create each task via agent_service
    created_tasks: list[dict] = []
    for task_spec in needed_tasks:
        try:
            task_create = AgentTaskCreate(
                direction=task_spec["direction"],
                task_type=task_spec["task_type"],
                context={"idea_id": idea_id, "trigger": "stake_compute", "staker_id": staker_id},
            )
            task = agent_service.create_task(task_create)
            created_tasks.append({
                "task_id": task["id"],
                "type": _task_type_value(task_spec["task_type"]),
                "direction": task_spec["direction"],
            })
        except Exception:
            logger.warning("Failed to create task for idea %s", idea_id, exc_info=True)

    # 4. Record a stake_compute contribution with metadata showing task_ids
    task_ids = [t["task_id"] for t in created_tasks]
    if task_ids:
        try:
            contribution_ledger_service.record_contribution(
                contributor_id=staker_id,
                contribution_type="compute",
                amount_cc=0.0,
                idea_id=idea_id,
                metadata={"trigger": "stake_compute", "task_ids": task_ids},
            )
        except Exception:
            logger.warning("Failed to record stake_compute contribution", exc_info=True)

    # 5. Get current idea stage
    idea = idea_service.get_idea(idea_id)
    stage_val = "none"
    if idea is not None:
        stage = idea.stage if hasattr(idea, "stage") else "none"
        stage_val = stage.value if hasattr(stage, "value") else str(stage or "none")

    task_count = len(created_tasks)
    message = f"Staked {amount_cc} CC"
    if task_count > 0:
        message += f" -> {task_count} task{'s' if task_count != 1 else ''} created and queued for execution"
    else:
        message += " -> no new tasks needed"

    return {
        "stake": {
            "amount_cc": amount_cc,
            "contributor": staker_id,
            "rationale": rationale,
            "record": stake_result.get("stake_record"),
        },
        "tasks_created": created_tasks,
        "idea_stage": stage_val,
        "message": message,
    }


def get_idea_progress(idea_id: str) -> dict:
    """Get progress for an idea: stage, tasks by phase, CC staked/spent, contributors."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return {"error": "not_found"}

    stage = idea.stage if hasattr(idea, "stage") else "none"
    stage_val = stage.value if hasattr(stage, "value") else str(stage or "none")

    # Tasks by phase
    tasks_response = _tasks_for_idea(idea_id)
    groups = tasks_response.get("groups", []) if isinstance(tasks_response, dict) else []

    phases: dict[str, dict] = {}
    for phase_name in ["spec", "impl", "test", "review"]:
        phases[phase_name] = {"done": 0, "total": 0}

    for group in groups:
        tt = group.get("task_type", "")
        if tt in phases:
            total = group.get("count", 0)
            status_counts = group.get("status_counts", {})
            done = status_counts.get("completed", 0)
            phases[tt] = {"done": done, "total": total}

    # CC staked and spent from contribution ledger
    investments = contribution_ledger_service.get_idea_investments(idea_id)
    cc_staked = 0.0
    cc_spent = 0.0
    contributors: set[str] = set()
    for inv in investments:
        ctype = inv.get("contribution_type", "")
        amount = inv.get("amount_cc", 0.0)
        contributor = inv.get("contributor_id", "")
        if ctype == "stake":
            cc_staked += amount
            contributors.add(contributor)
        elif ctype == "compute" and amount < 0:
            cc_spent += abs(amount)

    return {
        "idea_id": idea_id,
        "idea_name": idea.name,
        "stage": stage_val,
        "phases": phases,
        "cc_staked": round(cc_staked, 4),
        "cc_spent": round(cc_spent, 4),
        "cc_balance": round(cc_staked - cc_spent, 4),
        "contributors": sorted(contributors),
        "total_tasks": tasks_response.get("total", 0) if isinstance(tasks_response, dict) else 0,
    }


def record_task_cost(task_id: str, idea_id: str, provider: str, duration_s: float, success: bool):
    """Record the compute cost of a task execution against an idea's CC budget."""
    # Simple cost model: 0.1 CC per second of compute
    cost_cc = round(duration_s * 0.1, 4)

    contribution_ledger_service.record_contribution(
        contributor_id=f"provider:{provider}",
        contribution_type="compute",
        amount_cc=-cost_cc,
        idea_id=idea_id,
        metadata={
            "trigger": "compute_spent",
            "task_id": task_id,
            "provider": provider,
            "duration_s": round(duration_s, 2),
            "success": success,
            "cost_cc": cost_cc,
        },
    )

    return {
        "task_id": task_id,
        "idea_id": idea_id,
        "cost_cc": cost_cc,
        "provider": provider,
        "success": success,
    }
