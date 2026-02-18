"""Runtime telemetry persistence and aggregation service."""

from __future__ import annotations

import json
import os
import re
import time
import asyncio
from typing import Any
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.routing import APIRoute

from app.models.runtime import (
    EndpointAttentionReport,
    EndpointAttentionRow,
    EndpointRuntimeSummary,
    IdeaRuntimeSummary,
    RuntimeEvent,
    RuntimeEventCreate,
)
from app.services import idea_lineage_service, route_registry_service, runtime_event_store, value_lineage_service


_RUNTIME_EVENTS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "cache_key": "",
    "rows": [],
}
_RUNTIME_EVENTS_CACHE_TTL_SECONDS = 30.0


def _default_events_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "runtime_events.json"


def _events_path() -> Path:
    configured = os.getenv("RUNTIME_EVENTS_PATH")
    return Path(configured) if configured else _default_events_path()


def _default_idea_map_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "runtime_idea_map.json"


def _idea_map_path() -> Path:
    configured = os.getenv("RUNTIME_IDEA_MAP_PATH")
    return Path(configured) if configured else _default_idea_map_path()


def _runtime_cost_per_second() -> float:
    return float(os.getenv("RUNTIME_COST_PER_SECOND", "0.002"))


def _runtime_events_store_cache_key() -> str:
    if runtime_event_store.enabled():
        url = (
            os.getenv("RUNTIME_DATABASE_URL", "").strip()
            or os.getenv("DATABASE_URL", "").strip()
            or "<runtime-database>"
        )
        return f"db:{url}"
    return f"file:{_events_path()}"


def _runtime_events_cache_key(limit: int, since: datetime | None) -> str:
    cutoff = "all"
    if since is not None:
        since_ts = int(since.timestamp())
        cutoff = str(since_ts // max(1, int(_RUNTIME_EVENTS_CACHE_TTL_SECONDS)))
    return f"store={_runtime_events_store_cache_key()}|limit={limit}|cutoff={cutoff}"


def _invalidate_runtime_events_cache() -> None:
    _RUNTIME_EVENTS_CACHE["expires_at"] = 0.0
    _RUNTIME_EVENTS_CACHE["cache_key"] = ""
    _RUNTIME_EVENTS_CACHE["rows"] = []


def _ensure_events_store() -> None:
    if runtime_event_store.enabled():
        runtime_event_store.ensure_schema()
        return
    path = _events_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"events": []}, indent=2), encoding="utf-8")


def _read_store() -> dict:
    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(limit=5000)
        return {"events": [row.model_dump(mode="json") for row in rows]}
    _ensure_events_store()
    path = _events_path()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"events": []}
    if not isinstance(data, dict):
        return {"events": []}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    return {"events": events}


def _write_store(data: dict) -> None:
    if runtime_event_store.enabled():
        # Writes happen via record_event() for DB-backed storage.
        return
    path = _events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _default_idea_map() -> dict:
    return {
        "prefix_map": {
            "/api/health": "oss-interface-alignment",
            "/api/ideas": "portfolio-governance",
            "/api/inventory": "portfolio-governance",
            "/api/agent": "portfolio-governance",
            "/api/value-lineage": "portfolio-governance",
            "/api/gates": "oss-interface-alignment",
            "/api/runtime": "oss-interface-alignment",
            "/api/health-proxy": "oss-interface-alignment",
            "/v1": "portfolio-governance",
            "/api": "oss-interface-alignment",
            "/gates": "oss-interface-alignment",
            "/search": "coherence-signal-depth",
            "/": "oss-interface-alignment",
        }
    }


def _load_idea_map() -> dict:
    path = _idea_map_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_default_idea_map(), indent=2), encoding="utf-8")
        return _default_idea_map()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_idea_map()
    if not isinstance(data, dict):
        return _default_idea_map()
    return data


def _normalize_path(endpoint: str) -> str:
    cleaned = str(endpoint or "").strip()
    if not cleaned:
        return "/"
    path = cleaned.split("?", 1)[0].strip()
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def _canonical_api_routes() -> list[dict]:
    routes = route_registry_service.get_canonical_routes().get("api_routes", [])
    if not isinstance(routes, list):
        return []
    return [row for row in routes if isinstance(row, dict) and isinstance(row.get("path"), str)]


def _template_regex(template: str) -> str:
    escaped = re.escape(template)
    return "^" + re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped) + "$"


