"""Helpers for web-view completion aggregation and render/API cost summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.runtime import RuntimeEvent, WebViewPerformanceReport, WebViewPerformanceRow


def _metadata_string(event: RuntimeEvent, key: str) -> str:
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    value = metadata.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _metadata_float(event: RuntimeEvent, key: str, default: float = 0.0) -> float:
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    value = metadata.get(key)
    try:
        return float(default) if value is None else float(value)
    except (TypeError, ValueError):
        return float(default)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = max(0.0, min(float(percentile), 1.0)) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)
    return round(interpolated, 4)


def _api_events_by_view(rows: list[RuntimeEvent]) -> dict[str, list[RuntimeEvent]]:
    out: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        if event.source != "api":
            continue
        view_id = _metadata_string(event, "page_view_id")
        if not view_id:
            continue
        out.setdefault(view_id, []).append(event)
    return out


def _group_web_rows(
    rows: list[RuntimeEvent],
    *,
    route_prefix: str | None,
    api_events_by_view: dict[str, list[RuntimeEvent]],
) -> dict[str, list[dict[str, float | datetime]]]:
    grouped: dict[str, list[dict[str, float | datetime]]] = {}
    prefix = (route_prefix or "").strip()
    for event in rows:
        if event.source != "web" or _metadata_string(event, "tracking_kind") != "web_view_complete":
            continue
        route = str(event.endpoint or "").strip()
        if not route or (prefix and not route.startswith(prefix)):
            continue
        view_id = _metadata_string(event, "page_view_id")
        linked = api_events_by_view.get(view_id, []) if view_id else []
        api_call_count = _metadata_float(event, "api_call_count", default=float(len(linked)))
        if linked:
            default_endpoint_count = float(len({api_event.endpoint for api_event in linked}))
            default_runtime = float(sum(float(api_event.runtime_ms) for api_event in linked))
            default_cost = float(sum(float(api_event.runtime_cost_estimate) for api_event in linked))
        else:
            default_endpoint_count = 0.0
            default_runtime = 0.0
            default_cost = 0.0
        grouped.setdefault(route, []).append(
            {
                "render_ms": float(event.runtime_ms),
                "api_call_count": max(0.0, api_call_count),
                "api_endpoint_count": max(0.0, _metadata_float(event, "api_endpoint_count", default=default_endpoint_count)),
                "api_runtime_ms": max(0.0, _metadata_float(event, "api_runtime_ms", default=default_runtime)),
                "api_runtime_cost_estimate": max(
                    0.0,
                    _metadata_float(
                        event,
                        "api_runtime_cost_estimate",
                        default=_metadata_float(event, "api_runtime_cost_usd", default=default_cost),
                    ),
                ),
                "recorded_at": event.recorded_at,
            }
        )
    return grouped


def summarize_web_view_performance_from_rows(
    *,
    rows: list[RuntimeEvent],
    window_seconds: int,
    requested_limit: int,
    route_prefix: str | None = None,
) -> WebViewPerformanceReport:
    grouped = _group_web_rows(rows, route_prefix=route_prefix, api_events_by_view=_api_events_by_view(rows))
    report_rows: list[WebViewPerformanceRow] = []
    for route, route_rows in grouped.items():
        if not route_rows:
            continue
        render_values = [float(row["render_ms"]) for row in route_rows]
        api_call_values = [float(row["api_call_count"]) for row in route_rows]
        api_endpoint_values = [float(row["api_endpoint_count"]) for row in route_rows]
        api_runtime_values = [float(row["api_runtime_ms"]) for row in route_rows]
        api_cost_values = [float(row["api_runtime_cost_estimate"]) for row in route_rows]
        latest_row = max(route_rows, key=lambda row: row["recorded_at"])
        report_rows.append(
            WebViewPerformanceRow(
                route=route,
                views=len(route_rows),
                p50_render_ms=_percentile(render_values, 0.5),
                p95_render_ms=_percentile(render_values, 0.95),
                average_render_ms=round(sum(render_values) / len(render_values), 4),
                average_api_call_count=round(sum(api_call_values) / len(api_call_values), 4),
                average_api_endpoint_count=round(sum(api_endpoint_values) / len(api_endpoint_values), 4),
                average_api_runtime_ms=round(sum(api_runtime_values) / len(api_runtime_values), 4),
                average_api_runtime_cost_estimate=round(sum(api_cost_values) / len(api_cost_values), 8),
                last_render_ms=round(float(latest_row["render_ms"]), 4),
                last_api_runtime_ms=round(float(latest_row["api_runtime_ms"]), 4),
                last_api_runtime_cost_estimate=round(float(latest_row["api_runtime_cost_estimate"]), 8),
                last_view_at=latest_row["recorded_at"],
            )
        )
    report_rows.sort(
        key=lambda row: (row.average_api_runtime_cost_estimate, row.p95_render_ms, row.route),
        reverse=True,
    )
    return WebViewPerformanceReport(
        window_seconds=window_seconds,
        route_prefix=route_prefix or None,
        total_routes=len(report_rows),
        rows=report_rows[: max(1, min(int(requested_limit), 500))],
    )
