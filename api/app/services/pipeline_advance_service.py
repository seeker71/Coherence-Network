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

def _extract_partial_work(task: dict[str, Any]) -> str:
    """Extract self-contained partial work from a timed-out/failed task.

    Priority:
    1. Git diff (actual code changes) from context.diff_content
    2. Checkpoint file content from context.checkpoint
    3. Provider output (text description of what was done)

    The result must be self-contained: actual file contents and diffs,
    not references to local paths. A different node should be able to
    apply this work without access to the original filesystem.
    """
    context = task.get("context") or {}

    # Best: actual git diff (set by the runner when worktree has changes)
    diff = context.get("diff_content", "")
    if diff and len(diff) > 50:
        return f"Git diff from previous attempt (apply with `git apply`):\n\n{diff[:5000]}"

    # Good: checkpoint summary with file contents
    checkpoint = context.get("checkpoint", "")
    if checkpoint and len(checkpoint) > 50:
        return f"Checkpoint from previous attempt:\n\n{checkpoint[:3000]}"

    # Fallback: provider output text (descriptions, not code)
    output = (task.get("output") or "").strip()
    if output and len(output) > 50:
        return f"Provider output (may describe changes but not include full code):\n\n{output[:3000]}"

    return ""

def _find_spec_file(idea_id: str, task: dict[str, Any]) -> str:
    """Find the spec file path for an idea.

    Searches:
    1. The completed spec task's output for a path like specs/NNN-*.md
    2. The specs/ directory for files matching the idea slug
    3. The spec registry for linked spec IDs
    """
    import re
    from pathlib import Path

    # 1. Extract from the completed task output (spec tasks often say "Created specs/156-foo.md")
    output = (task.get("output") or "").strip()
    spec_mentions = re.findall(r'specs/[\w-]+\.md', output)
    if spec_mentions:
        # Verify the file exists
        repo_root = Path(__file__).resolve().parents[3]
        for mention in spec_mentions:
            if (repo_root / mention).exists():
                return mention

    # 2. Search specs/ directory by idea slug
    repo_root = Path(__file__).resolve().parents[3]
    specs_dir = repo_root / "specs"
    if specs_dir.exists():
        slug = idea_id.lower().replace("_", "-")
        # Try exact slug match
        for f in specs_dir.iterdir():
            if f.suffix == ".md" and slug in f.stem.lower():
                return f"specs/{f.name}"
        # Try partial word overlap
        slug_words = set(slug.split("-"))
        best_match = None
        best_overlap = 0
        for f in specs_dir.iterdir():
            if f.suffix != ".md":
                continue
            stem_words = set(f.stem.lower().split("-"))
            overlap = len(slug_words & stem_words)
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = f"specs/{f.name}"
        if best_match:
            return best_match

    # 3. Check spec registry
    try:
        from app.services import spec_registry_service
        specs = spec_registry_service.list_specs(limit=500)
        for spec in specs:
            if spec.idea_id == idea_id:
                return f"specs/{spec.spec_id}.md" if not spec.content_path else spec.content_path
    except Exception:
        pass

    return ""


_NEXT_PHASE: dict[str, str | None] = {
    "spec": "impl",
    "impl": "test",
    "test": "code-review",
    "code-review": "deploy",          # R1: code-review → deploy (Spec 159)
    "deploy": "verify-production",    # R1: deploy → verify-production (Spec 159)
    "verify-production": None,        # R1: terminal — triggers validated status (Spec 159)
    "review": None,                   # backward compat: legacy dead-end
    "verify": None,                   # backward compat
    "heal": None,
}

# All phases downstream of a given phase — used for cascade invalidation
_DOWNSTREAM: dict[str, list[str]] = {
    "spec": ["impl", "test", "code-review", "deploy", "verify-production", "review"],
    "impl": ["test", "code-review", "deploy", "verify-production", "review"],
    "test": ["code-review", "deploy", "verify-production", "review"],
    "code-review": ["deploy", "verify-production"],  # R5: cascade includes deploy+verify
    "deploy": ["verify-production"],                 # R5
}

_PHASE_TASK_TYPE: dict[str, TaskType] = {
    "spec": TaskType.SPEC,
    "impl": TaskType.IMPL,
    "test": TaskType.TEST,
    "code-review": TaskType.CODE_REVIEW,
    "deploy": TaskType.DEPLOY,           # R1: deploy phase task type
    "verify-production": TaskType.VERIFY, # R1: verify-production phase task type
}

# Minimum output length to consider a task genuinely completed.
# Text-only providers (openrouter/free) often claim completion with 0 output.
_MIN_OUTPUT_CHARS: dict[str, int] = {
    "spec": 100,             # A real spec is at least a paragraph
    "impl": 200,             # A real impl must describe files changed + verification
    "test": 100,             # A real test run must show test results
    "code-review": 30,       # A review at least says PASSED or FAILED
    "deploy": 50,            # Health check output
    "verify-production": 50, # curl scenario output
    "verify": 50,            # alias for verify-production (TaskType.VERIFY.value)
}