def _method_allowed(route: dict, method: str | None) -> bool:
    if not method:
        return True
    methods = route.get("methods")
    if not isinstance(methods, list) or not methods:
        return True
    normalized = method.strip().upper()
    return normalized in {
        m.strip().upper() for m in methods if isinstance(m, str) and m.strip()
    }


def _match_canonical_route(endpoint: str, method: str | None = None) -> dict | None:
    path = _normalize_path(endpoint)
    routes = _canonical_api_routes()

    for row in routes:
        template = str(row.get("path") or "").strip()
        if template == path and _method_allowed(row, method):
            return row

    for row in routes:
        template = str(row.get("path") or "").strip()
        if "{" not in template or "}" not in template:
            continue
        if not _method_allowed(row, method):
            continue
        if re.match(_template_regex(template), path):
            return row

    return None


def normalize_endpoint(endpoint: str, method: str | None = None) -> str:
    path = _normalize_path(endpoint)
    canonical = _match_canonical_route(path, method=method)
    if isinstance(canonical, dict):
        canonical_path = str(canonical.get("path") or "").strip()
        if canonical_path:
            return canonical_path
    return path


def resolve_origin_idea_id(idea_id: str | None) -> str:
    return idea_lineage_service.resolve_origin_idea_id(idea_id)


def resolve_idea_id(
    endpoint: str,
    explicit_idea_id: str | None = None,
    method: str | None = None,
) -> str:
    if explicit_idea_id:
        return explicit_idea_id

    canonical = _match_canonical_route(endpoint, method=method)
    if isinstance(canonical, dict):
        canonical_idea_id = str(canonical.get("idea_id") or "").strip()
        if canonical_idea_id:
            return canonical_idea_id

    normalized_endpoint = normalize_endpoint(endpoint, method=method)
    map_data = _load_idea_map()
    prefix_map = map_data.get("prefix_map") if isinstance(map_data.get("prefix_map"), dict) else {}
    for prefix, idea_id in prefix_map.items():
        if isinstance(prefix, str) and isinstance(idea_id, str) and normalized_endpoint.startswith(prefix):
            return idea_id

    # Derive idea from lineage endpoint references where possible.
    marker = "/api/value-lineage/links/"
    if marker in endpoint:
        tail = endpoint.split(marker, 1)[1]
        lineage_id = tail.split("/", 1)[0]
        link = value_lineage_service.get_link(lineage_id)
        if link:
            return link.idea_id

    if normalized_endpoint.startswith("/api"):
        return "oss-interface-alignment"
    if normalized_endpoint.startswith("/v1"):
        return "portfolio-governance"
    if normalized_endpoint.startswith("/"):
        return "oss-interface-alignment"

    return "unmapped"


def record_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    normalized_endpoint = normalize_endpoint(payload.endpoint, payload.method)
    raw_endpoint = _normalize_path(payload.raw_endpoint or payload.endpoint)
    idea_id = resolve_idea_id(endpoint=payload.endpoint, explicit_idea_id=payload.idea_id, method=payload.method)
    origin_idea_id = resolve_origin_idea_id(idea_id)
    runtime_cost = round((float(payload.runtime_ms) / 1000.0) * _runtime_cost_per_second(), 8)
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
        data = _read_store()
        data["events"].append(event.model_dump(mode="json"))
        _write_store(data)
    _invalidate_runtime_events_cache()
    return event


