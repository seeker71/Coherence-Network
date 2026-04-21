"""Event recording, listing, and live-change token for runtime telemetry."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.runtime import RuntimeEvent, RuntimeEventCreate
from app.services import (
    agent_task_store_service,
    runtime_event_store,
    telemetry_persistence_service,
)

from app.services.runtime import paths as runtime_paths
from app.services.runtime import cache as runtime_cache
from app.services.runtime import store as runtime_store
from app.services.runtime.routes import normalize_endpoint, normalize_path
from app.services.runtime.ideas import resolve_idea_id, resolve_origin_idea_id

_RUNTIME_EVENTS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "cache_key": "",
    "rows": [],
}
_RUNTIME_EVENTS_CACHE_TTL_SECONDS = 30.0

_LIVE_CHANGE_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "payload": {},
}
_LIVE_CHANGE_CACHE_TTL_SECONDS = 5.0


def _invalidate_runtime_events_cache() -> None:
    _RUNTIME_EVENTS_CACHE["expires_at"] = 0.0
    _RUNTIME_EVENTS_CACHE["rows"] = []

    try:
        from app.services import automation_usage_service

        automation_usage_service.invalidate_cache()
    except (ImportError, Exception):
        pass

    _RUNTIME_EVENTS_CACHE["rows"] = []


def list_events(
    limit: int = 100,
    since: datetime | None = None,
    source: str | None = None,
) -> list[RuntimeEvent]:
    requested_limit = max(1, min(int(limit), 5000))
    source_value = str(source or "").strip().lower()
    cache_key = runtime_cache.runtime_events_cache_key(
        requested_limit, since, source_value or None
    )
    now = time.time()
    if (
        _RUNTIME_EVENTS_CACHE.get("expires_at", 0.0) > now
        and _RUNTIME_EVENTS_CACHE.get("cache_key") == cache_key
        and isinstance(_RUNTIME_EVENTS_CACHE.get("rows"), list)
    ):
        return [row.model_copy(deep=True) for row in _RUNTIME_EVENTS_CACHE["rows"][:requested_limit]]

    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(
            limit=max(1, min(requested_limit, 5000)),
            since=since,
            source=source_value or None,
        )
        out: list[RuntimeEvent] = []
        for event in rows:
            try:
                if not event.raw_endpoint:
                    event.raw_endpoint = event.endpoint
                if source_value and str(event.source).strip().lower() != source_value:
                    continue
                event.endpoint = normalize_endpoint(event.endpoint, event.method)
                if not event.origin_idea_id:
                    event.origin_idea_id = resolve_origin_idea_id(event.idea_id)
                out.append(event)
            except Exception:
                continue
        out.sort(key=lambda x: x.recorded_at, reverse=True)
        out = out[:requested_limit]
        _RUNTIME_EVENTS_CACHE["expires_at"] = now + _RUNTIME_EVENTS_CACHE_TTL_SECONDS
        _RUNTIME_EVENTS_CACHE["cache_key"] = cache_key
        _RUNTIME_EVENTS_CACHE["rows"] = out
        return out

    data = runtime_store.read_store()
    out = []
    for raw in data["events"]:
        try:
            event = RuntimeEvent(**raw)
            if not event.raw_endpoint:
                event.raw_endpoint = event.endpoint
            if source_value and str(event.source).strip().lower() != source_value:
                continue
            event.endpoint = normalize_endpoint(event.endpoint, event.method)
            if not event.origin_idea_id:
                event.origin_idea_id = resolve_origin_idea_id(event.idea_id)
            out.append(event)
        except Exception:
            continue
    out.sort(key=lambda x: x.recorded_at, reverse=True)
    out = out[:requested_limit]
    _RUNTIME_EVENTS_CACHE["expires_at"] = now + _RUNTIME_EVENTS_CACHE_TTL_SECONDS
    _RUNTIME_EVENTS_CACHE["cache_key"] = cache_key
    _RUNTIME_EVENTS_CACHE["rows"] = out
    return out


def record_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    normalized_endpoint = normalize_endpoint(payload.endpoint, payload.method)
    raw_endpoint = normalize_path(payload.raw_endpoint or payload.endpoint)
    idea_id = resolve_idea_id(
        endpoint=payload.endpoint, explicit_idea_id=payload.idea_id, method=payload.method
    )
    origin_idea_id = resolve_origin_idea_id(idea_id)
    runtime_cost = runtime_paths.estimate_runtime_cost(float(payload.runtime_ms))
    metadata = dict(payload.metadata)
    if raw_endpoint != normalized_endpoint:
        metadata.setdefault("normalized_from", raw_endpoint)
    event = RuntimeEvent(
        id=f"rt_{uuid4().hex[:12]}",
        source=payload.source,
        endpoint=normalized_endpoint,
        raw_endpoint=raw_endpoint,
        method=payload.method.upper(),
        status_code=payload.status_code,
        runtime_ms=round(float(payload.runtime_ms), 4),
        idea_id=idea_id,
        origin_idea_id=origin_idea_id,
        metadata=metadata,
        runtime_cost_estimate=runtime_cost,
    )
    if runtime_event_store.enabled():
        runtime_event_store.write_event(event)
    else:
        data = runtime_store.read_store()
        data["events"].append(event.model_dump(mode="json"))
        runtime_store.write_store(data)
    _invalidate_runtime_events_cache()
    return event


def cached_runtime_events(
    *,
    limit: int = 100,
    source: str | None = None,
    force_refresh: bool = False,
) -> list[RuntimeEvent]:
    requested_limit = max(1, min(int(limit), 5000))
    source_value = str(source or "").strip().lower() or None
    params = {
        "limit": requested_limit,
        "source": source_value or "",
    }
    payload = runtime_cache.runtime_endpoint_cached_value(
        "runtime_events_list",
        fresh_ttl_seconds=45.0,
        refresh_producer=lambda: [
            row.model_dump(mode="json")
            for row in list_events(limit=requested_limit, source=source_value)
        ],
        params=params,
        force_refresh=force_refresh,
    )
    rows = runtime_store.coerce_runtime_event_rows(payload, limit=requested_limit)
    if rows:
        return rows
    return list_events(limit=requested_limit, source=source_value)


def live_change_token(force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    if (
        not force_refresh
        and isinstance(_LIVE_CHANGE_CACHE.get("payload"), dict)
        and float(_LIVE_CHANGE_CACHE.get("expires_at") or 0.0) > now
    ):
        return dict(_LIVE_CHANGE_CACHE["payload"])

    try:
        if runtime_event_store.enabled():
            runtime_checkpoint = runtime_event_store.checkpoint(
                exclude_endpoints=["/api/runtime/change-token"],
            )
        else:
            runtime_checkpoint = {
                "enabled": False,
                "count": None,
                "max_recorded_at": None,
                "file": runtime_paths.path_signature(runtime_paths.events_path()),
            }
    except Exception as exc:
        runtime_checkpoint = {"error": str(exc), "enabled": runtime_event_store.enabled()}

    try:
        if agent_task_store_service.enabled():
            task_checkpoint = agent_task_store_service.checkpoint()
        else:
            task_checkpoint = {
                "enabled": False,
                "count": None,
                "max_updated_at": None,
                "file": runtime_paths.path_signature(runtime_paths.agent_tasks_path()),
            }
    except Exception as exc:
        task_checkpoint = {"error": str(exc), "enabled": agent_task_store_service.enabled()}

    try:
        telemetry_checkpoint = telemetry_persistence_service.checkpoint()
    except Exception as exc:
        telemetry_checkpoint = {"error": str(exc)}

    file_checkpoints = {
        "monitor_issues": runtime_paths.path_signature(runtime_paths.monitor_issues_path()),
        "status_report": runtime_paths.path_signature(runtime_paths.status_report_path()),
    }

    components: dict[str, Any] = {
        "runtime": runtime_checkpoint,
        "tasks": task_checkpoint,
        "telemetry": telemetry_checkpoint,
        "files": file_checkpoints,
    }
    token_basis = json.dumps(components, sort_keys=True, default=str)
    token = hashlib.sha256(token_basis.encode("utf-8")).hexdigest()[:24]
    payload = {
        "token": token,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
    _LIVE_CHANGE_CACHE["expires_at"] = now + _LIVE_CHANGE_CACHE_TTL_SECONDS
    _LIVE_CHANGE_CACHE["payload"] = payload
    return dict(payload)
