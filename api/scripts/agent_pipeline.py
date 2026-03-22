#!/usr/bin/env python3
"""Background idea-driven pipeline loop (spec 139)."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from app.services import pipeline_service

try:
    from scripts import local_runner
except Exception:  # pragma: no cover - defensive fallback for import edge cases
    local_runner = None

LOG = logging.getLogger("agent_pipeline")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_API_DIR / "logs" / "agent_pipeline_runner.log"),
    ],
)

API_BASE = os.getenv("AGENT_API_BASE", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("COHERENCE_API_KEY") or os.getenv("API_KEY") or ""
HTTP = httpx.Client(timeout=30.0)
STOP_REQUESTED = False


def _headers() -> dict[str, str]:
    if not API_KEY:
        return {}
    return {"X-API-Key": API_KEY}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_failure(output: str) -> str:
    if local_runner and hasattr(local_runner, "classify_error"):
        return str(local_runner.classify_error(output or ""))
    text = (output or "").lower()
    if "timeout" in text:
        return "timeout"
    if "unauthorized" in text or "forbidden" in text or "auth" in text:
        return "auth"
    if "rate limit" in text or "429" in text:
        return "rate_limit"
    return "unknown"


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    resp = HTTP.request(method, url, headers=_headers(), json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {resp.status_code} {resp.text[:400]}")
    return resp.json() if resp.text else {}


def fetch_ideas() -> list[dict[str, Any]]:
    payload = _request("GET", "/api/ideas?limit=500&offset=0")
    return list(payload.get("ideas") or [])


def has_active_task(idea_id: str) -> bool:
    payload = _request("GET", f"/api/ideas/{idea_id}/tasks")
    for group in payload.get("groups") or []:
        counts = group.get("status_counts") or {}
        if int(counts.get("pending", 0)) > 0 or int(counts.get("running", 0)) > 0:
            return True
    return False


def build_direction(idea: dict[str, Any], task_type: str) -> str:
    title = str(idea.get("name") or idea.get("id") or "idea").strip()
    description = str(idea.get("description") or "").strip()
    stage = str(idea.get("stage") or "none")
    return (
        f"Idea pipeline task for '{title}'. "
        f"Current stage: {stage}. "
        f"Run {task_type} work next. "
        f"Description: {description}"
    )


def create_agent_task(idea: dict[str, Any], task_type: str) -> dict[str, Any]:
    idea_id = str(idea.get("id") or "").strip()
    if not idea_id:
        raise RuntimeError("Cannot create task without idea id")
    return _request(
        "POST",
        "/api/agent/tasks",
        payload={
            "direction": build_direction(idea, task_type),
            "task_type": task_type,
            "context": {
                "idea_id": idea_id,
                "idea_stage": idea.get("stage"),
                "pipeline_source": "agent_pipeline",
                "roi_score": pipeline_service.roi_score(idea),
            },
        },
    )


def run_local_runner(task_id: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "scripts/local_runner.py", "--task", task_id],
        cwd=str(_API_DIR),
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode == 0, output.strip()


def advance_idea(idea_id: str) -> None:
    url = f"{API_BASE}/api/ideas/{idea_id}/advance"
    resp = HTTP.post(url, headers=_headers())
    if resp.status_code in (200, 201, 409):
        return
    raise RuntimeError(f"advance failed: {resp.status_code} {resp.text[:400]}")


def process_idea(idea: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    idea_id = str(idea.get("id") or "")
    stage = str(idea.get("stage") or "none").strip().lower()
    task_type = pipeline_service.task_type_for_stage(stage)
    started = time.perf_counter()
    provider = "local_runner"

    if not task_type:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "idea_id": idea_id,
            "task_type": "",
            "provider": provider,
            "status": "skipped",
            "duration_ms": duration_ms,
            "error_classification": None,
        }

    if dry_run:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "idea_id": idea_id,
            "task_type": task_type,
            "provider": provider,
            "status": "skipped",
            "duration_ms": duration_ms,
            "error_classification": None,
        }

    backoff = pipeline_service.RETRY_BACKOFF_SECONDS
    max_retries = len(backoff)
    output = ""
    error_class = "unknown"
    for attempt in range(max_retries + 1):
        task = create_agent_task(idea, task_type)
        task_id = str(task.get("id") or "")
        success, output = run_local_runner(task_id)
        if success:
            advance_idea(idea_id)
            pipeline_service.mark_task_completed()
            pipeline_service.mark_idea_advanced()
            duration_ms = int((time.perf_counter() - started) * 1000)
            return {
                "idea_id": idea_id,
                "task_type": task_type,
                "provider": provider,
                "status": "completed",
                "duration_ms": duration_ms,
                "error_classification": None,
            }
        error_class = classify_failure(output)
        if attempt < max_retries:
            time.sleep(backoff[attempt])
            continue
        pipeline_service.mark_task_failed()
        pipeline_service.mark_needs_attention(idea_id)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "idea_id": idea_id,
            "task_type": task_type,
            "provider": provider,
            "status": "failed",
            "duration_ms": duration_ms,
            "error_classification": error_class,
            "output": output[:1000],
        }

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "idea_id": idea_id,
        "task_type": task_type,
        "provider": provider,
        "status": "failed",
        "duration_ms": duration_ms,
        "error_classification": error_class,
        "output": output[:1000],
    }


def run_cycle(*, dry_run: bool = False) -> list[dict[str, Any]]:
    pipeline_service.mark_cycle()
    ideas = fetch_ideas()
    candidates: list[dict[str, Any]] = []
    for idea in ideas:
        idea_id = str(idea.get("id") or "")
        if not idea_id:
            continue
        if pipeline_service.is_needs_attention(idea_id):
            continue
        if has_active_task(idea_id):
            continue
        candidates.append(idea)

    selected = pipeline_service.rank_candidate_ideas(
        candidates, top_n=pipeline_service.DEFAULT_CONCURRENCY
    )
    if not selected:
        return []

    pipeline_service.set_current_idea(str(selected[0].get("id") or ""))
    results: list[dict[str, Any]] = []
    max_workers = min(pipeline_service.DEFAULT_CONCURRENCY, len(selected))
    if max_workers <= 1:
        for idea in selected:
            results.append(process_idea(idea, dry_run=dry_run))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(process_idea, idea, dry_run) for idea in selected]
            for future in as_completed(futures):
                results.append(future.result())
    pipeline_service.set_current_idea(None)
    for result in results:
        payload = {
            "timestamp": _utc_now(),
            "cycle": pipeline_service.get_status().get("cycle_count", 0),
            "idea_id": result.get("idea_id"),
            "task_type": result.get("task_type"),
            "provider": result.get("provider"),
            "status": result.get("status"),
            "duration_ms": result.get("duration_ms", 0),
        }
        pipeline_service.append_cycle_log(payload)
    pipeline_service.persist_state()
    return results


def _signal_handler(_signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    LOG.info("Shutdown requested; finishing current cycle")


def run(*, once: bool = False, dry_run: bool = False, interval: int = 60) -> int:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    pipeline_service.load_state()
    pipeline_service.start()
    pipeline_service.persist_state()

    try:
        if once:
            run_cycle(dry_run=dry_run)
            return 0

        while not STOP_REQUESTED:
            run_cycle(dry_run=dry_run)
            if STOP_REQUESTED:
                break
            time.sleep(max(1, interval))
        return 0
    finally:
        pipeline_service.stop()
        pipeline_service.persist_state()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coherence agent idea pipeline loop")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--once", action="store_true", help="Run exactly one cycle")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--interval", type=int, default=pipeline_service.DEFAULT_POLL_INTERVAL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    once = bool(args.once or not args.loop)
    return run(once=once, dry_run=args.dry_run, interval=int(args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