def list_events(limit: int = 100, since: datetime | None = None) -> list[RuntimeEvent]:
    requested_limit = max(1, min(int(limit), 2000))
    if since is None:
        cutoff = "all"
    else:
        since_ts = int(since.timestamp())
        cutoff = str(since_ts // max(1, int(_RUNTIME_EVENTS_CACHE_TTL_SECONDS)))
    cache_key = _runtime_events_cache_key(requested_limit, since)
    now = time.time()
    if (
        _RUNTIME_EVENTS_CACHE.get("expires_at", 0.0) > now
        and _RUNTIME_EVENTS_CACHE.get("cache_key") == cache_key
        and isinstance(_RUNTIME_EVENTS_CACHE.get("rows"), list)
    ):
        return [row.model_copy(deep=True) for row in _RUNTIME_EVENTS_CACHE["rows"][:requested_limit]]

    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(limit=max(1, min(requested_limit, 5000)), since=since)
        out: list[RuntimeEvent] = []
        for event in rows:
            try:
                if not event.raw_endpoint:
                    event.raw_endpoint = event.endpoint
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

    data = _read_store()
    out: list[RuntimeEvent] = []
    for raw in data["events"]:
        try:
            event = RuntimeEvent(**raw)
            if not event.raw_endpoint:
                event.raw_endpoint = event.endpoint
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


def summarize_by_idea(
    seconds: int = 3600,
    event_limit: int = 2000,
    event_rows: list[RuntimeEvent] | None = None,
) -> list[IdeaRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    if event_rows is None:
        rows = list_events(limit=max(1, min(int(event_limit), 5000)), since=cutoff)
    else:
        rows = [row for row in event_rows if row.recorded_at >= cutoff]

    grouped: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        grouped.setdefault(event.idea_id or "unmapped", []).append(event)

    summaries: list[IdeaRuntimeSummary] = []
    for idea_id, events in grouped.items():
        total_runtime = round(sum(e.runtime_ms for e in events), 4)
        total_cost = round(sum(e.runtime_cost_estimate for e in events), 8)
        by_source: dict[str, int] = {}
        for event in events:
            by_source[event.source] = by_source.get(event.source, 0) + 1
        summaries.append(
            IdeaRuntimeSummary(
                idea_id=idea_id,
                event_count=len(events),
                total_runtime_ms=total_runtime,
                average_runtime_ms=round(total_runtime / len(events), 4),
                runtime_cost_estimate=total_cost,
                by_source=by_source,
            )
        )
    summaries.sort(key=lambda x: x.runtime_cost_estimate, reverse=True)
    return summaries


def summarize_by_endpoint(seconds: int = 3600) -> list[EndpointRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = list_events(limit=2000, since=cutoff)

    grouped: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        grouped.setdefault(event.endpoint, []).append(event)

    summaries: list[EndpointRuntimeSummary] = []
    for endpoint, events in grouped.items():
        methods = sorted({e.method.upper() for e in events})
        by_source: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        idea_counts: dict[str, int] = {}
        paid_tool_event_count = 0
        paid_tool_failure_count = 0
        paid_tool_runtime_ms = 0.0
        paid_tool_runtime_cost = 0.0

        for event in events:
            by_source[event.source] = by_source.get(event.source, 0) + 1
            status_key = str(event.status_code)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            idea_key = str(event.idea_id or "unmapped")
            idea_counts[idea_key] = idea_counts.get(idea_key, 0) + 1

            metadata = event.metadata if isinstance(event.metadata, dict) else {}
            if bool(metadata.get("is_paid_provider")):
                paid_tool_event_count += 1
                paid_tool_runtime_ms += float(event.runtime_ms or 0.0)
                raw_runtime_cost = metadata.get("runtime_cost_usd")
                if raw_runtime_cost is not None:
                    try:
                        paid_tool_runtime_cost += float(raw_runtime_cost)
                    except (TypeError, ValueError):
                        paid_tool_runtime_cost += float(event.runtime_cost_estimate)
                else:
                    paid_tool_runtime_cost += float(event.runtime_cost_estimate)
                if event.status_code >= 400:
                    paid_tool_failure_count += 1

        primary_idea_id = max(idea_counts.items(), key=lambda item: item[1])[0]
        total_runtime = round(sum(e.runtime_ms for e in events), 4)
        total_cost = round(sum(e.runtime_cost_estimate for e in events), 8)
        paid_tool_ratio = float(paid_tool_event_count) / float(len(events)) if events else 0.0
        paid_tool_average_runtime_ms = (
            round((paid_tool_runtime_ms / paid_tool_event_count), 4) if paid_tool_event_count else 0.0
        )
        summaries.append(
            EndpointRuntimeSummary(
                endpoint=endpoint,
                methods=methods,
                idea_id=primary_idea_id,
                origin_idea_id=resolve_origin_idea_id(primary_idea_id),
                event_count=len(events),
                total_runtime_ms=total_runtime,
                average_runtime_ms=round(total_runtime / len(events), 4),
                runtime_cost_estimate=total_cost,
                paid_tool_event_count=paid_tool_event_count,
                paid_tool_failure_count=paid_tool_failure_count,
                paid_tool_ratio=round(paid_tool_ratio, 4),
                paid_tool_runtime_cost=round(paid_tool_runtime_cost, 8),
                paid_tool_average_runtime_ms=paid_tool_average_runtime_ms,
                by_source=by_source,
                status_counts=status_counts,
            )
        )
    summaries.sort(key=lambda x: (x.runtime_cost_estimate, x.endpoint), reverse=True)
    return summaries


def _parse_status_code(value: str) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load_idea_value_rows() -> dict[str, dict[str, float]]:
    try:
        from app.services import idea_service
    except Exception:
        return {}

    rows: dict[str, dict[str, float]] = {}
    try:
        ideas = idea_service.list_ideas()
    except Exception:
        return rows

    for idea in ideas.ideas:
        rows[str(idea.id)] = {
            "potential_value": float(idea.potential_value or 0.0),
            "actual_value": float(idea.actual_value or 0.0),
            "estimated_cost": float(idea.estimated_cost or 0.0),
            "actual_cost": float(idea.actual_cost or 0.0),
            "confidence": float(idea.confidence or 0.0),
        }
    return rows


def _endpoint_friction_counts(seconds: int) -> dict[str, int]:
    from app.services import friction_service

    try:
        events, _ignored = friction_service.load_events()
    except Exception:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, min(seconds, 60 * 60 * 24 * 30)))
    counts: dict[str, int] = {}
    for event in events:
        if event.timestamp < cutoff:
            continue
        endpoint = str(getattr(event, "endpoint", "") or "").strip()
        if not endpoint:
            continue
        counts[endpoint] = counts.get(endpoint, 0) + 1
    return counts


def _attention_reasons(
    *,
    success_rate: float,
    paid_ratio: float,
    friction_density: float,
    value_gap: float,
    cost_per_event: float,
    event_count: int,
) -> list[str]:
    reasons: list[str] = []
    if event_count < 5:
        reasons.append("low_sample")
    if success_rate < 0.90:
        reasons.append(f"low_success_rate:{round(success_rate * 100.0, 2)}%")
    if paid_ratio > 0.0:
        reasons.append(f"paid_requests:{round(paid_ratio * 100.0, 2)}%")
    if friction_density > 0.0:
        reasons.append(f"friction_density:{round(friction_density * 100.0, 2)}%")
    if value_gap > 1.0:
        reasons.append(f"value_gap:{round(value_gap, 4)}")
    if cost_per_event > 0.002:
        reasons.append(f"cost_per_event:{round(cost_per_event, 6)}")
    return reasons


def _endpoint_attention_score(
    *,
    event_count: int,
    success_rate: float,
    paid_ratio: float,
    friction_density: float,
    value_gap: float,
    cost_per_event: float,
    attention_threshold: float,
) -> tuple[float, bool]:
    """Compute attention score and whether attention_threshold is exceeded."""
    failure_score = (1.0 - success_rate) * 100.0
    paid_score = min(paid_ratio * 60.0, 30.0)
    cost_score = min(cost_per_event * 1000.0, 25.0)
    friction_score = min(friction_density * 300.0, 20.0)
    value_gap_score = min(value_gap / 5.0, 25.0)
    sample_score = min(event_count / 20.0, 1.0) * 10.0

    attention_score = (
        failure_score * min(event_count / 5.0, 1.0)
        + paid_score
        + cost_score
        + friction_score
        + value_gap_score
        + sample_score
    )
    return attention_score, attention_score >= attention_threshold


def _endpoint_attention_status_counts(
    row: EndpointRuntimeSummary,
) -> tuple[int, int]:
    success_count = 0
    failure_count = 0
    for code_str, count in row.status_counts.items():
        code = _parse_status_code(code_str)
        if 200 <= code < 400:
            success_count += _safe_int(count, 0)
        else:
            failure_count += _safe_int(count, 0)
    return success_count, failure_count


def _endpoint_attention_paid_counts(
    endpoint_events: list[RuntimeEvent],
) -> tuple[int, int]:
    paid_tool_event_count = 0
    paid_tool_failure_count = 0
    for event in endpoint_events:
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        if bool(metadata.get("is_paid_provider")):
            paid_tool_event_count += 1
            if event.status_code >= 400:
                paid_tool_failure_count += 1
    return paid_tool_event_count, paid_tool_failure_count


def _build_endpoint_attention_row(
    row: EndpointRuntimeSummary,
    *,
    min_event_count: int,
    attention_threshold: float,
    endpoint_events: list[RuntimeEvent],
    friction_count: int,
    idea_rows: dict[str, dict[str, float]],
) -> EndpointAttentionRow | None:
    event_count = int(row.event_count)
    if event_count < max(1, int(min_event_count)):
        return None

    success_count, failure_count = _endpoint_attention_status_counts(row)

    success_rate = float(success_count) / float(event_count) if event_count else 0.0

    paid_tool_event_count, paid_tool_failure_count = _endpoint_attention_paid_counts(endpoint_events)

    paid_ratio = float(paid_tool_event_count) / float(event_count) if event_count else 0.0
    friction_density = (float(friction_count) / float(event_count)) if event_count else 0.0

    idea_data = idea_rows.get(row.idea_id) or idea_rows.get(row.origin_idea_id, {})
    potential_value = _safe_float(idea_data.get("potential_value", 0.0))
    actual_value = _safe_float(idea_data.get("actual_value", 0.0))
    estimated_cost = _safe_float(idea_data.get("estimated_cost", 0.0))
    actual_cost = _safe_float(idea_data.get("actual_cost", 0.0))
    idea_confidence = _safe_float(idea_data.get("confidence", 0.0), default=0.0)

    value_gap = max(potential_value - actual_value, 0.0)
    cost_per_event = float(row.runtime_cost_estimate) / float(max(event_count, 1))

    confidence = min(event_count / 20.0, 1.0) * 0.75 + 0.25 * idea_confidence
    attention_score, needs_attention = _endpoint_attention_score(
        event_count=event_count,
        success_rate=success_rate,
        paid_ratio=paid_ratio,
        friction_density=friction_density,
        value_gap=value_gap,
        cost_per_event=cost_per_event,
        attention_threshold=attention_threshold,
    )

    return EndpointAttentionRow(
        endpoint=row.endpoint,
        methods=row.methods,
        idea_id=row.idea_id,
        origin_idea_id=row.origin_idea_id,
        event_count=event_count,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=round(success_rate, 4),
        runtime_cost_estimate=round(float(row.runtime_cost_estimate), 8),
        cost_per_event=round(cost_per_event, 8),
        paid_tool_event_count=paid_tool_event_count,
        paid_tool_failure_count=paid_tool_failure_count,
        paid_tool_ratio=round(paid_ratio, 4),
        friction_event_count=friction_count,
        friction_event_density=round(friction_density, 4),
        potential_value=round(potential_value, 4),
        actual_value=round(actual_value, 4),
        estimated_cost=round(estimated_cost, 4),
        actual_cost=round(actual_cost, 4),
        value_gap=round(value_gap, 4),
        attention_score=round(attention_score, 3),
        confidence=round(max(0.0, min(confidence, 1.0)), 4),
        needs_attention=needs_attention,
        reasons=_attention_reasons(
            success_rate=success_rate,
            paid_ratio=paid_ratio,
            friction_density=friction_density,
            value_gap=value_gap,
            cost_per_event=cost_per_event,
            event_count=event_count,
        ),
    )


def summarize_endpoint_attention(
    *,
    seconds: int = 3600,
    min_event_count: int = 1,
    attention_threshold: float = 40.0,
    limit: int | None = None,
) -> EndpointAttentionReport:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    endpoint_rows = summarize_by_endpoint(seconds=window_seconds)
    friction_by_endpoint = _endpoint_friction_counts(window_seconds)
    idea_rows = _load_idea_value_rows()

    window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    attention_events = list_events(limit=2000, since=window_start)
    by_endpoint: dict[str, list[RuntimeEvent]] = {}
    for event in attention_events:
        by_endpoint.setdefault(event.endpoint, []).append(event)

    rows: list[EndpointAttentionRow] = []
    for row in endpoint_rows:
        built = _build_endpoint_attention_row(
            row,
            min_event_count=min_event_count,
            attention_threshold=attention_threshold,
            endpoint_events=by_endpoint.get(row.endpoint, []),
            friction_count=int(friction_by_endpoint.get(row.endpoint, 0)),
            idea_rows=idea_rows,
        )
        if built is None:
            continue
        rows.append(built)

    rows.sort(key=lambda row: row.attention_score, reverse=True)
    if limit is not None:
        rows = rows[: max(1, min(int(limit), len(rows), 2000))]

    attention_count = sum(1 for row in rows if row.needs_attention)
    return EndpointAttentionReport(
        window_seconds=window_seconds,
        attention_threshold=round(float(attention_threshold), 3),
        min_event_count=max(1, int(min_event_count)),
        total_endpoints=len(rows),
        attention_count=attention_count,
        endpoints=rows,
    )


def verify_internal_vs_public_usage(
    *,
    public_api_base: str,
    runtime_window_seconds: int = 86400,
    timeout_seconds: float = 8.0,
) -> dict[str, object]:
    window_seconds = max(60, min(runtime_window_seconds, 60 * 60 * 24 * 30))
    internal = summarize_by_endpoint(seconds=window_seconds)
    internal_by_endpoint = {row.endpoint: row for row in internal}

    public_url = f"{public_api_base.rstrip('/')}/api/runtime/endpoints/summary"
    public_rows: list[dict] = []
    error = ""
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(public_url, params={"seconds": window_seconds})
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("endpoints"), list):
            public_rows = [row for row in payload["endpoints"] if isinstance(row, dict)]
        else:
            error = "public_payload_invalid"
    except Exception as exc:
        error = str(exc)

    public_by_endpoint: dict[str, dict] = {}
    for row in public_rows:
        endpoint = str(row.get("endpoint") or "").strip()
        if endpoint:
            public_by_endpoint[endpoint] = row

    internal_only = sorted(set(internal_by_endpoint.keys()) - set(public_by_endpoint.keys()))
    public_only = sorted(set(public_by_endpoint.keys()) - set(internal_by_endpoint.keys()))
    overlap = sorted(set(internal_by_endpoint.keys()) & set(public_by_endpoint.keys()))

    missing_public_records = [
        endpoint for endpoint in overlap if int(public_by_endpoint[endpoint].get("event_count") or 0) <= 0
    ]
    pass_contract = not error and len(missing_public_records) == 0

    return {
        "runtime_window_seconds": window_seconds,
        "public_api_base": public_api_base.rstrip("/"),
        "pass_contract": pass_contract,
        "error": error,
        "internal_endpoint_count": len(internal_by_endpoint),
        "public_endpoint_count": len(public_by_endpoint),
        "overlap_count": len(overlap),
        "internal_only_endpoints": internal_only,
        "public_only_endpoints": public_only,
        "missing_public_records": missing_public_records,
    }


