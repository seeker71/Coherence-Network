"""Auto-heal from diagnostics: maps error categories to heal strategies. Spec 114."""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.models.agent import AgentTaskCreate, TaskType
from app.services.failed_task_diagnostics_service import classify_error


HEAL_STRATEGIES: dict[str, dict[str, Any]] = {
    "timeout": {
        "direction_template": (
            "Heal: task {source_task_id} failed with timeout.\n"
            "Error: {error_summary}\n\n"
            "Retry with extended observation window. If the task involves network calls, "
            "add explicit timeouts and retry logic. Check for resource contention."
        ),
        "executor_hint": None,
        "max_retries": 2,
        "cooldown_seconds": 600,
    },
    "executor_crash": {
        "direction_template": (
            "Heal: task {source_task_id} crashed.\n"
            "Error: {error_summary}\n\n"
            "Investigate the crash. Check executor logs and dependencies. "
            "If the crash is in a specific file, read and fix that file. "
            "Run the original acceptance commands to verify."
        ),
        "executor_hint": "claude",
        "max_retries": 2,
        "cooldown_seconds": 300,
    },
    "provider_error": {
        "direction_template": (
            "Heal: task {source_task_id} hit a provider error.\n"
            "Error: {error_summary}\n\n"
            "The provider returned a rate limit or billing error. "
            "Route to a different provider or wait for quota reset. "
            "Check provider readiness before retrying."
        ),
        "executor_hint": "openrouter",
        "max_retries": 3,
        "cooldown_seconds": 900,
    },
    "validation_failure": {
        "direction_template": (
            "Heal: task {source_task_id} failed validation.\n"
            "Error: {error_summary}\n\n"
            "Fix the validation issue. Read the spec acceptance criteria, "
            "identify which assertion failed, and apply the minimal fix. "
            "Run the failed validation command to verify."
        ),
        "executor_hint": None,
        "max_retries": 2,
        "cooldown_seconds": 120,
    },
    "unknown": {
        "direction_template": (
            "Heal: task {source_task_id} failed with unknown error.\n"
            "Error: {error_summary}\n\n"
            "Analyze the task output and attempt to diagnose the root cause. "
            "If the error is not actionable, escalate by setting status to needs_decision."
        ),
        "executor_hint": None,
        "max_retries": 1,
        "cooldown_seconds": 1800,
    },
}


def _default_store_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "auto_heal_records.json"


def _load_records(store_path: Path) -> list[dict]:
    if not store_path.exists():
        return []
    try:
        with open(store_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_record(record: dict, store_path: Path) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with open(store_path, "a+" if store_path.exists() else "w+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            records: list[dict] = json.loads(content) if content else []
            records.append(record)
            f.seek(0)
            f.truncate()
            json.dump(records, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def maybe_create_heal_task(
    failed_task: dict,
    *,
    store_path: Path | None = None,
    task_creator: Callable | None = None,
) -> dict | None:
    """Inspect a failed task, classify its error, and create a heal task if eligible.

    Returns the heal task dict or None if suppressed.
    """
    store = store_path or _default_store_path()
    context = failed_task.get("context") or {}
    task_id = failed_task.get("id", "unknown")

    # Guard: already has a heal task
    if context.get("heal_task_id"):
        return None

    # Guard: retry limit exceeded
    retry_count = int(context.get("retry_count", 0))

    # Classify error
    error_category = failed_task.get("error_category")
    error_summary = failed_task.get("error_summary")
    if not error_category:
        output = failed_task.get("output")
        error_summary, error_category = classify_error(output)

    strategy = HEAL_STRATEGIES.get(error_category, HEAL_STRATEGIES["unknown"])

    if retry_count >= strategy["max_retries"]:
        return None

    # Guard: cooldown — check if a heal for same category was created recently
    records = _load_records(store)
    now = datetime.now(timezone.utc)
    cooldown = strategy["cooldown_seconds"]
    for rec in reversed(records):
        if rec.get("error_category") != error_category:
            continue
        try:
            rec_time = datetime.fromisoformat(rec["created_at"])
            elapsed = (now - rec_time).total_seconds()
            if elapsed < cooldown:
                return None
        except (KeyError, ValueError):
            continue
        break  # only check most recent for this category

    # Build heal task
    direction = strategy["direction_template"].format(
        source_task_id=task_id,
        error_summary=error_summary or "No details",
    )

    heal_context = {
        "source_task_id": task_id,
        "error_category": error_category,
        "error_summary": error_summary or "No details",
        "retry_count": retry_count + 1,
        "strategy_name": error_category,
    }
    if strategy.get("executor_hint"):
        heal_context["executor"] = strategy["executor_hint"]

    create_data = AgentTaskCreate(
        direction=direction,
        task_type=TaskType.HEAL,
        context=heal_context,
    )

    # Create the task
    if task_creator:
        heal_task = task_creator(create_data)
    else:
        from app.services import agent_service
        heal_task = agent_service.create_task(create_data)

    # Record for cooldown tracking
    record = {
        "source_task_id": task_id,
        "heal_task_id": heal_task.get("id", "unknown"),
        "error_category": error_category,
        "strategy_name": error_category,
        "created_at": now.isoformat(),
    }
    _save_record(record, store)

    return heal_task


def compute_auto_heal_stats(
    all_failed_tasks: list[dict],
    *,
    store_path: Path | None = None,
) -> dict:
    """Compute auto-heal statistics from heal records and failed tasks."""
    store = store_path or _default_store_path()
    records = _load_records(store)

    total_failed = len(all_failed_tasks)
    heals_created = len(records)
    heal_rate = min(1.0, heals_created / total_failed) if total_failed > 0 else 0.0

    # Build by-category stats
    healed_by_cat: dict[str, int] = {}
    for rec in records:
        cat = rec.get("error_category", "unknown")
        healed_by_cat[cat] = healed_by_cat.get(cat, 0) + 1

    failed_by_cat: dict[str, int] = {}
    for t in all_failed_tasks:
        cat = t.get("error_category")
        if not cat:
            output = t.get("output")
            _, cat = classify_error(output)
        failed_by_cat[cat] = failed_by_cat.get(cat, 0) + 1

    by_category: dict[str, dict[str, int]] = {}
    all_cats = set(failed_by_cat.keys()) | set(healed_by_cat.keys())
    for cat in all_cats:
        f = failed_by_cat.get(cat, 0)
        h = healed_by_cat.get(cat, 0)
        by_category[cat] = {
            "failed": f,
            "healed": h,
            "suppressed": max(0, f - h),
        }

    return {
        "total_failed": total_failed,
        "heals_created": heals_created,
        "heal_rate": round(heal_rate, 2),
        "by_category": by_category,
    }
