"""Pipeline auto-advance + auto-retry.

Auto-advance: when a task completes, create the next phase task.
  spec → impl → test → code-review

Auto-retry: when a task times out or fails, create a retry (up to 2 per phase).
  Avoids the provider that failed via exclude_provider hint.

Both fire from the task update API, making the pipeline self-sustaining
regardless of which runner or client changes the task status.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.agent import AgentTaskCreate, TaskType

log = logging.getLogger(__name__)

_MAX_RETRIES = 2

_NEXT_PHASE: dict[str, str | None] = {
    "spec": "impl",
    "impl": "test",
    "test": "code-review",
    "code-review": None,
    "review": None,
    "deploy": None,
    "verify": None,
    "heal": None,
}

_PHASE_TASK_TYPE: dict[str, TaskType] = {
    "spec": TaskType.SPEC,
    "impl": TaskType.IMPL,
    "test": TaskType.TEST,
    "code-review": TaskType.REVIEW,
}


def maybe_advance(task: dict[str, Any]) -> dict[str, Any] | None:
    """If the task completed successfully, create the next phase task.

    Returns the created task dict, or None if no advancement was needed.
    """
    status = task.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status != "completed":
        return None

    task_type = task.get("task_type", "")
    if hasattr(task_type, "value"):
        task_type = task_type.value

    next_phase = _NEXT_PHASE.get(task_type)
    if not next_phase:
        return None

    context = task.get("context") or {}
    idea_id = context.get("idea_id", "")
    if not idea_id:
        return None

    # Check if a task for this phase already exists for this idea
    from app.services import agent_service
    existing_tasks, _total, _backfill = agent_service.list_tasks(limit=200, offset=0)
    for existing in existing_tasks:
        existing_type = existing.get("task_type", "")
        if hasattr(existing_type, "value"):
            existing_type = existing_type.value
        existing_status = existing.get("status", "")
        if hasattr(existing_status, "value"):
            existing_status = existing_status.value
        existing_idea = (existing.get("context") or {}).get("idea_id", "")

        if (existing_type == next_phase
                and existing_idea == idea_id
                and existing_status in ("pending", "running")):
            log.info("AUTO_ADVANCE skip — %s task already exists for %s", next_phase, idea_id)
            return None

    # Build direction
    idea_name = idea_id.replace("-", " ").replace("_", " ").title()
    if next_phase == "impl":
        direction = (
            f"Implement '{idea_name}' ({idea_id}).\n\n"
            f"A spec was just completed for this idea. Read the spec in specs/ and implement it.\n"
            f"Follow CLAUDE.md conventions. The implementation must satisfy all verification "
            f"criteria in the spec.\n\n"
            f"After writing code, verify with DIF:\n"
            f"  cc dif verify --language python --file <file.py> --json\n"
            f"Fix any DIF concerns before finishing."
        )
    elif next_phase == "test":
        direction = (
            f"Write tests for '{idea_name}' ({idea_id}).\n\n"
            f"Implementation was just completed. Write tests that verify the spec's acceptance "
            f"criteria. Run them and ensure they pass.\n\n"
            f"After writing tests, verify with DIF:\n"
            f"  cc dif verify --language python --file <test_file.py> --json"
        )
    elif next_phase == "code-review":
        direction = (
            f"Code review for '{idea_name}' ({idea_id}).\n\n"
            f"Implementation and tests were completed. Review for:\n"
            f"1. Does code match spec requirements?\n"
            f"2. Are tests covering key scenarios?\n"
            f"3. Code quality, error handling, project conventions\n\n"
            f"Run DIF on all changed files. Output CODE_REVIEW_PASSED or CODE_REVIEW_FAILED."
        )
    else:
        direction = f"Execute '{next_phase}' phase for '{idea_name}' ({idea_id})."

    next_task_type = _PHASE_TASK_TYPE.get(next_phase, TaskType.IMPL)

    try:
        created = agent_service.create_task(AgentTaskCreate(
            direction=direction,
            task_type=next_task_type,
            context={
                "idea_id": idea_id,
                "auto_advanced_from": task_type,
                "auto_advance_source": "pipeline_advance_service",
                "source_task_id": task.get("id", ""),
            },
        ))
        log.info(
            "AUTO_ADVANCE %s→%s for idea=%s created task=%s",
            task_type, next_phase, idea_id, created.get("id", "?"),
        )
        return created
    except Exception:
        log.warning("AUTO_ADVANCE failed %s→%s for idea=%s", task_type, next_phase, idea_id, exc_info=True)
        return None


def maybe_retry(task: dict[str, Any]) -> dict[str, Any] | None:
    """If a task timed out or failed, create a retry task (up to _MAX_RETRIES).

    Returns the created retry task dict, or None if no retry was needed.
    """
    status = task.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status not in ("timed_out", "failed"):
        return None

    task_type = task.get("task_type", "")
    if hasattr(task_type, "value"):
        task_type = task_type.value

    context = task.get("context") or {}
    idea_id = context.get("idea_id", "")
    if not idea_id:
        return None

    retry_count = int(context.get("retry_count", 0))
    if retry_count >= _MAX_RETRIES:
        log.info("AUTO_RETRY skip — %s for %s already retried %d times", task_type, idea_id, retry_count)
        return None

    # Don't retry if a pending/running task already exists for this phase+idea
    from app.services import agent_service
    existing_tasks, _total, _backfill = agent_service.list_tasks(limit=200, offset=0)
    for existing in existing_tasks:
        existing_type = existing.get("task_type", "")
        if hasattr(existing_type, "value"):
            existing_type = existing_type.value
        existing_status = existing.get("status", "")
        if hasattr(existing_status, "value"):
            existing_status = existing_status.value
        existing_idea = (existing.get("context") or {}).get("idea_id", "")

        if (existing_type == task_type
                and existing_idea == idea_id
                and existing_status in ("pending", "running")):
            log.info("AUTO_RETRY skip — %s task already pending/running for %s", task_type, idea_id)
            return None

    # Reuse the original direction
    direction = task.get("direction", "")
    failed_provider = task.get("model", "") or context.get("provider", "")
    task_type_enum = _PHASE_TASK_TYPE.get(task_type, TaskType.IMPL)

    try:
        created = agent_service.create_task(AgentTaskCreate(
            direction=direction,
            task_type=task_type_enum,
            context={
                "idea_id": idea_id,
                "retry_count": retry_count + 1,
                "retry_of": task.get("id", ""),
                "failed_provider": failed_provider,
                "exclude_provider": failed_provider,
                "auto_retry_source": "pipeline_advance_service",
            },
        ))
        log.info(
            "AUTO_RETRY %s #%d for idea=%s (failed_provider=%s) → task=%s",
            task_type, retry_count + 1, idea_id, failed_provider, created.get("id", "?"),
        )
        return created
    except Exception:
        log.warning("AUTO_RETRY failed for idea=%s type=%s", idea_id, task_type, exc_info=True)
        return None
