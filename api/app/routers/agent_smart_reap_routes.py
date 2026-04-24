"""Smart-reap routes: diagnose stuck tasks before marking them timed_out.

Spec: smart-reap-diagnose-resume

POST /agent/smart-reap/run  — Diagnose and reap (or extend) stuck tasks.
GET  /agent/smart-reap/preview — Preview which tasks would be reaped without acting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from app.models.agent import TaskStatus
from app.services import agent_service
from app.services.agent_runner_registry_service import list_runners
from app.services.smart_reaper_service import diagnose_batch
from app.services.config_service import get_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_log_dir_default() -> Path:
    """Get default log directory from config."""
    config = get_config()
    log_dir = config.get("agent_task_log_dir")
    if log_dir:
        return Path(log_dir)
    return Path("data/task_logs")


def _get_max_age_minutes_default() -> int:
    """Get default max age minutes from config."""
    config = get_config()
    max_age = config.get("smart_reap_max_age_minutes")
    if max_age is not None:
        try:
            return int(max_age)
        except (TypeError, ValueError):
            pass
    return 15


def _get_log_dir() -> Path:
    """Return the task log directory, ensuring it exists."""
    d = _get_log_dir_default()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_stuck_tasks(max_age_minutes: int) -> list[dict[str, Any]]:
    """Return running tasks that have been active longer than max_age_minutes."""
    items, _total, _extra = agent_service.list_tasks(
        status=TaskStatus.RUNNING,
        limit=200,
        offset=0,
    )
    now = datetime.now(timezone.utc)
    stuck = []
    for task in items:
        for key in ("started_at", "updated_at", "created_at"):
            raw = task.get(key)
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_min = (now - dt).total_seconds() / 60
                if age_min >= max_age_minutes:
                    stuck.append(task)
                break
            except Exception:
                continue
    return stuck


def _parse_task_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _weak_task_card_reason(task: dict[str, Any]) -> str | None:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    validation = ctx.get("task_card_validation") if isinstance(ctx.get("task_card_validation"), dict) else {}
    try:
        score = float(validation.get("score", 1.0))
    except (TypeError, ValueError):
        score = 1.0
    missing = validation.get("missing_fields") or validation.get("missing") or []
    missing_fields = [str(item).strip() for item in missing if str(item).strip()] if isinstance(missing, list) else []
    if score >= 0.4:
        return None
    if not missing_fields:
        return f"weak task card score={score:.2f}"
    return f"weak task card score={score:.2f}; missing {', '.join(missing_fields)}"


def _load_dormant_weak_pending_tasks(max_age_minutes: int) -> list[dict[str, Any]]:
    items, _total, _extra = agent_service.list_tasks(
        status=TaskStatus.PENDING,
        limit=200,
        offset=0,
    )
    now = datetime.now(timezone.utc)
    dormant = []
    for task in items:
        created = _parse_task_datetime(task.get("created_at"))
        if created is None:
            continue
        age_min = (now - created).total_seconds() / 60
        reason = _weak_task_card_reason(task)
        if age_min >= max_age_minutes and reason:
            next_task = dict(task)
            next_task["_quarantine_age_minutes"] = round(age_min, 1)
            next_task["_quarantine_reason"] = reason
            dormant.append(next_task)
    return dormant


def _apply_pending_quarantine(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    reason = str(task.get("_quarantine_reason") or "dormant malformed pending task")
    age_minutes = task.get("_quarantine_age_minutes")
    prompt = (
        "DORMANT_PENDING_QUARANTINE: This pending task is old and not executable as-is: "
        f"{reason}. Release it if obsolete, or requeue with a complete task card "
        "(goal, files_allowed, done_when, commands, constraints)."
    )
    context_patch = {
        "dormant_pending_quarantine": {
            "quarantined_at": now,
            "age_minutes": age_minutes,
            "reason": reason,
        }
    }
    updated = agent_service.update_task(
        task_id,
        status=TaskStatus.NEEDS_DECISION,
        decision_prompt=prompt,
        current_step="quarantined_dormant_pending",
        context=context_patch,
    )
    return updated or task


def _run_pending_quarantine(
    max_age_minutes: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if max_age_minutes is None:
        max_age_minutes = 24 * 60
    now = datetime.now(timezone.utc)
    candidates = _load_dormant_weak_pending_tasks(max_age_minutes)
    results: list[dict[str, Any]] = []
    quarantined = 0
    for task in candidates:
        task_id = str(task.get("id") or "")
        result = {
            "task_id": task_id,
            "action": "quarantine",
            "reason": task.get("_quarantine_reason"),
            "age_minutes": task.get("_quarantine_age_minutes"),
        }
        if not dry_run:
            _apply_pending_quarantine(task)
            quarantined += 1
        results.append(result)
    return {
        "checked": len(candidates),
        "quarantined": quarantined,
        "skipped": 0,
        "results": results,
        "dry_run": dry_run,
        "ts": now.isoformat().replace("+00:00", "Z"),
    }


def _apply_reap_result(task: dict[str, Any], diag: dict[str, Any]) -> dict[str, Any]:
    """Apply the diagnosis to the task: update status and merge context patch."""
    task_id = str(task.get("id") or "")
    context_patch = diag.get("context_patch") or {}

    # Merge partial output snippet into the diagnosis context
    if diag.get("has_partial") and diag.get("partial_output"):
        snippet = diag["partial_output"][-500:]
        ctx = dict(context_patch)
        diag_block = dict(ctx.get("smart_reap_diagnosis") or {})
        diag_block["partial_output_snippet"] = snippet
        ctx["smart_reap_diagnosis"] = diag_block
        context_patch = ctx

    try:
        updated = agent_service.update_task(
            task_id,
            status=TaskStatus.TIMED_OUT,
            output=diag.get("diagnosis_text", "Task timed out after smart reap diagnostics."),
            context=context_patch if context_patch else None,
        )
        return updated or task
    except Exception as exc:
        logger.warning("smart_reap: failed to update task %s: %s", task_id, exc)
        return task


def _apply_extend_result(task: dict[str, Any], diag: dict[str, Any]) -> dict[str, Any]:
    """Extend a slow task: update context with diagnosis but keep status=running."""
    task_id = str(task.get("id") or "")
    context_patch: dict[str, Any] = dict(diag.get("context_patch") or {})
    context_patch["extended_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        updated = agent_service.update_task(
            task_id,
            context=context_patch if context_patch else None,
        )
        return updated or task
    except Exception as exc:
        logger.warning("smart_reap: failed to extend task %s: %s", task_id, exc)
        return task


def _run_smart_reap(
    max_age_minutes: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Core smart-reap logic shared by preview and run endpoints."""
    if max_age_minutes is None:
        max_age_minutes = _get_max_age_minutes_default()
    now = datetime.now(timezone.utc)
    stuck_tasks = _load_stuck_tasks(max_age_minutes)

    if not stuck_tasks:
        return {
            "checked": 0,
            "reaped": 0,
            "extended": 0,
            "skipped": 0,
            "results": [],
            "dry_run": dry_run,
            "ts": now.isoformat().replace("+00:00", "Z"),
        }

    runners = list_runners(include_stale=True, limit=500)
    diagnoses = diagnose_batch(
        stuck_tasks,
        log_dir=_get_log_dir(),
        runners=runners,
        now=now,
        max_age_minutes=max_age_minutes,
    )

    reaped = 0
    extended = 0
    skipped = 0
    results: list[dict[str, Any]] = []

    for diag in diagnoses:
        task = diag["task"]
        task_id = str(task.get("id") or "")
        summary: dict[str, Any] = {
            "task_id": task_id,
            "error_class": diag["error_class"],
            "diagnosis": diag["diagnosis_text"],
            "runner_alive": diag["runner_alive"],
            "provider_pid_alive": diag["provider_pid_alive"],
            "partial_pct": round(diag["partial_pct"] * 100, 1),
            "has_partial": diag["has_partial"],
            "action": None,
        }

        if diag["should_reap"]:
            summary["action"] = "reap"
            if not dry_run:
                _apply_reap_result(task, diag)
            reaped += 1
            logger.info(
                "smart_reap: REAP task=%s error_class=%s partial=%.0f%% dry=%s",
                task_id, diag["error_class"], diag["partial_pct"] * 100, dry_run,
            )
        elif diag["should_extend"]:
            summary["action"] = "extend"
            if not dry_run:
                _apply_extend_result(task, diag)
            extended += 1
            logger.info(
                "smart_reap: EXTEND task=%s (slow_provider) age=%.1fmin dry=%s",
                task_id, diag.get("context_patch", {}).get("smart_reap_diagnosis", {}).get("age_min", 0), dry_run,
            )
        else:
            summary["action"] = "skip"
            skipped += 1

        results.append(summary)

    return {
        "checked": len(diagnoses),
        "reaped": reaped,
        "extended": extended,
        "skipped": skipped,
        "results": results,
        "dry_run": dry_run,
        "ts": now.isoformat().replace("+00:00", "Z"),
    }


