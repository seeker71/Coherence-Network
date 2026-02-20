"""Runtime endpoint exerciser implementation."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi.routing import APIRoute

from app.services import value_lineage_service


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
        return _sample_path_value(match.group(1))

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
    return sorted(set(paths))


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


async def run_get_endpoint_exerciser(
    *,
    app,
    base_url: str,
    cycles: int = 1,
    max_endpoints: int = 250,
    delay_ms: int = 0,
    timeout_seconds: float = 8.0,
    runtime_window_seconds: int = 86400,
) -> dict[str, Any]:
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