_EXERCISER_QUERY_DEFAULTS: dict[str, dict[str, str]] = {
    "/api/agent/route": {"task_type": "impl"},
    "/api/agent/tasks": {"limit": "20", "offset": "0"},
    "/api/agent/tasks/attention": {"limit": "20"},
    "/api/agent/tasks/count": {},
    "/api/runtime/events": {"limit": "100"},
    "/api/runtime/ideas/summary": {"seconds": "3600"},
    "/api/runtime/endpoints/summary": {"seconds": "3600"},
    "/api/runtime/endpoints/attention": {
        "seconds": "3600",
        "min_event_count": "1",
        "attention_threshold": "0.0",
    },
    "/api/inventory/process-completeness": {"runtime_window_seconds": "86400"},
    "/api/inventory/questions/proactive": {"limit": "20", "top": "20"},
    "/api/inventory/endpoint-traceability": {"runtime_window_seconds": "86400"},
    "/api/inventory/system-lineage": {"runtime_window_seconds": "3600"},
    "/api/automation/usage/snapshots": {"limit": "200"},
    "/api/automation/usage/provider-validation": {
        "runtime_window_seconds": "86400",
        "min_execution_events": "1",
    },
}


def _sample_path_value(param_name: str) -> str:
    key = (param_name or "").strip().lower()
    if key == "task_id":
        try:
            from app.services import agent_service

            rows, total = agent_service.list_tasks(limit=1)
            if total > 0 and rows:
                value = str(rows[0].get("id") or "").strip()
                if value:
                    return value
        except Exception:
            pass
        return "task_missing"
    if key == "lineage_id":
        try:
            rows = value_lineage_service.list_links(limit=1)
            if rows:
                return rows[0].id
        except Exception:
            pass
        return "lineage_missing"
    if key == "spec_id":
        try:
            from app.services import spec_registry_service

            rows = spec_registry_service.list_specs(limit=1)
            if rows:
                return rows[0].spec_id
        except Exception:
            pass
        return "spec_missing"
    if key == "idea_id":
        return "portfolio-governance"
    return f"{key}_sample"


