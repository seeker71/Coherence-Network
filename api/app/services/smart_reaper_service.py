"""Smart Reap Service — Spec 169.

Upgrades the reaper from blind timeout to diagnostic-first:
- Check runner liveness before marking timed_out
- Extend timeout for live runners (up to 2 times)
- Capture partial output from task logs on crash
- Write structured reap_diagnosis to task context
- Create resume tasks when partial output >= 20%
- Track per-idea timeout counts; flag needs_human_attention after 3 failures
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.failed_task_diagnostics_service import classify_error

logger = logging.getLogger(__name__)

# --- Constants ---
REAP_MAX_EXTENSIONS: int = 2
REAP_RUNNER_LIVENESS_SECONDS: int = int(os.environ.get("REAP_RUNNER_LIVENESS_SECONDS", "270"))
REAP_HUMAN_ATTENTION_THRESHOLD: int = int(os.environ.get("REAP_HUMAN_ATTENTION_THRESHOLD", "3"))
PARTIAL_RESUME_THRESHOLD_PCT: int = 20
MAX_LOG_BYTES: int = 4096
MAX_PARTIAL_IN_DIRECTION: int = 3000

# Heuristic expected-output lengths by task type (chars)
_EXPECTED_OUTPUT_BY_TYPE: dict[str, int] = {
    "spec": 3000,
    "impl": 5000,
    "test": 4000,
    "review": 2000,
}
_DEFAULT_EXPECTED_OUTPUT: int = 4000


def is_runner_alive(task: dict[str, Any], runners: list[dict[str, Any]]) -> bool:
    """Return True if the runner that claimed this task is still online.

    Checks whether the runner's last_seen_at is within REAP_RUNNER_LIVENESS_SECONDS.
    If claimed_by is None / empty, returns False immediately.

    Args:
        task: Task dict with at least 'claimed_by' field.
        runners: List of runner registry rows (each has 'runner_id', 'last_seen_at').
    """
    claimed_by = (task.get("claimed_by") or "").strip()
    if not claimed_by:
        return False

    now = datetime.now(timezone.utc)
    for runner in runners:
        rid = str(runner.get("runner_id") or "").strip()
        if rid != claimed_by:
            continue
        last_seen_raw = runner.get("last_seen_at")
        if not last_seen_raw:
            return False
        try:
            last_seen = datetime.fromisoformat(str(last_seen_raw).replace("Z", "+00:00"))
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            age_seconds = (now - last_seen).total_seconds()
            return age_seconds <= REAP_RUNNER_LIVENESS_SECONDS
        except Exception:
            return False
    # Runner not found in registry at all → assume dead
    return False


def get_extension_count(task: dict[str, Any]) -> int:
    """Return the number of reap extensions already granted for this task."""
    ctx = task.get("context") or {}
    return int(ctx.get("reap_extensions", 0))


def can_extend(task: dict[str, Any], max_age_minutes: int) -> bool:
    """Return True if this task is eligible for a timeout extension.

    Extension is only allowed when:
    - Extensions granted so far < REAP_MAX_EXTENSIONS
    - Task has not exceeded 3 × max_age_minutes
    """
    ext_count = get_extension_count(task)
    if ext_count >= REAP_MAX_EXTENSIONS:
        return False

    created = task.get("created_at", "")
    if not created:
        return False
    try:
        dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        return age_min <= 3 * max_age_minutes
    except Exception:
        return False


def capture_partial_output(task_id: str, log_dir: Path) -> tuple[str, int]:
    """Read the last MAX_LOG_BYTES from the task's on-disk log.

    Returns (partial_text, char_count). Returns ("", 0) if no log found.
    """
    log_path = log_dir / f"task_{task_id}.log"
    if not log_path.exists():
        return "", 0
    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as fh:
            if size > MAX_LOG_BYTES:
                fh.seek(-MAX_LOG_BYTES, 2)
            raw = fh.read(MAX_LOG_BYTES)
        text = raw.decode("utf-8", errors="replace")
        return text, len(text)
    except Exception as exc:
        logger.debug("smart_reap: could not read log for %s: %s", task_id, exc)
        return "", 0


def estimate_partial_pct(partial_chars: int, task_type: str, target_state: str | None = None) -> int:
    """Estimate how much of the expected output was produced (0–100)."""
    if partial_chars == 0:
        return 0
    if target_state:
        expected = max(len(target_state), 500)
    else:
        expected = _EXPECTED_OUTPUT_BY_TYPE.get(task_type, _DEFAULT_EXPECTED_OUTPUT)
    pct = int((partial_chars / expected) * 100)
    return min(pct, 100)


def build_resume_direction(original_direction: str, partial_output: str) -> str:
    """Compose a resume prompt that includes the partial work from the previous attempt."""
    truncated = partial_output[:MAX_PARTIAL_IN_DIRECTION]
    if len(partial_output) > MAX_PARTIAL_IN_DIRECTION:
        truncated += "\n[truncated]"
    prefix = "Previous attempt produced this partial work [attached]. Continue from where it left off.\n\n---\n"
    resume = prefix + truncated
    if original_direction:
        resume += f"\n\n---\nOriginal direction:\n{original_direction[:1000]}"
    return resume


def get_idea_timeout_count_from_tasks(
    idea_id: str,
    task_type: str,
    timed_out_tasks: list[dict[str, Any]],
) -> int:
    """Count how many timed_out tasks exist for the given idea_id + task_type.

    Scans the provided list of already-retrieved timed_out tasks (no extra API call).
    """
    count = 0
    for t in timed_out_tasks:
        if t.get("task_type") != task_type:
            continue
        ctx = t.get("context") or {}
        if str(ctx.get("idea_id", "")).strip() == idea_id:
            count += 1
    return count


def build_reap_diagnosis(
    *,
    runner_alive: bool,
    provider: str,
    partial_output: str,
    partial_chars: int,
    partial_pct: int,
    extensions_granted: int,
    resume_task_id: str | None,
    error_class: str,
) -> dict[str, Any]:
    """Build the reap_diagnosis dict to be written into task context."""
    return {
        "runner_alive": runner_alive,
        "provider": provider,
        "error_class": error_class,
        "partial_output_chars": partial_chars,
        "partial_output_pct": partial_pct,
        "extensions_granted": extensions_granted,
        "resume_task_id": resume_task_id,
        "reaped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def aggregate_reap_history(
    timed_out_tasks: list[dict[str, Any]],
    *,
    idea_id_filter: str | None = None,
    needs_attention_filter: bool | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Aggregate reap history from timed_out tasks.

    Groups by (idea_id, task_type) and returns summary records.
    Computes needs_human_attention if timeout_count >= REAP_HUMAN_ATTENTION_THRESHOLD.
    """
    # Build aggregation map: key → summary
    agg: dict[tuple[str, str], dict[str, Any]] = {}

    for t in timed_out_tasks:
        ctx = t.get("context") or {}
        tid = str(ctx.get("idea_id") or "").strip()
        ttype = str(t.get("task_type") or "").strip()
        if not tid:
            continue
        if idea_id_filter and tid != idea_id_filter:
            continue

        key = (tid, ttype)
        diag = ctx.get("reap_diagnosis") or {}
        reaped_at_raw = diag.get("reaped_at") or t.get("updated_at") or ""

        if key not in agg:
            agg[key] = {
                "idea_id": tid,
                "idea_name": str(ctx.get("idea_name") or tid[:30]),
                "task_type": ttype,
                "timeout_count": 0,
                "last_reaped_at": reaped_at_raw,
                "needs_human_attention": False,
                "last_error_class": diag.get("error_class") or "unknown",
                "last_partial_output_pct": diag.get("partial_output_pct") or 0,
            }

        entry = agg[key]
        entry["timeout_count"] += 1

        # Keep the most recent reaped_at
        if reaped_at_raw and str(reaped_at_raw) > str(entry["last_reaped_at"]):
            entry["last_reaped_at"] = reaped_at_raw
            entry["last_error_class"] = diag.get("error_class") or "unknown"
            entry["last_partial_output_pct"] = diag.get("partial_output_pct") or 0

        if entry["timeout_count"] >= REAP_HUMAN_ATTENTION_THRESHOLD:
            entry["needs_human_attention"] = True

    results = list(agg.values())

    # Apply needs_attention filter
    if needs_attention_filter is True:
        results = [r for r in results if r["needs_human_attention"]]
    elif needs_attention_filter is False:
        results = [r for r in results if not r["needs_human_attention"]]

    # Sort by last_reaped_at desc
    results.sort(key=lambda x: str(x.get("last_reaped_at") or ""), reverse=True)

    return results[:limit]