# Pass-gate tokens: if the completed task output does NOT contain this token,
# the advance is blocked even if status is "completed".
_PASS_GATE_TOKEN: dict[str, str] = {
    "code-review": "CODE_REVIEW_PASSED",   # R2: must contain explicit pass signal
}

# Phases that MUST produce code (git diff). Text output alone is not enough.
_CODE_REQUIRED_PHASES = {"impl", "test"}


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

    # DIF verification evidence — extract eventIds and persist for feedback loop
    if task_type in _CODE_REQUIRED_PHASES:
        import re
        dif_evidence = re.findall(r'DIF:\s*trust=(\w+),?\s*verify=(\d+)', output, re.IGNORECASE)
        event_ids = re.findall(r'eventId=([a-f0-9-]{8,})', output, re.IGNORECASE)
        if dif_evidence:
            dif_results = [
                {"trust": t, "verify": int(v), "eventId": event_ids[i] if i < len(event_ids) else ""}
                for i, (t, v) in enumerate(dif_evidence)
            ]
            # Persist DIF results for feedback loop
            try:
                from app.services import agent_service
                agent_service.update_task(
                    task.get("id", ""),
                    context={**(task.get("context") or {}), "dif_results": dif_results, "dif_verified": True},
                )
            except Exception:
                pass
            # Block if DIF flagged concerns
            concerns = [d for d in dif_results if d["trust"] == "concern"]
            if concerns:
                return False, f"DIF flagged {len(concerns)} concern(s) — code must be fixed before advancing"
            log.info("DIF_VERIFIED task=%s files=%d eventIds=%s", task.get("id", "?")[:16], len(dif_results), event_ids[:3])
        else:
            log.warning("DIF_MISSING task=%s type=%s — no DIF evidence in output", task.get("id", "?")[:16], task_type)

    return True, ""


def _set_idea_validated(idea_id: str) -> None:
    """Set idea manifestation_status=validated after verify-production passes (Spec 159 R5)."""
    try:
        from app.services import idea_service
        idea_service.update_idea(idea_id, manifestation_status="validated")
        log.info("IDEA_VALIDATED idea=%s after verify-production passed", idea_id)
    except Exception:
        log.warning("IDEA_VALIDATED failed for idea=%s", idea_id, exc_info=True)


