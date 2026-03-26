"""Pipeline auto-advance + auto-retry + smart escalation.

Auto-advance: when a task completes, create the next phase task.
  spec → impl → test → code-review

Auto-retry: when a task times out or fails, create a retry (up to 2 per phase).
  Avoids the provider that failed via exclude_provider hint.
  Carries partial output forward so retries don't start from scratch.

Smart escalation: when retries exhaust, analyze the failure pattern and either:
  - Auto-fix (split task, simplify direction, try different approach)
  - Escalate to needs_decision with structured options for a human

All fire from the task update API, making the pipeline self-sustaining
regardless of which runner or client changes the task status.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.agent import AgentTaskCreate, AgentTaskUpdate, TaskType, TaskStatus

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

# All phases downstream of a given phase — used for cascade invalidation
_DOWNSTREAM: dict[str, list[str]] = {
    "spec": ["impl", "test", "code-review", "review"],
    "impl": ["test", "code-review", "review"],
    "test": ["code-review", "review"],
}

_PHASE_TASK_TYPE: dict[str, TaskType] = {
    "spec": TaskType.SPEC,
    "impl": TaskType.IMPL,
    "test": TaskType.TEST,
    "code-review": TaskType.REVIEW,
}

# Minimum output length to consider a task genuinely completed.
# Text-only providers (openrouter/free) often claim completion with 0 output.
_MIN_OUTPUT_CHARS: dict[str, int] = {
    "spec": 100,    # A real spec is at least a paragraph
    "impl": 200,    # A real impl must describe files changed + verification
    "test": 100,    # A real test run must show test results
    "code-review": 30,  # A review at least says PASSED or FAILED
}

# Phases that MUST produce code (git diff). Text output alone is not enough.
_CODE_REQUIRED_PHASES = {"impl", "test"}

<<<<<<< HEAD

def invalidate_downstream(task_type: str, idea_id: str) -> int:
    """When a phase is reclassified as failed, invalidate its downstream tasks.

    If impl fails, any completed test/review for that idea is also invalid
    (it was reviewing hollow output). Mark them failed so they get retried
    after the upstream phase succeeds.

    Returns the number of downstream tasks invalidated.
    """
    from app.services import agent_service

    downstream_phases = _DOWNSTREAM.get(task_type, [])
    if not downstream_phases or not idea_id:
        return 0

    all_tasks, _total, _backfill = agent_service.list_tasks(limit=500, offset=0)
    invalidated = 0

    for t in all_tasks:
        t_type = t.get("task_type", "")
        if hasattr(t_type, "value"):
            t_type = t_type.value
        t_status = t.get("status", "")
        if hasattr(t_status, "value"):
            t_status = t_status.value
        t_idea = (t.get("context") or {}).get("idea_id", "")

        if (t_type in downstream_phases
                and t_idea == idea_id
                and t_status in ("completed", "pending", "running")):
            try:
                agent_service.update_task(
                    t.get("id", ""),
                    status="failed",
                    output=f"Invalidated: upstream {task_type} was reclassified as failed. This {t_type} was based on hollow upstream output.",
                    context={
                        **(t.get("context") or {}),
                        "cascade_invalidated": True,
                        "invalidated_by_phase": task_type,
                    },
                )
                invalidated += 1
                log.info("CASCADE_INVALIDATE %s for idea=%s (upstream %s failed)", t_type, idea_id, task_type)
            except Exception:
                pass

    return invalidated

=======
>>>>>>> origin/main

def _validate_output(task: dict[str, Any]) -> tuple[bool, str]:
    """Check if a completed task has meaningful output.

    For impl/test: output must mention file changes or contain code evidence.
    Returns (is_valid, reason).
    """
    task_type = task.get("task_type", "")
    if hasattr(task_type, "value"):
        task_type = task_type.value
    output = (task.get("output") or "").strip()
    min_chars = _MIN_OUTPUT_CHARS.get(task_type, 30)

    if len(output) < min_chars:
        return False, f"Output too short ({len(output)} chars < {min_chars} min for {task_type})"

    # impl/test must show evidence of code changes, not just text claims
    if task_type in _CODE_REQUIRED_PHASES:
        context = task.get("context") or {}
        # Check for git diff evidence, file paths, or branch push
        code_signals = any([
            "diff" in output.lower(),
            ".py" in output or ".tsx" in output or ".mjs" in output or ".ts" in output,
            "created" in output.lower() and ("file" in output.lower() or "test" in output.lower()),
            "modified" in output.lower(),
            context.get("branch_pushed"),
            context.get("diff_size"),
        ])
        if not code_signals:
            return False, f"{task_type} completed but output has no evidence of code changes (no file paths, no diff, no branch)"

    return True, ""


def maybe_advance(task: dict[str, Any]) -> dict[str, Any] | None:
    """If the task completed successfully WITH meaningful output, create the next phase task.

    Returns the created task dict, or None if no advancement was needed.
    """
    status = task.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status != "completed":
        return None

    # Reject hollow completions — text-only providers claim success with no output
    valid, reason = _validate_output(task)
    if not valid:
        task_type_raw = task.get("task_type", "")
        if hasattr(task_type_raw, "value"):
            task_type_raw = task_type_raw.value
        idea_id = (task.get("context") or {}).get("idea_id", "?")
        log.warning(
            "HOLLOW_COMPLETION blocked advance: type=%s idea=%s — %s",
            task_type_raw, idea_id, reason,
        )
        # Mark it failed so auto-retry kicks in with a real provider
        try:
            from app.services import agent_service
            agent_service.update_task(
                task.get("id", ""),
                status=TaskStatus.FAILED,
                output=f"Hollow completion rejected: {reason}",
                context={**(task.get("context") or {}), "hollow_rejection": True},
            )
            # Cascade: invalidate downstream tasks built on this hollow output
            invalidated = invalidate_downstream(task_type_raw, idea_id)
            if invalidated:
                log.info("CASCADE_INVALIDATED %d downstream tasks for idea=%s", invalidated, idea_id)
        except Exception:
            pass
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
        log.info("AUTO_RETRY exhausted — %s for %s retried %d times, escalating", task_type, idea_id, retry_count)
        _escalate_or_autofix(task, task_type, idea_id, retry_count)
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

    # Reuse the original direction, enriched with partial output
    direction = task.get("direction", "")
    failed_provider = task.get("model", "") or context.get("provider", "")
    partial_output = (task.get("output") or "").strip()

    if partial_output and len(partial_output) > 20:
        # Carry partial work forward so the retry doesn't start from scratch
        direction = (
            f"{direction}\n\n"
            f"--- PARTIAL WORK FROM PREVIOUS ATTEMPT (timed out) ---\n"
            f"{partial_output[:3000]}\n"
            f"--- END PARTIAL WORK ---\n\n"
            f"Continue from the partial work above. Do not start over — "
            f"pick up where the previous attempt left off and complete the task."
        )

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


# ── Failure analysis + smart escalation ──────────────────────────


def _classify_failure(task: dict[str, Any]) -> dict[str, Any]:
    """Analyze why a task failed and suggest fixes."""
    context = task.get("context") or {}
    output = (task.get("output") or "").strip()
    error = (task.get("error_summary") or "").strip()
    direction = (task.get("direction") or "").strip()
    task_type = task.get("task_type", "")
    if hasattr(task_type, "value"):
        task_type = task_type.value
    failed_providers = set()
    if context.get("failed_provider"):
        failed_providers.add(context["failed_provider"])
    # Collect providers from retry chain
    if context.get("exclude_provider"):
        failed_providers.add(context["exclude_provider"])

    analysis = {
        "failure_type": "unknown",
        "reason": "",
        "auto_fixable": False,
        "fix_action": None,
        "fix_description": "",
    }

    combined = f"{output} {error}".lower()

    # Pattern: timeout — task too large for provider
    if "timed_out" in str(task.get("status", "")).lower() or "timeout" in combined:
        if len(direction) > 2000:
            analysis["failure_type"] = "task_too_large"
            analysis["reason"] = f"Direction is {len(direction)} chars — providers time out on large tasks."
            analysis["auto_fixable"] = True
            analysis["fix_action"] = "split"
            analysis["fix_description"] = "Split into smaller sub-tasks with focused directions."
        else:
            analysis["failure_type"] = "provider_timeout"
            analysis["reason"] = f"All tried providers timed out: {', '.join(failed_providers) or 'unknown'}."
            analysis["auto_fixable"] = False
            analysis["fix_description"] = "Needs a faster/stronger provider or simpler task scope."

    # Pattern: spec too vague for impl
    elif task_type == "impl" and ("spec" in combined and ("unclear" in combined or "missing" in combined or "not found" in combined)):
        analysis["failure_type"] = "spec_unclear"
        analysis["reason"] = "Implementation failed because the spec is unclear or missing."
        analysis["auto_fixable"] = True
        analysis["fix_action"] = "respec"
        analysis["fix_description"] = "Create a new spec task with more specific requirements."

    # Pattern: test failures in impl or test phase
    elif "test" in combined and ("fail" in combined or "error" in combined or "assert" in combined):
        analysis["failure_type"] = "test_failure"
        analysis["reason"] = "Tests are failing — likely a bug in the implementation."
        analysis["auto_fixable"] = True
        analysis["fix_action"] = "heal"
        analysis["fix_description"] = "Create a heal task to fix the failing tests."

    # Pattern: import/dependency error
    elif "import" in combined and "error" in combined or "modulenotfounderror" in combined:
        analysis["failure_type"] = "missing_dependency"
        analysis["reason"] = "Missing import or dependency."
        analysis["auto_fixable"] = True
        analysis["fix_action"] = "heal"
        analysis["fix_description"] = "Create a heal task to fix the missing dependency."

    # Pattern: empty output — provider didn't respond meaningfully
    elif not output or len(output) < 20:
        analysis["failure_type"] = "empty_output"
        analysis["reason"] = "Provider returned empty or trivial output."
        analysis["auto_fixable"] = False
        analysis["fix_description"] = "Needs a different provider or clearer direction."

    # Default: unknown failure
    else:
        analysis["failure_type"] = "unknown"
        analysis["reason"] = error[:200] if error else "No clear error pattern detected."
        analysis["auto_fixable"] = False
        analysis["fix_description"] = "Manual review needed."

    return analysis


def _escalate_or_autofix(
    task: dict[str, Any],
    task_type: str,
    idea_id: str,
    retry_count: int,
) -> None:
    """Analyze failure, auto-fix if possible, escalate to needs_decision if not."""
    from app.services import agent_service

    analysis = _classify_failure(task)
    context = task.get("context") or {}
    idea_name = idea_id.replace("-", " ").replace("_", " ").title()

    log.info(
        "ESCALATE idea=%s type=%s failure=%s auto_fixable=%s",
        idea_id, task_type, analysis["failure_type"], analysis["auto_fixable"],
    )

    # ── Auto-fix path ──
    if analysis["auto_fixable"] and analysis["fix_action"]:
        action = analysis["fix_action"]

        if action == "split":
            # Create a simpler version of the same task with shorter direction
            original_direction = task.get("direction", "")
            # Take just the first paragraph as the focused direction
            simplified = original_direction.split("\n\n")[0][:500]
            try:
                created = agent_service.create_task(AgentTaskCreate(
                    direction=(
                        f"{simplified}\n\n"
                        f"Keep the scope minimal — implement only the core requirement. "
                        f"Skip optional features. This is a simplified retry after timeout."
                    ),
                    task_type=_PHASE_TASK_TYPE.get(task_type, TaskType.IMPL),
                    context={
                        "idea_id": idea_id,
                        "auto_fix": "split",
                        "original_task_id": task.get("id", ""),
                        "retry_count": 0,  # Fresh retry count for the simplified version
                    },
                ))
                log.info("AUTO_FIX split task=%s → simplified task=%s", task.get("id", "?"), created.get("id", "?"))
                return
            except Exception:
                log.warning("AUTO_FIX split failed for %s", idea_id, exc_info=True)

        elif action == "respec":
            # Create a new spec task that's more specific
            try:
                created = agent_service.create_task(AgentTaskCreate(
                    direction=(
                        f"Write a more detailed spec for '{idea_name}' ({idea_id}).\n\n"
                        f"A previous implementation attempt failed because the spec was unclear.\n"
                        f"This spec MUST include:\n"
                        f"1. Concrete acceptance criteria (what 'done' looks like)\n"
                        f"2. Specific files to create or modify\n"
                        f"3. At least one test scenario with expected input/output\n"
                        f"4. Verification command to prove it works"
                    ),
                    task_type=TaskType.SPEC,
                    context={
                        "idea_id": idea_id,
                        "auto_fix": "respec",
                        "original_task_id": task.get("id", ""),
                    },
                ))
                log.info("AUTO_FIX respec for idea=%s → task=%s", idea_id, created.get("id", "?"))
                return
            except Exception:
                log.warning("AUTO_FIX respec failed for %s", idea_id, exc_info=True)

        elif action == "heal":
            # Create a heal task to fix the specific issue
            error_snippet = (task.get("output") or task.get("error_summary") or "")[:500]
            try:
                created = agent_service.create_task(AgentTaskCreate(
                    direction=(
                        f"Fix the failing code for '{idea_name}' ({idea_id}).\n\n"
                        f"Error from previous run:\n{error_snippet}\n\n"
                        f"Find the root cause, fix it, and verify the fix with tests."
                    ),
                    task_type=TaskType.IMPL,
                    context={
                        "idea_id": idea_id,
                        "auto_fix": "heal",
                        "original_task_id": task.get("id", ""),
                    },
                ))
                log.info("AUTO_FIX heal for idea=%s → task=%s", idea_id, created.get("id", "?"))
                return
            except Exception:
                log.warning("AUTO_FIX heal failed for %s", idea_id, exc_info=True)

    # ── Escalation path — mark the ORIGINAL task as needs_decision ──
    failed_providers = set(filter(None, [
        context.get("failed_provider"),
        context.get("exclude_provider"),
        task.get("model"),
    ]))

    decision_prompt = (
        f"Task '{task_type}' for '{idea_name}' failed {retry_count + 1} times.\n"
        f"\n"
        f"Failure: {analysis['failure_type']} — {analysis['reason']}\n"
        f"Providers tried: {', '.join(failed_providers) or 'unknown'}\n"
        f"\n"
        f"Options:\n"
        f"  A) Retry with simplified scope (trim direction, focus on core)\n"
        f"  B) Rewrite the spec with clearer acceptance criteria\n"
        f"  C) Deprioritize this idea (lower confidence score)\n"
        f"  D) Skip this phase and advance anyway\n"
        f"\n"
        f"Reply with A, B, C, or D."
    )

    try:
        agent_service.update_task(
            task.get("id", ""),
            status=TaskStatus.NEEDS_DECISION,
            decision_prompt=decision_prompt,
            context={
                **(task.get("context") or {}),
                "failure_analysis": analysis,
                "escalation_source": "pipeline_advance_service",
            },
        )
        log.info("ESCALATED idea=%s type=%s → needs_decision (failure=%s)", idea_id, task_type, analysis["failure_type"])
    except Exception:
        log.warning("ESCALATE failed for idea=%s", idea_id, exc_info=True)


def handle_decision(task: dict[str, Any], decision: str) -> dict[str, Any] | None:
    """Process a human decision (A/B/C/D) on an escalated task.

    Returns the created follow-up task, or None.
    """
    from app.services import agent_service

    context = task.get("context") or {}
    idea_id = context.get("idea_id", "")
    task_type = task.get("task_type", "")
    if hasattr(task_type, "value"):
        task_type = task_type.value
    idea_name = idea_id.replace("-", " ").replace("_", " ").title()

    choice = decision.strip().upper()[:1]
    log.info("DECISION idea=%s type=%s choice=%s", idea_id, task_type, choice)

    if choice == "A":
        # Retry with simplified scope
        original = task.get("direction", "")
        simplified = original.split("\n\n")[0][:500]
        try:
            return agent_service.create_task(AgentTaskCreate(
                direction=(
                    f"{simplified}\n\n"
                    f"Keep scope minimal — core requirement only. Skip optional features."
                ),
                task_type=_PHASE_TASK_TYPE.get(task_type, TaskType.IMPL),
                context={"idea_id": idea_id, "decision_action": "simplified_retry", "retry_count": 0},
            ))
        except Exception:
            log.warning("DECISION A failed for %s", idea_id, exc_info=True)

    elif choice == "B":
        # Rewrite spec
        try:
            return agent_service.create_task(AgentTaskCreate(
                direction=(
                    f"Rewrite the spec for '{idea_name}' ({idea_id}) with concrete acceptance criteria.\n"
                    f"Include: specific files, test scenarios, verification commands."
                ),
                task_type=TaskType.SPEC,
                context={"idea_id": idea_id, "decision_action": "respec"},
            ))
        except Exception:
            log.warning("DECISION B failed for %s", idea_id, exc_info=True)

    elif choice == "C":
        # Deprioritize — lower the idea's confidence
        try:
            from app.services import graph_service
            node = graph_service.get_node(idea_id)
            if node:
                current_conf = float(node.get("confidence", 0.5))
                graph_service.update_node(idea_id, properties={"confidence": max(0.1, current_conf * 0.5)})
                log.info("DEPRIORITIZED idea=%s confidence %.2f → %.2f", idea_id, current_conf, current_conf * 0.5)
            # Mark task completed (it's been handled by deprioritizing)
            agent_service.update_task(task.get("id", ""), status=TaskStatus.COMPLETED, output=f"Deprioritized: confidence halved.")
        except Exception:
            log.warning("DECISION C failed for %s", idea_id, exc_info=True)

    elif choice == "D":
        # Skip phase and advance
        try:
            agent_service.update_task(task.get("id", ""), status=TaskStatus.COMPLETED, output=f"Phase skipped by human decision.")
            # Trigger auto-advance from the now-completed task
            task_copy = dict(task)
            task_copy["status"] = "completed"
            return maybe_advance(task_copy)
        except Exception:
            log.warning("DECISION D failed for %s", idea_id, exc_info=True)

    return None