def smart_reap_task(
    task: dict[str, Any],
    *,
    runners: list[dict[str, Any]],
    timed_out_tasks: list[dict[str, Any]],
    log_dir: Path,
    max_age_minutes: int,
    api_fn: Any,  # callable(method, path, body) → dict|None
    send_alert_fn: Any | None = None,  # callable(text) → None
) -> dict[str, Any]:
    """Execute the smart reap decision for a single stale task.

    Returns a result dict with keys:
        action: "extended" | "reaped" | "skipped"
        task_id: str
        diagnosis: dict | None
    """
    task_id = task.get("id", "")
    task_type = task.get("task_type", "spec")
    ctx = task.get("context") or {}
    idea_id = str(ctx.get("idea_id") or "").strip()
    idea_name = str(ctx.get("idea_name") or idea_id or task_id[:20])
    provider = str(ctx.get("provider") or "unknown")
    extensions_granted = get_extension_count(task)

    # R10 — idempotency: check if already reaped (has reap_diagnosis)
    if ctx.get("reap_diagnosis"):
        logger.info("REAPER: task %s already reaped, skipping", task_id[:16])
        return {"action": "skipped", "task_id": task_id, "diagnosis": None}

    # R1 — Runner liveness check
    runner_alive = False
    try:
        runner_alive = is_runner_alive(task, runners)
    except Exception as exc:
        # Registry unavailable → assume alive, defer reap (R: failure mode)
        logger.warning("REAPER: runner liveness check failed for %s: %s — deferring", task_id[:16], exc)
        return {"action": "skipped", "task_id": task_id, "diagnosis": None}

    # R2 — Extend timeout for live runners
    if runner_alive and can_extend(task, max_age_minutes):
        new_ext_count = extensions_granted + 1
        patch_result = api_fn("PATCH", f"/api/agent/tasks/{task_id}", {
            "context": {**ctx, "reap_extensions": new_ext_count},
        })
        if patch_result:
            logger.info(
                "REAPER: extended timeout for %s (runner alive, ext %d/%d)",
                task_id[:16], new_ext_count, REAP_MAX_EXTENSIONS,
            )
            return {"action": "extended", "task_id": task_id, "diagnosis": None}
        # If patch failed, fall through to reap

    # R3 — Capture partial output from log
    partial_output, partial_chars = capture_partial_output(task_id, log_dir)

    # Classify the error
    _summary, error_class = classify_error(partial_output if partial_output else None)
    if not runner_alive and not partial_output:
        # No log, runner gone → executor_crash
        error_class = "executor_crash" if not error_class or error_class == "unknown" else error_class

    # R5 — Estimate partial output percentage
    target_state = task.get("target_state") or None
    partial_pct = estimate_partial_pct(partial_chars, task_type, target_state)

    # R6 — Compute idea timeout count BEFORE reaping (existing timed_out tasks)
    idea_timeout_count = 0
    if idea_id:
        idea_timeout_count = get_idea_timeout_count_from_tasks(idea_id, task_type, timed_out_tasks)
        # +1 for the current task being reaped now
        idea_timeout_count += 1

    needs_attention = idea_timeout_count >= REAP_HUMAN_ATTENTION_THRESHOLD

    # R5 — Create resume task if partial output >= 20% and not needs_human_attention
    resume_task_id: str | None = None
    if partial_pct >= PARTIAL_RESUME_THRESHOLD_PCT and idea_id and not needs_attention:
        original_direction = task.get("direction", ctx.get("direction", ""))
        resume_direction = build_resume_direction(original_direction, partial_output)
        retry_ctx = dict(ctx)
        retry_ctx["retry_count"] = int(ctx.get("retry_count", 0)) + 1
        retry_ctx["retried_from"] = task_id
        retry_ctx["failed_provider"] = provider
        retry_ctx["seed_source"] = "smart_reap_resume"
        retry_ctx["is_resume"] = True

        resume_result = api_fn("POST", "/api/agent/tasks", {
            "direction": resume_direction[:5000],
            "task_type": task_type,
            "context": retry_ctx,
            "target_state": task.get("target_state", f"{task_type.title()} completed for: {idea_name}"),
        })
        if resume_result and resume_result.get("id"):
            resume_task_id = resume_result["id"]
            logger.info(
                "REAPER: created resume task %s for %s (partial_pct=%d%%)",
                resume_task_id[:16], task_id[:16], partial_pct,
            )

    # R4 — Build structured diagnosis
    diagnosis = build_reap_diagnosis(
        runner_alive=runner_alive,
        provider=provider,
        partial_output=partial_output,
        partial_chars=partial_chars,
        partial_pct=partial_pct,
        extensions_granted=extensions_granted,
        resume_task_id=resume_task_id,
        error_class=error_class,
    )

    # Build updated context with diagnosis and reap history
    new_ctx = dict(ctx)
    new_ctx["reap_diagnosis"] = diagnosis
    if idea_id:
        new_ctx["reap_history"] = {
            "idea_id": idea_id,
            "timeout_count": idea_timeout_count,
            "needs_human_attention": needs_attention,
            "last_reaped_at": diagnosis["reaped_at"],
        }

    # R4 — Reap the task (PATCH to timed_out)
    reap_result = api_fn("PATCH", f"/api/agent/tasks/{task_id}", {
        "status": "timed_out",
        "output": f"Smart reaped: runner_alive={runner_alive}, error_class={error_class}, partial={partial_pct}%",
        "error_summary": f"Stale task reaped. Runner alive: {runner_alive}. Error: {error_class}",
        "error_category": error_class,
        "context": new_ctx,
    })

    if not reap_result:
        logger.warning("REAPER: PATCH timed_out failed for %s (already reaped?)", task_id[:16])
        return {"action": "skipped", "task_id": task_id, "diagnosis": None}

    logger.info(
        "REAPER: reaped %s (runner_alive=%s, error=%s, partial=%d%%, resume=%s, attention=%s)",
        task_id[:16], runner_alive, error_class, partial_pct,
        resume_task_id[:16] if resume_task_id else "none", needs_attention,
    )

    # R8 — Send Telegram alert for executor_crash or needs_human_attention
    if send_alert_fn and (error_class == "executor_crash" or needs_attention):
        try:
            attention_label = " [NEEDS HUMAN ATTENTION]" if needs_attention else ""
            msg = (
                f"REAPER{attention_label}: task {task_id[:16]} reaped\n"
                f"  idea: {idea_name[:40]}\n"
                f"  error: {error_class}\n"
                f"  partial: {partial_pct}%\n"
                f"  resume: {resume_task_id[:16] if resume_task_id else 'none'}"
            )
            send_alert_fn(msg)
        except Exception:
            pass

    return {"action": "reaped", "task_id": task_id, "diagnosis": diagnosis}


