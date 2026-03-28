"""Smart-reap API routes. Spec: smart-reap-diagnose-resume.

GET  /agent/smart-reap/preview - Dry-run diagnosis.
POST /agent/smart-reap/run     - Reap or extend stuck tasks.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Query
from app.models.agent import TaskStatus
from app.services import agent_service
from app.services.agent_runner_registry_service import list_runners
from app.services.smart_reaper_service import diagnose_batch
logger = logging.getLogger(__name__)
router = APIRouter()
_DEFAULT_LOG_DIR = Path(os.getenv("AGENT_TASK_LOG_DIR", "data/task_logs"))
_DEFAULT_MAX_AGE_MINUTES = int(os.getenv("SMART_REAP_MAX_AGE_MINUTES", "15"))
def _get_log_dir() -> Path:
    d = _DEFAULT_LOG_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d
def _load_stuck_tasks(max_age_minutes: int) -> list[dict[str, Any]]:
    items, _total, _extra = agent_service.list_tasks(status=TaskStatus.RUNNING, limit=200, offset=0)
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
                if (now - dt).total_seconds() / 60 >= max_age_minutes:
                    stuck.append(task)
                break
            except Exception:
                continue
    return stuck
def _run(max_age_minutes: int, dry_run: bool) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stuck_tasks = _load_stuck_tasks(max_age_minutes)
    if not stuck_tasks:
        return {"checked": 0, "reaped": 0, "extended": 0, "skipped": 0, "results": [], "dry_run": dry_run, "ts": now.isoformat().replace("+00:00", "Z")}
    runners = list_runners(include_stale=True, limit=500)
    diagnoses = diagnose_batch(stuck_tasks, log_dir=_get_log_dir(), runners=runners, now=now, max_age_minutes=max_age_minutes)
    reaped = extended = skipped = 0
    results: list[dict[str, Any]] = []
    for diag in diagnoses:
        task = diag["task"]
        task_id = str(task.get("id") or "")
        if diag["should_reap"]:
            action = "reap"
            if not dry_run:
                try:
                    agent_service.update_task(task_id, status=TaskStatus.TIMED_OUT, output=diag.get("diagnosis_text", "Smart reaped."), context=diag.get("context_patch") or None)
                except Exception as exc:
                    logger.warning("smart_reap reap failed %s: %s", task_id, exc)
            reaped += 1
        elif diag["should_extend"]:
            action = "extend"
            if not dry_run:
                try:
                    ctx_patch = dict(diag.get("context_patch") or {})
                    ctx_patch["extended_at"] = now.isoformat().replace("+00:00", "Z")
                    agent_service.update_task(task_id, context=ctx_patch or None)
                except Exception as exc:
                    logger.warning("smart_reap extend failed %s: %s", task_id, exc)
            extended += 1
        else:
            action = "skip"
            skipped += 1
        results.append({"task_id": task_id, "action": action, "error_class": diag["error_class"], "diagnosis": diag["diagnosis_text"], "runner_alive": diag["runner_alive"], "partial_pct": round(diag["partial_pct"] * 100, 1), "has_partial": diag["has_partial"]})
    return {"checked": len(diagnoses), "reaped": reaped, "extended": extended, "skipped": skipped, "results": results, "dry_run": dry_run, "ts": now.isoformat().replace("+00:00", "Z")}
@router.get("/smart-reap/preview")
async def smart_reap_preview(max_age_minutes: int = Query(_DEFAULT_MAX_AGE_MINUTES, ge=1, le=1440)) -> dict:
    """Preview which stuck tasks would be reaped/extended (no state changes)."""
    return _run(max_age_minutes=max_age_minutes, dry_run=True)
@router.post("/smart-reap/run")
async def smart_reap_run(max_age_minutes: int = Query(_DEFAULT_MAX_AGE_MINUTES, ge=1, le=1440)) -> dict:
    """Diagnose and reap stuck running tasks. Dead runners to timed_out; live but slow to extend."""
    return _run(max_age_minutes=max_age_minutes, dry_run=False)