def _materialize_route_path(path_template: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return _sample_path_value(name)

    return re.sub(r"\{([^{}]+)\}", _replace, path_template)


def _discover_get_api_paths(app) -> list[str]:
    paths: list[str] = []
    for route in getattr(app, "routes", []):
        if not isinstance(route, APIRoute):
            continue
        methods = {m.upper() for m in (route.methods or set())}
        if "GET" not in methods:
            continue
        path = str(getattr(route, "path", "") or "").strip()
        if not path.startswith("/api/"):
            continue
        if path.startswith("/api/runtime/exerciser"):
            continue
        paths.append(path)
    unique = sorted(set(paths))
    return unique


async def run_get_endpoint_exerciser(
    *,
    app,
    base_url: str,
    cycles: int = 1,
    max_endpoints: int = 250,
    delay_ms: int = 0,
    timeout_seconds: float = 8.0,
    runtime_window_seconds: int = 86400,
) -> dict:
    total_cycles = max(1, min(int(cycles), 200))
    endpoint_limit = max(1, min(int(max_endpoints), 2000))
    per_call_delay = max(0, min(int(delay_ms), 30000))
    timeout = max(1.0, min(float(timeout_seconds), 60.0))
    paths = _discover_get_api_paths(app)[:endpoint_limit]

    before_with_usage, before_total = _exerciser_inventory_snapshot(
        runtime_window_seconds=runtime_window_seconds
    )
    results, by_status = await _run_get_endpoint_exerciser_calls(
        app=app,
        base_url=base_url,
        paths=paths,
        total_cycles=total_cycles,
        per_call_delay=per_call_delay,
        timeout=timeout,
    )
    after_with_usage, after_total = _exerciser_inventory_snapshot(
        runtime_window_seconds=runtime_window_seconds
    )

    return {
        "result": "runtime_get_endpoint_exerciser_completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "cycles": total_cycles,
            "max_endpoints": endpoint_limit,
            "delay_ms": per_call_delay,
            "timeout_seconds": timeout,
            "runtime_window_seconds": runtime_window_seconds,
        },
        "coverage": {
            "before_with_usage_events": before_with_usage,
            "after_with_usage_events": after_with_usage,
            "delta_with_usage_events": after_with_usage - before_with_usage,
            "before_total_endpoints": before_total,
            "after_total_endpoints": after_total,
        },
        "summary": {
            "discovered_get_endpoints": len(paths),
            "total_calls": len(results),
            "status_counts": by_status,
            "successful_calls": sum(1 for row in results if int(row["status_code"]) < 400),
            "failed_calls": sum(1 for row in results if int(row["status_code"]) >= 400),
        },
        "calls": results[:500],
    }


