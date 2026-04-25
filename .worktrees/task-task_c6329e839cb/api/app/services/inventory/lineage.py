"""System lineage inventory: ideas, questions, links, runtime."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import idea_service, runtime_service, value_lineage_service
from app.services.inventory.cache import (
    _cache_key,
    _inventory_environment_cache_key,
    _inventory_timing_enabled,
    _inventory_timing_ms_threshold,
    _read_inventory_cache,
    _write_inventory_cache,
)
from app.services.inventory.constants import _answer_roi, _question_roi
from app.services.inventory.constants import logger
from app.services.inventory.spec_discovery import (
    _discover_specs,
    _idea_api_path,
    _project_root,
    _spec_api_path,
)


def _build_lineage_idea_items(ideas_response: Any) -> list[dict]:
    return [
        {
            **item.model_dump(mode="json"),
            "api_path": _idea_api_path(item.id),
        }
        for item in ideas_response.ideas
    ]


def _build_lineage_question_rows(ideas_response: Any) -> tuple[list[dict], list[dict]]:
    answered_questions: list[dict] = []
    unanswered_questions: list[dict] = []
    for idea in ideas_response.ideas:
        for q in idea.open_questions:
            row = {
                "idea_id": idea.id,
                "idea_api_path": _idea_api_path(idea.id),
                "idea_name": idea.name,
                "question": q.question,
                "value_to_whole": q.value_to_whole,
                "estimated_cost": q.estimated_cost,
                "question_roi": _question_roi(q.value_to_whole, q.estimated_cost),
                "answer": q.answer,
                "measured_delta": q.measured_delta,
                "answer_roi": _answer_roi(q.measured_delta, q.estimated_cost),
            }
            if q.answer:
                answered_questions.append(row)
            else:
                unanswered_questions.append(row)
    unanswered_questions.sort(key=lambda x: -float(x.get("question_roi") or 0.0))
    answered_questions.sort(
        key=lambda x: (
            -float(x.get("answer_roi") or 0.0),
            -float(x.get("question_roi") or 0.0),
        ),
    )
    return answered_questions, unanswered_questions


def _build_lineage_link_rows(
    lineage_link_limit: int = 300,
    usage_event_limit: int = 1000,
) -> tuple[list[dict], list, list]:
    links = value_lineage_service.list_links(limit=max(1, min(int(lineage_link_limit), 1000)))
    events = value_lineage_service.list_usage_events(limit=max(1, min(int(usage_event_limit), 5000)))
    rows: list[dict] = []
    for link in links:
        valuation = value_lineage_service.valuation(link.id)
        rows.append(
            {
                "lineage_id": link.id,
                "idea_id": link.idea_id,
                "idea_api_path": _idea_api_path(link.idea_id),
                "spec_id": link.spec_id,
                "spec_api_path": _spec_api_path(link.spec_id),
                "implementation_refs": link.implementation_refs,
                "estimated_cost": link.estimated_cost,
                "valuation": valuation.model_dump(mode="json") if valuation else None,
            }
        )
    return rows, links, events


def build_system_lineage_inventory(
    runtime_window_seconds: int = 3600,
    lineage_link_limit: int = 300,
    usage_event_limit: int = 1000,
    runtime_event_limit: int = 2000,
) -> dict:
    start_ms = time.perf_counter()
    cache_key = _cache_key(
        "system-lineage",
        runtime_window_seconds,
        lineage_link_limit,
        usage_event_limit,
        runtime_event_limit,
        _inventory_environment_cache_key(),
    )
    cached = _read_inventory_cache("system_lineage", cache_key)
    if cached is not None:
        if _inventory_timing_enabled():
            logger.warning("inventory_cache_hit endpoint=system-lineage key=%s", cache_key)
        return cached

    stage_timings: dict[str, float] = {}
    stage_start = time.perf_counter()
    ideas_response = idea_service.list_ideas()
    stage_timings["ideas"] = round((time.perf_counter() - stage_start) * 1000.0, 2)
    stage_start = time.perf_counter()
    ideas = _build_lineage_idea_items(ideas_response)
    answered_questions, unanswered_questions = _build_lineage_question_rows(ideas_response)
    stage_timings["lineage_map"] = round((time.perf_counter() - stage_start) * 1000.0, 2)
    stage_start = time.perf_counter()
    link_rows, links, events = _build_lineage_link_rows(
        lineage_link_limit=lineage_link_limit,
        usage_event_limit=usage_event_limit,
    )
    stage_timings["lineage_links"] = round((time.perf_counter() - stage_start) * 1000.0, 2)
    stage_start = time.perf_counter()

    runtime_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=max(60, min(runtime_window_seconds, 60 * 60 * 24 * 30))
    )
    runtime_events = runtime_service.list_events(
        limit=runtime_event_limit,
        since=runtime_cutoff,
    )
    stage_timings["runtime_events"] = round((time.perf_counter() - stage_start) * 1000.0, 2)
    stage_start = time.perf_counter()
    runtime_summary = [
        x.model_dump(mode="json")
        for x in runtime_service.summarize_by_idea(
            seconds=runtime_window_seconds,
            event_limit=runtime_event_limit,
            event_rows=runtime_events,
        )
    ]
    stage_timings["runtime_summary"] = round((time.perf_counter() - stage_start) * 1000.0, 2)
    stage_start = time.perf_counter()
    spec_items, spec_source = _discover_specs()
    tracked_idea_ids = idea_service.list_tracked_idea_ids()
    stage_timings["spec_discovery"] = round((time.perf_counter() - stage_start) * 1000.0, 2)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ideas": {
            "summary": ideas_response.summary.model_dump(mode="json"),
            "items": ideas,
        },
        "questions": {
            "total": len(answered_questions) + len(unanswered_questions),
            "answered_count": len(answered_questions),
            "unanswered_count": len(unanswered_questions),
            "answered": answered_questions,
            "unanswered": unanswered_questions,
        },
        "specs": {
            "count": len(spec_items),
            "source": spec_source,
            "items": spec_items,
        },
        "implementation_usage": {
            "lineage_links_count": len(link_rows),
            "usage_events_count": len(events),
            "lineage_links": link_rows,
        },
        "runtime": {
            "window_seconds": runtime_window_seconds,
            "ideas": runtime_summary,
        },
        "tracking": {
            "tracked_idea_ids_count": len(tracked_idea_ids),
            "tracked_idea_ids": tracked_idea_ids,
            "tracked_ideas": [
                {"idea_id": idea_id, "api_path": _idea_api_path(idea_id)}
                for idea_id in tracked_idea_ids
            ],
            "spec_discovery_source": spec_source,
            "runtime_events_count": len(runtime_events),
            "commit_evidence_local_available": (_project_root() / "docs" / "system_audit").exists(),
        },
    }
    if _inventory_timing_enabled():
        payload["_timing_ms"] = stage_timings
    elapsed_ms = round((time.perf_counter() - start_ms) * 1000.0, 2)
    if _inventory_timing_enabled() and elapsed_ms >= _inventory_timing_ms_threshold():
        logger.warning(
            "inventory_timing endpoint=system-lineage elapsed_ms=%s cache=miss details=%s",
            elapsed_ms,
            ", ".join(f"{k}={v}ms" for k, v in stage_timings.items()),
        )
    _write_inventory_cache("system_lineage", cache_key, payload)
    return payload
