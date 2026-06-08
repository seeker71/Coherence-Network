#!/usr/bin/env python3
"""Rank web-used API routes for native high-grammar promotion.

The command accepts both ordinary and slash forms:

    python3 scripts/native_route_goal_loop.py /goal
    python3 scripts/native_route_goal_loop.py /loop --write-state

`/goal` reads the current route-frequency surface. `/loop` also writes the
state artifact that the next agent can continue from. Both commands use runtime
events as the evidence source and overlay the checked-in native manifests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_BASE = "https://api.coherencycoin.com"
DEFAULT_STATE_PATH = ROOT / "docs" / "system_audit" / "native_route_goal_state.json"
FRONT_DOOR_BML = ROOT / "deploy" / "front-door" / "api.bml"
PRODUCTION_ROUTES = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
TARGET_SHARE = 0.90
WEB_PROXY_UPSTREAM_ENDPOINTS = {
    ("GET", "/api/health-proxy"): "/api/health",
}


@dataclass(frozen=True)
class NativeRoute:
    endpoint: str
    method: str
    grammar: str
    source_file: str
    handler: str
    required_header: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _route_key(method: str, endpoint: str) -> str:
    return f"{method.upper()} {endpoint}"


def load_bml_routes() -> dict[str, NativeRoute]:
    text = _read_text(FRONT_DOOR_BML)
    routes: dict[str, NativeRoute] = {}
    pattern = re.compile(
        r'route\("[^"]+",\s*"([A-Z]+)",\s*"(/api/[^"]+)",\s*\d+,\s*"([^"]+)",\s*"([^"]*)"'
    )
    for method, endpoint, handler, required_header in pattern.findall(text):
        routes[_route_key(method, endpoint)] = NativeRoute(
            endpoint=endpoint,
            method=method,
            grammar="BML",
            source_file=str(FRONT_DOOR_BML.relative_to(ROOT)),
            handler=handler,
            required_header=required_header,
        )
    return routes


def load_form_routes() -> dict[str, NativeRoute]:
    text = _read_text(PRODUCTION_ROUTES)
    routes: dict[str, NativeRoute] = {}
    for endpoint, handler in re.findall(r'\(list\s+"(/api/[^"]+)"\s+([A-Za-z_]\w*)\)', text):
        routes[_route_key("GET", endpoint)] = NativeRoute(
            endpoint=endpoint,
            method="GET",
            grammar="Form",
            source_file=str(PRODUCTION_ROUTES.relative_to(ROOT)),
            handler=handler,
        )
    return routes


def load_native_routes() -> dict[str, NativeRoute]:
    routes = load_form_routes()
    routes.update(load_bml_routes())
    return routes


def _url(path: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{path}?{query}" if query else path


def fetch_endpoint_summary(
    *,
    api_base: str,
    seconds: int,
    limit: int,
    source: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    path = _url(
        f"{api_base.rstrip('/')}/api/runtime/endpoints/summary",
        {"seconds": seconds, "limit": limit, "source": source},
    )
    request = urllib.request.Request(
        path,
        headers={
            "Accept": "application/json",
            "User-Agent": "coherence-native-route-goal-loop/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runtime endpoint summary did not return an object")
    return payload


def fetch_runtime_events(
    *,
    api_base: str,
    limit: int,
    source: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    path = _url(
        f"{api_base.rstrip('/')}/api/runtime/events",
        {"limit": limit, "source": source},
    )
    request = urllib.request.Request(
        path,
        headers={
            "Accept": "application/json",
            "User-Agent": "coherence-native-route-goal-loop/1.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runtime events did not return an object")
    return payload


def _endpoint_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("endpoints")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and isinstance(row.get("endpoint"), str)]


def _runtime_event_rows(payload: dict[str, Any], *, seconds: int) -> list[dict[str, Any]]:
    rows = payload.get("items")
    if not isinstance(rows, list):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, int(seconds)))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        endpoint = row.get("endpoint")
        method = row.get("method")
        if not isinstance(endpoint, str) or not isinstance(method, str):
            continue
        recorded_at = str(row.get("recorded_at") or "")
        if recorded_at:
            try:
                observed_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
            except ValueError:
                observed_at = None
            if observed_at is not None and observed_at < cutoff:
                continue
        filtered.append(row)
    return filtered


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _route_goal_endpoint(event: dict[str, Any], *, method: str, endpoint: str) -> str:
    metadata = _event_metadata(event)
    for key in ("route_goal_endpoint", "upstream_endpoint"):
        candidate = str(metadata.get(key) or "").strip()
        if candidate.startswith("/api/"):
            return candidate
    if str(event.get("source") or "") == "web_api":
        return WEB_PROXY_UPSTREAM_ENDPOINTS.get((method, endpoint), endpoint)
    return endpoint


def _events_to_summary_payload(
    events_payload: dict[str, Any],
    *,
    seconds: int,
    source: str | None,
) -> tuple[dict[str, Any], str | None]:
    events = _runtime_event_rows(events_payload, seconds=seconds)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    sources_seen: set[str] = set()
    for event in events:
        method = str(event.get("method") or "GET").upper()
        endpoint = _route_goal_endpoint(
            event,
            method=method,
            endpoint=str(event.get("endpoint") or ""),
        )
        groups.setdefault((method, endpoint), []).append(event)
        event_source = str(event.get("source") or "").strip()
        if event_source:
            sources_seen.add(event_source)

    rows: list[dict[str, Any]] = []
    for (method, endpoint), items in groups.items():
        by_source: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        idea_counts: dict[str, int] = {}
        total_runtime_ms = 0.0
        total_cost = 0.0
        for item in items:
            item_source = str(item.get("source") or "unknown")
            by_source[item_source] = by_source.get(item_source, 0) + 1
            status_key = str(item.get("status_code") or 0)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            idea_key = str(item.get("idea_id") or "unmapped")
            idea_counts[idea_key] = idea_counts.get(idea_key, 0) + 1
            total_runtime_ms += _numeric(item, "runtime_ms")
            total_cost += _numeric(item, "runtime_cost_estimate")
        primary_idea = max(idea_counts.items(), key=lambda pair: pair[1])[0] if idea_counts else "unmapped"
        rows.append(
            {
                "endpoint": endpoint,
                "method": method,
                "methods": [method],
                "idea_id": primary_idea,
                "event_count": len(items),
                "total_runtime_ms": round(total_runtime_ms, 4),
                "average_runtime_ms": round(total_runtime_ms / len(items), 4) if items else 0.0,
                "runtime_cost_estimate": round(total_cost, 8),
                "by_source": by_source,
                "status_counts": status_counts,
            }
        )

    source_effective = source
    if source is not None and sources_seen and sources_seen != {source}:
        source_effective = None
    return {
        "window_seconds": seconds,
        "source": source_effective,
        "measurement_source": "runtime_events",
        "endpoints": rows,
    }, source_effective


def _numeric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return default


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(row.get(key))
    except (TypeError, ValueError):
        return default


def desired_grammar(endpoint: str) -> str:
    if endpoint.startswith("/api/ideas"):
        return "BML idea-route catalog"
    if endpoint.startswith("/api/runtime"):
        return "BML route-observation grammar"
    if endpoint.startswith("/api/inventory"):
        return "inventory lineage grammar"
    if endpoint.startswith("/api/agent"):
        return "agent task grammar"
    if endpoint.startswith("/api/substrate"):
        return "substrate notation grammar"
    if endpoint.startswith("/api/content") or endpoint.startswith("/api/entity"):
        return "content/entity grammar"
    return "BML route catalog"


def find_native_route(method: str, endpoint: str, native_routes: dict[str, NativeRoute]) -> NativeRoute | None:
    wanted_method = method.upper()
    native = native_routes.get(_route_key(wanted_method, endpoint))
    if native:
        return native
    template_matches = [
        route
        for route in native_routes.values()
        if route.method.upper() == wanted_method and _template_route_matches(route.endpoint, endpoint)
    ]
    if template_matches:
        return max(template_matches, key=lambda route: len(route.endpoint))
    wildcard_matches = [
        route
        for route in native_routes.values()
        if (
            route.method.upper() == wanted_method
            and route.endpoint.endswith("*")
            and _wildcard_route_matches(route.endpoint, endpoint)
        )
    ]
    if not wildcard_matches:
        return None
    return max(wildcard_matches, key=lambda route: len(route.endpoint))


def _wildcard_route_matches(pattern: str, endpoint: str) -> bool:
    prefix = pattern[:-1]
    if not endpoint.startswith(prefix):
        return False
    if prefix.endswith("/"):
        return True
    remainder = endpoint[len(prefix):]
    return bool(remainder) and "/" not in remainder


def _template_route_matches(pattern: str, endpoint: str) -> bool:
    if "{" not in pattern and "/:" not in pattern:
        return False
    pattern_parts = pattern.strip("/").split("/")
    endpoint_parts = endpoint.strip("/").split("/")
    if len(pattern_parts) != len(endpoint_parts):
        return False
    for pattern_part, endpoint_part in zip(pattern_parts, endpoint_parts, strict=True):
        template_segment = (
            (pattern_part.startswith(":") and len(pattern_part) > 1)
            or (
                pattern_part.startswith("{")
                and pattern_part.endswith("}")
                and len(pattern_part) > 2
            )
        )
        if template_segment:
            if not endpoint_part:
                return False
            continue
        if pattern_part != endpoint_part:
            return False
    return True


def route_status(method: str, endpoint: str, native_routes: dict[str, NativeRoute]) -> tuple[str, str, bool, bool]:
    native = find_native_route(method, endpoint, native_routes)
    if not native:
        return "python-fanout", desired_grammar(endpoint), False, False
    if native.required_header and native.required_header != "Accept":
        return "kernel-native-header-gated", native.grammar, False, False
    high_grammar = native.grammar in {"BML"}
    if high_grammar:
        return "kernel-native-high-grammar", native.grammar, True, True
    return "kernel-native-form-needs-source-lift", native.grammar, True, False


def build_goal_state(
    *,
    payload: dict[str, Any],
    source_requested: str | None,
    source_effective: str | None,
    seconds: int,
    target_share: float,
) -> dict[str, Any]:
    native_routes = load_native_routes()
    rows = sorted(
        _endpoint_rows(payload),
        key=lambda row: (_int(row, "event_count"), _numeric(row, "total_runtime_ms")),
        reverse=True,
    )
    total_events = sum(_int(row, "event_count") for row in rows)
    total_runtime_ms = sum(_numeric(row, "total_runtime_ms") for row in rows)

    route_rows: list[dict[str, Any]] = []
    cumulative_events = 0
    goal_native_events = 0
    executable_native_events = 0
    for row in rows:
        endpoint = str(row.get("endpoint") or "")
        method = str(row.get("method") or (row.get("methods") or ["GET"])[0] or "GET").upper()
        event_count = _int(row, "event_count")
        cumulative_events += event_count
        status, grammar, native_executable, high_grammar_native = route_status(method, endpoint, native_routes)
        if high_grammar_native:
            goal_native_events += event_count
        if native_executable:
            executable_native_events += event_count
        native = find_native_route(method, endpoint, native_routes)
        route_rows.append(
            {
                "method": method,
                "endpoint": endpoint,
                "methods": [method],
                "event_count": event_count,
                "traffic_share": round(event_count / total_events, 6) if total_events else 0.0,
                "cumulative_traffic_share": round(cumulative_events / total_events, 6) if total_events else 0.0,
                "total_runtime_ms": round(_numeric(row, "total_runtime_ms"), 4),
                "average_runtime_ms": round(_numeric(row, "average_runtime_ms"), 4),
                "by_source": row.get("by_source") if isinstance(row.get("by_source"), dict) else {},
                "status": status,
                "current_grammar": native.grammar if native else "",
                "current_source": native.source_file if native else "",
                "current_handler": native.handler if native else "",
                "current_required_header": native.required_header if native else "",
                "desired_grammar": grammar,
                "native_executable": native_executable,
                "high_grammar_native": high_grammar_native,
            }
        )

    promotion_rows: list[dict[str, Any]] = []
    promotion_events = goal_native_events
    for row in route_rows:
        if row["high_grammar_native"]:
            continue
        if total_events and promotion_events / total_events >= target_share:
            break
        promotion_rows.append(row)
        promotion_events += int(row["event_count"])

    next_route = promotion_rows[0] if promotion_rows else None
    source_filter_ready = source_requested is None or source_requested == source_effective
    if not source_filter_ready:
        next_action = "deploy-web-api-source-filter"
        next_task_card = source_filter_task_card(source_requested=source_requested, source_effective=source_effective)
    elif next_route:
        next_action = "promote-route"
        next_task_card = task_card(next_route)
    else:
        next_action = "observe-next-route-window"
        next_task_card = target_satisfied_task_card(source_requested=source_requested, source_effective=source_effective)
    state = {
        "generated_at": _now_iso(),
        "goal": "90% of web-used API method+path traffic served by kernel-native handlers written in BML or a route/domain grammar.",
        "measurement_source": str(payload.get("measurement_source") or "runtime_endpoint_summary"),
        "window_seconds": seconds,
        "source_requested": source_requested,
        "source_effective": source_effective,
        "source_filter_ready": source_filter_ready,
        "target_share": target_share,
        "total_events": total_events,
        "total_runtime_ms": round(total_runtime_ms, 4),
        "goal_native_events": goal_native_events,
        "goal_native_share": round(goal_native_events / total_events, 6) if total_events else 0.0,
        "native_executable_events": executable_native_events,
        "native_executable_share": round(executable_native_events / total_events, 6) if total_events else 0.0,
        "native_route_sources": {
            "bml_routes": len(load_bml_routes()),
            "form_manifest_routes": len(load_form_routes()),
        },
        "cell_surface": {
            "form": "form/form-stdlib/native-route-goal-cells.fk",
            "query": "form/form-stdlib/queries/native-route-goal-tending.fk",
            "make_target": "make native-route-goal-tending",
            "proof": "cd form && ./validate.sh form-stdlib/json.fk form-stdlib/native-route-goal-cells.fk form-stdlib/tests/native-route-goal-cells-band.fk",
        },
        "promotion_needed": promotion_rows,
        "next_route": next_route,
        "next_action": next_action,
        "next_task_card": next_task_card,
        "routes": route_rows,
    }
    return state


def source_filter_task_card(*, source_requested: str | None, source_effective: str | None) -> dict[str, Any]:
    return {
        "goal": "Deploy and verify web API route provenance so /goal ranks web-used traffic instead of all API traffic.",
        "files_allowed": [
            "web/app/api/[...path]/route.ts",
            "api/app/main.py",
            "api/app/routers/runtime.py",
            "api/app/services/runtime_service.py",
            "api/tests/test_runtime_web_api_provenance.py",
            "scripts/native_route_goal_loop.py",
            "docs/system_audit/native_route_goal_state.json",
        ],
        "done_when": [
            "GET /api/runtime/endpoints/summary?source=web_api returns source=web_api in the response body.",
            "Using the web interface creates endpoint summaries with by_source.web_api counts.",
            "scripts/native_route_goal_loop.py /goal reports source=web_api, not source=all fallback.",
        ],
        "commands": [
            "cd api && python3 -m pytest -q tests/test_runtime_web_api_provenance.py",
            "./scripts/verify_worktree_local_web.sh --start",
            "python3 scripts/native_route_goal_loop.py /goal --source web_api --seconds 86400 --limit 2000",
        ],
        "constraints": [
            f"Current requested/effective source: {source_requested or 'all'} -> {source_effective or 'all'}.",
            "Do not choose a promotion route from all-traffic fallback when the user asked for web-used route frequency.",
        ],
    }


def target_satisfied_task_card(*, source_requested: str | None, source_effective: str | None) -> dict[str, Any]:
    return {
        "goal": "Refresh route-goal observations until a non-native web-used API route appears, or switch to the backend API source queue for the next promotion.",
        "files_allowed": [
            "scripts/native_route_goal_loop.py",
            "docs/system_audit/native_route_goal_state.json",
            "form/form-stdlib/native-route-goal-cells.fk",
            "form/form-stdlib/tests/native-route-goal-cells-band.fk",
        ],
        "done_when": [
            "scripts/native_route_goal_loop.py /goal --source web_api reports next route none while the observed web_api window remains at or above target.",
            "Fresh web navigation traffic is captured if the web queue is the chosen next source.",
            "If backend promotion is chosen instead, scripts/native_route_goal_loop.py /goal --source api reports the next non-native backend route.",
        ],
        "commands": [
            "python3 scripts/native_route_goal_loop.py /goal --source web_api --seconds 86400 --limit 2000",
            "python3 scripts/native_route_goal_loop.py /goal --source api --seconds 86400 --limit 2000",
            "make native-route-goal-tending",
        ],
        "constraints": [
            f"Current requested/effective source: {source_requested or 'all'} -> {source_effective or 'all'}.",
            "Do not promote a route when the observed window already satisfies the native high-grammar target.",
            "Use fresh observed traffic, not a proxy shell path, to choose the next route.",
        ],
    }


def task_card(route: dict[str, Any] | None) -> dict[str, Any] | None:
    if not route:
        return None
    endpoint = route["endpoint"]
    method = route.get("method", "GET")
    grammar = route["desired_grammar"]
    return {
        "goal": f"Promote {method} {endpoint} to a kernel-native high-grammar handler.",
        "files_allowed": [
            "deploy/front-door/api.bml",
            "form/form-stdlib/tests/source-language-route-class-template-band.fk",
            "kernels/SOURCE_LANGUAGE_KERNEL_ROUTER_TRACKING.md",
            "docs/system_audit/native_route_goal_state.json",
        ],
        "done_when": [
            "The route has a BML or domain-grammar handler cell with real request parsing and JSON/Form response emission.",
            "The native handler parity proof compares current handler output to the kernel output for representative real inputs.",
            "The route appears as high_grammar_native in scripts/native_route_goal_loop.py /goal.",
        ],
        "commands": [
            "python3 scripts/native_route_goal_loop.py /goal --source web_api --seconds 86400 --limit 2000",
            "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk form-stdlib/kernel-http.fk form-stdlib/language-model.fk form-stdlib/tests/source-language-route-class-template-band.fk",
        ],
        "constraints": [
            f"Use the existing Python handler only as contract evidence; write the new route in {grammar}.",
            "Do not add JSON encoding to the kernel carrier; JSON emission stays Form/BML handler code.",
            "Do not add placeholder data, mock DB reads, or route-specific host hacks.",
        ],
    }


def read_goal_payload(args: argparse.Namespace) -> tuple[dict[str, Any], str | None]:
    source = None if args.source in {"", "all", "none", None} else str(args.source)
    try:
        events_payload = fetch_runtime_events(
            api_base=args.api_base,
            limit=args.limit,
            source=source,
            timeout_seconds=args.timeout,
        )
        return _events_to_summary_payload(
            events_payload,
            seconds=args.seconds,
            source=source,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        if not args.fallback_to_all:
            raise SystemExit(f"runtime events fetch failed: {exc}") from exc

    try:
        payload = fetch_endpoint_summary(
            api_base=args.api_base,
            seconds=args.seconds,
            limit=args.limit,
            source=source,
            timeout_seconds=args.timeout,
        )
        if source is not None and payload.get("source") != source:
            if not args.fallback_to_all:
                raise SystemExit("runtime endpoint summary does not expose source filtering yet")
        elif _endpoint_rows(payload) or not args.fallback_to_all or source is None:
            return payload, source
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        if not args.fallback_to_all:
            raise SystemExit(f"runtime summary fetch failed: {exc}") from exc

    try:
        payload = fetch_endpoint_summary(
            api_base=args.api_base,
            seconds=args.seconds,
            limit=args.limit,
            source=None,
            timeout_seconds=args.timeout,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"runtime summary fallback fetch failed: {exc}") from exc
    return payload, None


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_human(state: dict[str, Any], *, command: str) -> None:
    source = state.get("source_effective") or "all"
    total = int(state.get("total_events") or 0)
    goal_share = 100.0 * float(state.get("goal_native_share") or 0.0)
    native_share = 100.0 * float(state.get("native_executable_share") or 0.0)
    measurement_source = state.get("measurement_source") or "unknown"
    print(f"native-route {command}: source={source} measurement={measurement_source} window={state['window_seconds']}s events={total}")
    print(f"goal-native high-grammar share: {goal_share:.2f}%")
    print(f"kernel-native executable share: {native_share:.2f}%")
    next_route = state.get("next_route")
    if isinstance(next_route, dict):
        print(
            "next route: "
            f"{next_route.get('method', 'GET')} {next_route['endpoint']} count={next_route['event_count']} "
            f"share={100.0 * float(next_route['traffic_share']):.2f}% "
            f"desired={next_route['desired_grammar']}"
        )
    else:
        print("next route: none; target already satisfied in the observed window")
    if not bool(state.get("source_filter_ready", True)):
        print("next action: deploy web_api source filtering before promoting from this fallback queue")
    print()
    print("top routes:")
    for row in list(state.get("routes") or [])[:10]:
        print(
            f"- {row.get('method', 'GET')} {row['endpoint']} count={row['event_count']} "
            f"share={100.0 * float(row['traffic_share']):.2f}% "
            f"status={row['status']} desired={row['desired_grammar']}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["goal", "/goal", "loop", "/loop"])
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--seconds", type=int, default=86400)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--source", default="web_api")
    parser.add_argument("--target-share", type=float, default=TARGET_SHARE)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--fallback-to-all", action="store_true", default=True)
    parser.add_argument("--no-fallback-to-all", dest="fallback_to_all", action="store_false")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    command = args.command.lstrip("/")
    payload, source_effective = read_goal_payload(args)
    state = build_goal_state(
        payload=payload,
        source_requested=None if args.source in {"", "all", "none", None} else str(args.source),
        source_effective=source_effective,
        seconds=args.seconds,
        target_share=max(0.0, min(1.0, float(args.target_share))),
    )
    should_write = bool(args.write_state or command == "loop")
    if should_write:
        write_state(args.state_path, state)
    if args.json:
        print(json.dumps(state, indent=2, sort_keys=True))
    else:
        print_human(state, command=f"/{command}")
        if should_write:
            print(f"state: {args.state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
