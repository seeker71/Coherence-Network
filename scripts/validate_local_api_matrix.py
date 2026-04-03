#!/usr/bin/env python3
"""Validate local API-backed page contracts and timing against a running API."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


Validator = Callable[[Any], bool]


@dataclass(frozen=True)
class EndpointContract:
    name: str
    path: str
    validator: Validator
    description: str


def _is_list_payload(body: Any, *keys: str) -> bool:
    if isinstance(body, list):
        return True
    if not isinstance(body, dict):
        return False
    for key in keys:
        value = body.get(key)
        if isinstance(value, list):
            return True
    return False


def _has_keys(body: Any, *keys: str) -> bool:
    return isinstance(body, dict) and all(key in body for key in keys)


API_CONTRACTS: list[EndpointContract] = [
    EndpointContract("health", "/api/health", lambda body: _has_keys(body, "status", "version", "timestamp"), "health fields"),
    EndpointContract("ideas", "/api/ideas", lambda body: _is_list_payload(body, "ideas", "items"), "ideas payload"),
    EndpointContract("coherence_score", "/api/coherence/score", lambda body: _has_keys(body, "score"), "coherence score"),
    EndpointContract("contributors", "/api/contributors", lambda body: _is_list_payload(body, "items"), "contributors list"),
    EndpointContract("contributions", "/api/contributions", lambda body: _is_list_payload(body, "items"), "contributions list"),
    EndpointContract("assets", "/api/assets", lambda body: _is_list_payload(body, "items"), "assets list"),
    EndpointContract("spec_registry", "/api/spec-registry", lambda body: isinstance(body, list), "spec registry list"),
    EndpointContract("marketplace", "/api/marketplace/browse?page=1&page_size=10", lambda body: _has_keys(body, "listings", "total", "page", "page_size"), "marketplace browse"),
    EndpointContract("graph_nodes", "/api/graph/nodes", lambda body: _has_keys(body, "items", "total", "limit", "offset"), "graph nodes list"),
    EndpointContract("graph_edges", "/api/edges", lambda body: _has_keys(body, "items", "total", "limit", "offset"), "graph edges list"),
    EndpointContract("federation_nodes", "/api/federation/nodes", lambda body: isinstance(body, list), "federation nodes list"),
    EndpointContract("providers_stats", "/api/providers/stats", lambda body: _has_keys(body, "providers", "summary"), "provider stats"),
    EndpointContract("federation_stats", "/api/federation/nodes/stats", lambda body: _has_keys(body, "nodes", "providers", "total_measurements"), "federation stats"),
    EndpointContract("automation_usage", "/api/automation/usage?force_refresh=true", lambda body: _has_keys(body, "providers", "tracked_providers"), "automation usage"),
    EndpointContract("automation_readiness", "/api/automation/usage/readiness?force_refresh=true", lambda body: _has_keys(body, "providers", "all_required_ready", "blocking_issues"), "automation readiness"),
    EndpointContract("friction_report", "/api/friction/report?window_days=7", lambda body: _has_keys(body, "total_events", "open_events", "top_block_types"), "friction report"),
    EndpointContract("friction_events", "/api/friction/events?limit=20", lambda body: isinstance(body, list), "friction events"),
    EndpointContract("friction_entry_points", "/api/friction/entry-points?window_days=7&limit=25", lambda body: _has_keys(body, "entry_points", "total_entry_points", "open_entry_points"), "friction entry points"),
    EndpointContract("identity_providers", "/api/identity/providers", lambda body: _has_keys(body, "categories"), "identity providers"),
    EndpointContract("onboarding_roi", "/api/onboarding/roi", lambda body: _has_keys(body, "handle_registrations"), "onboarding ROI"),
    EndpointContract("inventory_lineage", "/api/inventory/system-lineage?runtime_window_seconds=3600", lambda body: _has_keys(body, "generated_at", "specs", "ideas", "runtime"), "system lineage"),
    EndpointContract("runtime_endpoint_summary", "/api/runtime/endpoints/summary?seconds=3600", lambda body: _has_keys(body, "window_seconds", "endpoints"), "runtime endpoint summary"),
]


def _request_json(base_url: str, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, float, Any]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    for attempt in range(4):
        body = None
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, method=method, data=data, headers=headers)
        started = time.perf_counter()
        retry_after = None
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            retry_after = exc.headers.get("Retry-After")
        except (TimeoutError, urllib.error.URLError) as exc:
            raw = str(exc).encode("utf-8", errors="replace")
            status = 599
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = raw.decode("utf-8", errors="replace")
        if status != 429:
            return status, elapsed_ms, body
        sleep_seconds = max(float(retry_after or 2), 0.5)
        time.sleep(sleep_seconds)
    return status, elapsed_ms, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local API response shapes and timing.")
    parser.add_argument("--api-base", default="http://127.0.0.1:18000", help="Base URL for the local API")
    parser.add_argument("--max-ms", type=float, default=1000.0, help="Maximum allowed runtime for curated endpoints")
    parser.add_argument("--exercise-max-endpoints", type=int, default=15, help="Max GET endpoints for runtime exerciser")
    parser.add_argument("--exercise-timeout-seconds", type=float, default=2.0, help="Timeout per exerciser request")
    args = parser.parse_args()

    failures: list[str] = []
    report: dict[str, Any] = {"api_base": args.api_base, "curated": [], "exerciser": None}

    for contract in API_CONTRACTS:
        status, elapsed_ms, body = _request_json(args.api_base, contract.path)
        ok = status == 200 and elapsed_ms <= args.max_ms and contract.validator(body)
        report["curated"].append(
            {
                "name": contract.name,
                "path": contract.path,
                "status_code": status,
                "elapsed_ms": elapsed_ms,
                "ok": ok,
                "description": contract.description,
            }
        )
        if status != 200:
            failures.append(f"{contract.name}: status {status}")
        elif elapsed_ms > args.max_ms:
            failures.append(f"{contract.name}: {elapsed_ms:.2f}ms > {args.max_ms:.2f}ms")
        elif not contract.validator(body):
            failures.append(f"{contract.name}: response shape mismatch")
        time.sleep(0.15)

    exercise_payload = {
        "cycles": 1,
        "max_endpoints": args.exercise_max_endpoints,
        "timeout_seconds": args.exercise_timeout_seconds,
        "runtime_window_seconds": 86400,
    }
    status, elapsed_ms, body = _request_json(
        args.api_base,
        "/api/runtime/exerciser/run",
        method="POST",
        payload=exercise_payload,
    )
    exerciser_report: dict[str, Any] = {
        "status_code": status,
        "elapsed_ms": elapsed_ms,
    }
    if isinstance(body, dict):
        calls = body.get("calls") or []
        slow_successes = [
            {
                "path": row.get("path_called"),
                "runtime_ms": row.get("runtime_ms"),
                "status_code": row.get("status_code"),
            }
            for row in calls
            if int(row.get("status_code", 599)) < 400 and float(row.get("runtime_ms", 0.0)) > args.max_ms
        ]
        exerciser_report.update(
            {
                "summary": body.get("summary"),
                "coverage": body.get("coverage"),
                "slow_successes": slow_successes,
            }
        )
        if slow_successes:
            failures.append(f"runtime exerciser: {len(slow_successes)} successful GET calls exceeded {args.max_ms:.0f}ms")
    else:
        failures.append("runtime exerciser: invalid response body")
        exerciser_report["body"] = body
    if status != 200:
        failures.append(f"runtime exerciser status {status}")
    report["exerciser"] = exerciser_report

    report["failures"] = failures
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
