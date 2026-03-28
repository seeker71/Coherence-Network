"""Aggregated live pipeline snapshot for dashboard and public visibility."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        s = dt.isoformat()
        if isinstance(s, str) and s.endswith("+00:00"):
            return s.replace("+00:00", "Z")
        return s
    return str(dt)


def _json_safe_runners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        for key in ("lease_expires_at", "last_seen_at", "updated_at", "created_at"):
            if key in r:
                r[key] = _iso(r.get(key))
        out.append(r)
    return out


def _attach_idea_labels(idea_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not idea_rows:
        return idea_rows
    try:
        from app.services import idea_service

        listed = idea_service.list_ideas(limit=500)
        ideas = getattr(listed, "ideas", None) or []
        by_id: dict[str, Any] = {}
        for idea in ideas:
            iid = getattr(idea, "id", None)
            if iid:
                by_id[str(iid)] = idea
        enriched: list[dict[str, Any]] = []
        for row in idea_rows:
            r = dict(row)
            iid = str(r.get("idea_id") or "")
            if iid and iid in by_id:
                ob = by_id[iid]
                r["idea_name"] = getattr(ob, "name", None) or ""
                ms = getattr(ob, "manifestation_status", None)
                if hasattr(ms, "value"):
                    r["manifestation_status"] = str(ms.value)
                else:
                    r["manifestation_status"] = str(ms) if ms is not None else ""
            enriched.append(r)
        return enriched
    except Exception:
        logger.debug("idea label enrichment skipped", exc_info=True)
        return idea_rows


def get_live_pipeline_snapshot() -> dict[str, Any]:
    """Build a single JSON snapshot for the live pipeline dashboard."""
    now = datetime.now(timezone.utc)
    generated = now.isoformat().replace("+00:00", "Z")
    partial_errors: list[str] = []

    runners_raw: list[dict[str, Any]] = []
    try:
        from app.services import agent_runner_registry_service

        runners_raw = agent_runner_registry_service.list_runners(include_stale=False, limit=100)
    except Exception:
        logger.warning("live_pipeline: list_runners failed", exc_info=True)
        partial_errors.append("runners")

    pipeline: dict[str, Any] = {}
    try:
        from app.services import agent_service

        pipeline = agent_service.get_pipeline_status(now_utc=now)
    except Exception:
        logger.warning("live_pipeline: get_pipeline_status failed", exc_info=True)
        partial_errors.append("pipeline")
        pipeline = {}

    metrics: dict[str, Any] = {}
    try:
        from app.services.metrics_service import get_aggregates

        metrics = get_aggregates(window_days=7)
    except Exception:
        logger.warning("live_pipeline: metrics failed", exc_info=True)
        partial_errors.append("metrics")
        metrics = {}

    effectiveness: dict[str, Any] = {}
    try:
        from app.services.effectiveness_service import get_effectiveness as _eff

        effectiveness = _eff()
    except Exception:
        logger.warning("live_pipeline: effectiveness failed", exc_info=True)
        partial_errors.append("effectiveness")
        effectiveness = {}

    prompt_ab: dict[str, Any] = {}
    try:
        from app.services import prompt_ab_roi_service

        prompt_ab = prompt_ab_roi_service.get_variant_stats()
    except Exception:
        logger.warning("live_pipeline: prompt_ab failed", exc_info=True)
        partial_errors.append("prompt_ab")
        prompt_ab = {}

    ideas_motion: list[dict[str, Any]] = []
    try:
        from app.services import runtime_service

        payload = runtime_service.cached_runtime_ideas_summary_payload(
            seconds=3600,
            limit=15,
            offset=0,
            event_limit=800,
            force_refresh=False,
        )
        raw_ideas = payload.get("ideas") if isinstance(payload, dict) else []
        if isinstance(raw_ideas, list):
            ideas_motion = _attach_idea_labels([x for x in raw_ideas if isinstance(x, dict)])
    except Exception:
        logger.warning("live_pipeline: runtime ideas summary failed", exc_info=True)
        partial_errors.append("ideas_in_motion")

    running = pipeline.get("running") if isinstance(pipeline.get("running"), list) else []
    pending = pipeline.get("pending") if isinstance(pipeline.get("pending"), list) else []
    recent = pipeline.get("recent_completed") if isinstance(pipeline.get("recent_completed"), list) else []
    diagnostics = pipeline.get("diagnostics") if isinstance(pipeline.get("diagnostics"), dict) else {}

    runners_safe = _json_safe_runners(runners_raw)
    online = len(runners_safe)

    summary = {
        "runners_online": online,
        "tasks_running": len(running),
        "tasks_pending": len(pending),
        "queue_depth": len(pending),
        "recent_completions_visible": len(recent),
        "pipeline_healthy": online > 0 or len(running) > 0 or len(pending) > 0,
    }

    by_model = metrics.get("by_model") if isinstance(metrics.get("by_model"), dict) else {}
    success_rate = metrics.get("success_rate") if isinstance(metrics.get("success_rate"), dict) else {}

    return {
        "generated_at": generated,
        "summary": summary,
        "runners": {
            "online_count": online,
            "items": runners_safe,
        },
        "execution": {
            "running": running,
            "pending": pending,
            "recent_completed": recent,
            "running_by_phase": pipeline.get("running_by_phase") or {},
            "attention": pipeline.get("attention") or {},
            "latest_request": pipeline.get("latest_request"),
            "latest_response": pipeline.get("latest_response"),
            "diagnostics": diagnostics,
        },
        "providers": {
            "window_days": 7,
            "success_rate": success_rate,
            "by_model": by_model,
            "execution_time": metrics.get("execution_time") or {},
        },
        "effectiveness": effectiveness,
        "prompt_ab": prompt_ab,
        "ideas_in_motion": ideas_motion,
        "partial_errors": partial_errors,
    }
