"""Runtime telemetry persistence and aggregation service."""

from __future__ import annotations

import json
import os
import re
import time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.routing import APIRoute

from app.models.runtime import EndpointRuntimeSummary, IdeaRuntimeSummary, RuntimeEvent, RuntimeEventCreate
from app.services import idea_lineage_service, route_registry_service, runtime_event_store, value_lineage_service


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
    return event


def list_events(limit: int = 100) -> list[RuntimeEvent]:
    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(limit=max(1, min(limit, 5000)))
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
        return out[: max(1, min(limit, 2000))]

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
    return out[: max(1, min(limit, 2000))]


def summarize_by_idea(seconds: int = 3600) -> list[IdeaRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = [e for e in list_events(limit=2000) if e.recorded_at >= cutoff]

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
    rows = [e for e in list_events(limit=2000) if e.recorded_at >= cutoff]

    grouped: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        grouped.setdefault(event.endpoint, []).append(event)

    summaries: list[EndpointRuntimeSummary] = []
    for endpoint, events in grouped.items():
        methods = sorted({e.method.upper() for e in events})
        by_source: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        idea_counts: dict[str, int] = {}
        for event in events:
            by_source[event.source] = by_source.get(event.source, 0) + 1
            status_key = str(event.status_code)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            idea_key = str(event.idea_id or "unmapped")
            idea_counts[idea_key] = idea_counts.get(idea_key, 0) + 1
        primary_idea_id = max(idea_counts.items(), key=lambda item: item[1])[0]
        total_runtime = round(sum(e.runtime_ms for e in events), 4)
        total_cost = round(sum(e.runtime_cost_estimate for e in events), 8)
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
                by_source=by_source,
                status_counts=status_counts,
            )
        )
    summaries.sort(key=lambda x: (x.runtime_cost_estimate, x.endpoint), reverse=True)
    return summaries


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
    from app.services import inventory_service

    total_cycles = max(1, min(int(cycles), 200))
    endpoint_limit = max(1, min(int(max_endpoints), 2000))
    per_call_delay = max(0, min(int(delay_ms), 30000))
    timeout = max(1.0, min(float(timeout_seconds), 60.0))

    before = inventory_service.build_endpoint_traceability_inventory(runtime_window_seconds=runtime_window_seconds)
    before_with_usage = int((before.get("summary") or {}).get("with_usage_events") or 0)
    before_total = int((before.get("summary") or {}).get("total_endpoints") or 0)

    paths = _discover_get_api_paths(app)[:endpoint_limit]
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

    after = inventory_service.build_endpoint_traceability_inventory(runtime_window_seconds=runtime_window_seconds)
    after_with_usage = int((after.get("summary") or {}).get("with_usage_events") or 0)
    after_total = int((after.get("summary") or {}).get("total_endpoints") or 0)

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