@router.get("/smart-reap/preview", summary="Preview which stuck tasks would be reaped or extended — no state changes")
async def smart_reap_preview(
    max_age_minutes: int | None = Query(None, ge=0, le=1440),
) -> dict:
    """Preview which stuck tasks would be reaped or extended — no state changes."""
    return _run_smart_reap(max_age_minutes=max_age_minutes, dry_run=True)


@router.post("/smart-reap/run", summary="Diagnose stuck running tasks and reap or extend them")
async def smart_reap_run(
    max_age_minutes: int | None = Query(None, ge=0, le=1440),
) -> dict:
    """Diagnose stuck running tasks and reap or extend them.

    - runner_dead / provider_crashed / unknown → mark timed_out with diagnostic context
    - slow_provider (PID alive, age < max_age * 1.5) → extend timeout, keep running
    - Partial output >20% captured → checkpoint flag in context
    """
    return _run_smart_reap(max_age_minutes=max_age_minutes, dry_run=False)


@router.get("/smart-reap/pending-preview", summary="Preview dormant malformed pending tasks — no state changes")
async def pending_quarantine_preview(
    max_age_minutes: int | None = Query(None, ge=0, le=43200),
) -> dict:
    """Preview dormant malformed pending tasks that should move to needs_decision."""
    return _run_pending_quarantine(max_age_minutes=max_age_minutes, dry_run=True)


@router.post("/smart-reap/pending-quarantine", summary="Move dormant malformed pending tasks to needs_decision")
async def pending_quarantine_run(
    max_age_minutes: int | None = Query(None, ge=0, le=43200),
) -> dict:
    """Move stale, weak-task-card pending tasks out of runner circulation."""
    return _run_pending_quarantine(max_age_minutes=max_age_minutes, dry_run=False)