def diagnose_batch(
    tasks: list[dict[str, Any]],
    *,
    log_dir: Path,
    runners: list[dict[str, Any]],
    now: datetime,
    max_age_minutes: int,
) -> list[dict[str, Any]]:
    """Diagnose a batch of stuck tasks without applying any state changes.

    Returns a list of diagnosis dicts with keys used by agent_smart_reap_routes:
        task, error_class, diagnosis_text, runner_alive, provider_pid_alive,
        partial_pct (0.0-1.0), has_partial, partial_output,
        should_reap, should_extend, context_patch
    """
    results = []
    for task in tasks:
        task_id = str(task.get("id") or "")
        ctx = task.get("context") or {}
        task_type = str(task.get("task_type") or "spec")
        provider = str(ctx.get("provider") or "unknown")
        extensions_granted = get_extension_count(task)

        # R10 — idempotency
        if ctx.get("reap_diagnosis"):
            results.append({
                "task": task,
                "error_class": "already_reaped",
                "diagnosis_text": "Task already has reap_diagnosis; skipping.",
                "runner_alive": False,
                "provider_pid_alive": False,
                "partial_pct": 0.0,
                "has_partial": False,
                "partial_output": "",
                "should_reap": False,
                "should_extend": False,
                "context_patch": {},
            })
            continue

        # R1 — Runner liveness
        try:
            runner_alive = is_runner_alive(task, runners)
        except Exception:
            runner_alive = True  # Assume alive if registry unavailable

        # R3 — Capture partial output
        partial_output, partial_chars = capture_partial_output(task_id, log_dir)
        has_partial = partial_chars > 0

        # Classify error
        _summary, error_class = classify_error(partial_output if partial_output else None)
        if not runner_alive and not partial_output:
            error_class = "executor_crash" if not error_class or error_class == "unknown" else error_class

        # R5 — Estimate partial pct
        target_state = task.get("target_state") or None
        partial_pct_int = estimate_partial_pct(partial_chars, task_type, target_state)
        partial_pct = partial_pct_int / 100.0

        # R2 — Should extend?
        should_extend = runner_alive and can_extend(task, max_age_minutes)
        # R4 — Should reap (if not extending)?
        should_reap = not should_extend and not ctx.get("reap_diagnosis")

        # Build context_patch for reap_diagnosis
        diagnosis = build_reap_diagnosis(
            runner_alive=runner_alive,
            provider=provider,
            partial_output=partial_output,
            partial_chars=partial_chars,
            partial_pct=partial_pct_int,
            extensions_granted=extensions_granted,
            resume_task_id=None,
            error_class=error_class,
        )
        context_patch: dict[str, Any] = {**ctx, "smart_reap_diagnosis": diagnosis}

        # Build human-readable diagnosis text
        diagnosis_text = (
            f"Smart reap diagnosis: runner_alive={runner_alive}, "
            f"error_class={error_class}, partial={partial_pct_int}%"
        )

        results.append({
            "task": task,
            "error_class": error_class,
            "diagnosis_text": diagnosis_text,
            "runner_alive": runner_alive,
            "provider_pid_alive": runner_alive,  # best-effort proxy
            "partial_pct": partial_pct,
            "has_partial": has_partial,
            "partial_output": partial_output,
            "should_reap": should_reap,
            "should_extend": should_extend,
            "context_patch": context_patch,
        })

    return results