def _handle_verify_failure(task: dict[str, Any], idea_id: str, output: str) -> None:
    """Handle verify-production failure — create urgent hotfix task and set regression status.

    Spec 159 R4: feature is publicly broken. Creates impl task with priority=urgent
    and context.hotfix=true. Sets manifestation_status=regression.
    """
    from app.services import agent_service
    idea_name = idea_id.replace("-", " ").replace("_", " ").title()

    # Create hotfix task with highest priority
    try:
        hotfix = agent_service.create_task(AgentTaskCreate(
            direction=(
                f"HOTFIX REQUIRED: '{idea_name}' ({idea_id}) verify-production FAILED.\n\n"
                f"The feature is publicly broken. Failing output:\n\n{output[:2000]}\n\n"
                f"Fix the regression so that all Verification Scenarios in the spec pass.\n"
                f"This is a live incident — highest priority."
            ),
            task_type=TaskType.IMPL,
            context={
                "idea_id": idea_id,
                "hotfix": True,
                "priority": "urgent",
                "failure_type": "verify_production_failure",
                "source_task_id": task.get("id", ""),
                "auto_advance_source": "pipeline_advance_service",
            },
        ))
        log.warning(
            "HOTFIX_CREATED idea=%s verify-production failed → hotfix task=%s",
            idea_id, hotfix.get("id", "?"),
        )
    except Exception:
        log.error("HOTFIX_CREATE_FAILED idea=%s", idea_id, exc_info=True)

    # Set idea manifestation_status=regression
    try:
        from app.services import idea_service
        idea_service.update_idea(idea_id, manifestation_status="regression")
        log.warning("IDEA_REGRESSION idea=%s — verify-production failed", idea_id)
    except Exception:
        log.warning("IDEA_REGRESSION update failed for idea=%s", idea_id, exc_info=True)


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

    output = (task.get("output") or "").strip()
    context = task.get("context") or {}
    idea_id = context.get("idea_id", "")

    # R2: Pass-gate check — code-review must contain CODE_REVIEW_PASSED (Spec 159)
    gate_token = _PASS_GATE_TOKEN.get(task_type)
    if gate_token and gate_token not in output:
        log.warning(
            "PASS_GATE blocked advance: type=%s idea=%s — output missing %s",
            task_type, idea_id or "?", gate_token,
        )
        return None

    # Normalize: TaskType.VERIFY has value "verify" but the phase is named "verify-production"
    # so we treat both as equivalent for the verify-production phase (Spec 159).
    _is_verify_phase = task_type in ("verify-production", "verify")

    # R4: verify-production failure — feature publicly broken (Spec 159)
    if _is_verify_phase and "VERIFY_FAILED" in output:
        if idea_id:
            _handle_verify_failure(task, idea_id, output)
        return None

    next_phase = _NEXT_PHASE.get(task_type)
    if not next_phase:
        # R5: verify-production with VERIFY_PASSED → set manifestation_status=validated
        if _is_verify_phase and "VERIFY_PASSED" in output and idea_id:
            _set_idea_validated(idea_id)
        return None

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

    # Find the spec file path for this idea
    spec_path = _find_spec_file(idea_id, task)
    idea_name = idea_id.replace("-", " ").replace("_", " ").title()

    DIF_VERIFY = (
        "DIF VERIFICATION (MANDATORY — task REJECTED without it):\n"
        "For EACH code file you create/modify, run:\n\n"
        "  DIF_RESULT=$(curl -s -X POST https://coherency-network.merly-mentor.ai/api/v2/dif/verify \\\n"
        "    -H 'Content-Type: application/json' \\\n"
        "    -d '{\"language\": \"LANG\", \"code\": \"FILE_CONTENTS\", \"response_mode\": \"script\", \"sensitivity\": 0}')\n"
        "  echo \"$DIF_RESULT\" | python3 -c \"import sys,json; d=json.load(sys.stdin); "
        "print(f'DIF: trust={d.get(\\\"trust_signal\\\",\\\"?\\\")}, verify={d.get(\\\"scores\\\",{}).get(\\\"verification\\\",\\\"?\\\")}, eventId={d.get(\\\"eventId\\\",\\\"?\\\")}')\"\n\n"
        "Replace LANG with: python, javascript, typescript\n"
        "Replace FILE_CONTENTS with actual code (escape \" as \\\").\n\n"
        "Your output MUST include for each file: DIF: trust=X, verify=Y, eventId=Z\n"
        "If trust_signal='concern': FIX the code and re-verify.\n"
        "If verification < 30: RETHINK your approach.\n\n"
    )

    if next_phase == "impl":
        if not spec_path:
            log.warning("AUTO_ADVANCE skip impl — no spec file found for %s", idea_id)
            return None
        direction = (
            f"Implement '{idea_name}' ({idea_id}).\n\n"
            f"The spec is at: {spec_path}\n"
            f"Read it and implement ONLY what it requires.\n\n"
            f"CRITICAL RULES:\n"
            f"- ONLY create or modify files listed in the spec's files_allowed section\n"
            f"- DO NOT delete, rename, or modify ANY other files in the repository\n"
            f"- DO NOT refactor, clean up, or reorganize existing code\n"
            f"- If the spec doesn't list a file, don't touch it\n"
            f"- The repo has many files you didn't write — leave them all as-is\n\n"
            f"{DIF_VERIFY}"
            f"Output: list every file you created/modified, what you changed, and the DIF line for each."
        )
    elif next_phase == "test":
        spec_hint = f"\nThe spec is at: {spec_path}\n" if spec_path else "\n"
        direction = (
            f"Write tests for '{idea_name}' ({idea_id}).\n{spec_hint}"
            f"Read the spec and write tests that verify its acceptance criteria.\n\n"
            f"CRITICAL RULES:\n"
            f"- ONLY create new test files (e.g. api/tests/test_*.py)\n"
            f"- DO NOT modify or delete ANY existing files\n"
            f"- Run your new tests and ensure they pass\n\n"
            f"{DIF_VERIFY}"
            f"Output: the test file path, number of tests, pass/fail results, and DIF line for each."
        )
    elif next_phase == "code-review":
        direction = (
            f"Code review for '{idea_name}' ({idea_id}).\n\n"
            f"Review the implementation against the spec's acceptance criteria:\n"
            f"1. Are the spec's files_allowed files created/modified correctly?\n"
            f"2. Do tests exist and cover key scenarios?\n"
            f"3. No unrelated files were modified or deleted?\n\n"
            f"{DIF_VERIFY}"
            f"Output CODE_REVIEW_PASSED or CODE_REVIEW_FAILED with DIF results + specific findings."
        )
    elif next_phase == "deploy":
        # R3: deploy phase — merge, build, deploy to VPS, health check (Spec 159)
        direction = (
            f"Deploy '{idea_name}' ({idea_id}) to production.\n\n"
            f"Steps:\n"
            f"1. Merge the feature branch to main: gh pr merge --squash --admin\n"
            f"2. SSH deploy: ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 "
            f"'cd /docker/coherence-network/repo && git pull origin main && "
            f"cd /docker/coherence-network && docker compose build --no-cache api web && "
            f"docker compose up -d api web'\n"
            f"3. Health check: curl -s https://api.coherencycoin.com/api/health\n\n"
            f"Pass gate: health check must return HTTP 200 with status ok.\n"
            f"On merge failure: output DEPLOY_FAILED: merge conflict — <details>.\n"
            f"On SSH/build failure: output DEPLOY_FAILED: <error>.\n"
            f"On success: output DEPLOY_PASSED: SHA <sha> live at coherencycoin.com.\n"
        )
    elif next_phase == "verify-production":
        # R4: verify-production phase — run spec scenarios against live production (Spec 159)
        spec_hint = f"\nSpec at: {spec_path}\n" if spec_path else "\n"
        direction = (
            f"Verify '{idea_name}' ({idea_id}) works in production.{spec_hint}\n"
            f"Run the spec's Verification Scenarios section against:\n"
            f"  - https://api.coherencycoin.com\n"
            f"  - https://coherencycoin.com\n\n"
            f"For each scenario use curl with Cache-Control: no-cache.\n"
            f"Record: URL + HTTP status + response snippet.\n\n"
            f"If ALL scenarios pass: output VERIFY_PASSED: <summary of results>.\n"
            f"If ANY scenario fails (404/500/wrong data): output VERIFY_FAILED: <failing scenario + output>.\n"
            f"No retries — if verify fails, it is a live incident.\n"
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
                "executor": "federation",
            },
        ))
        log.info(
            "AUTO_ADVANCE %s→%s for idea=%s created task=%s",
            task_type, next_phase, idea_id, created.get("id", "?"),
        )
        # Submit DIF feedback for the successfully advanced task
        if (task.get("context") or {}).get("dif_results"):
            try:
                feedback = submit_dif_feedback(task, ground_truth="positive", agent_action="accepted")
                if feedback:
                    log.info("DIF_FEEDBACK_SUBMITTED %d events for task=%s", len(feedback), task.get("id", "?")[:16])
            except Exception:
                pass
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

    # Reuse the original direction, enriched with partial work
    direction = task.get("direction", "")
    failed_provider = task.get("model", "") or context.get("provider", "")
    partial_work = _extract_partial_work(task)

    if partial_work:
        direction = (
            f"{direction}\n\n"
            f"--- PARTIAL WORK FROM PREVIOUS ATTEMPT ---\n"
            f"{partial_work}\n"
            f"--- END PARTIAL WORK ---\n\n"
            f"The previous attempt produced the code/content above but did not finish.\n"
            f"Apply these changes first, then complete the remaining work."
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
                "executor": "federation",
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


# ── DIF Feedback Loop ────────────────────────────────────────────


def submit_dif_feedback(
    task: dict[str, Any],
    ground_truth: str = "positive",
    agent_action: str = "accepted",
    confidence: float = 0.8,
) -> list[dict[str, Any]]:
    """Submit DIF feedback for all eventIds found in a completed task.

    Called after a task successfully advances through the pipeline.
    The feedback closes the loop: verify → implement → test → review → feedback.

    Returns list of submitted feedback records.
    """
    import httpx

    context = task.get("context") or {}
    dif_results = context.get("dif_results", [])
    if not dif_results:
        return []

    task_id = task.get("id", "")
    idea_id = context.get("idea_id", "")
    merly_base = "https://coherency-network.merly-mentor.ai"

    submitted = []
    for result in dif_results:
        event_id = result.get("eventId", "")
        if not event_id or event_id == "?":
            continue

        payload = {
            "eventId": event_id,
            "feedbackKind": "judgment",
            "groundTruth": ground_truth,
            "agentAction": agent_action,
            "confidence": confidence,
            "reasonCode": "pipeline_phase_passed",
            "notes": f"Task {task_id[:16]} for idea {idea_id} passed pipeline validation.",
            "resolutionState": "confirmed",
            "taskId": task_id,
            "evidence": {
                "idea_id": idea_id,
                "trust_signal": result.get("trust", ""),
                "verification_score": result.get("verify", 0),
            },
        }

        try:
            resp = httpx.post(
                f"{merly_base}/api/v2/dif/feedback",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                submitted.append({"eventId": event_id, "status": "submitted"})
                log.info("DIF_FEEDBACK submitted eventId=%s task=%s", event_id, task_id[:16])
            else:
                log.warning("DIF_FEEDBACK failed eventId=%s status=%d", event_id, resp.status_code)
        except Exception:
            log.warning("DIF_FEEDBACK error eventId=%s", event_id, exc_info=True)

    return submitted