def _exerciser_inventory_snapshot(runtime_window_seconds: int) -> tuple[int, int]:
    from app.services import inventory_service

    snapshot = inventory_service.build_endpoint_traceability_inventory(
        runtime_window_seconds=runtime_window_seconds
    )
    with_usage = int((snapshot.get("summary") or {}).get("with_usage_events") or 0)
    total = int((snapshot.get("summary") or {}).get("total_endpoints") or 0)
    return with_usage, total


async def _run_get_endpoint_exerciser_calls(
    *,
    app,
    base_url: str,
    paths: list[str],
    total_cycles: int,
    per_call_delay: int,
    timeout: float,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    results: list[dict[str, object]] = []
    by_status: dict[str, int] = {}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for cycle in range(1, total_cycles + 1):
            for path_template in paths:
                path = _materialize_route_path(path_template)
                params = dict(_EXERCISER_QUERY_DEFAULTS.get(path_template, {}))
                started = time.perf_counter()
                status_code = 599
                error = None
                try:
                    response = await client.get(path, params=params, headers={"x-endpoint-exerciser": "1"})
                    status_code = int(response.status_code)
                except Exception as exc:
                    error = str(exc)
                elapsed_ms = round(max(0.1, (time.perf_counter() - started) * 1000.0), 4)
                status_key = str(status_code)
                by_status[status_key] = by_status.get(status_key, 0) + 1
                row: dict[str, object] = {
                    "cycle": cycle,
                    "path_template": path_template,
                    "path_called": path,
                    "query_params": params,
                    "status_code": status_code,
                    "runtime_ms": elapsed_ms,
                }
                if error:
                    row["error"] = error
                results.append(row)
                if per_call_delay > 0:
                    await asyncio.sleep(per_call_delay / 1000.0)
    return results, by_status
