"""Runtime telemetry preserves web API provenance for route-frequency promotion."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service


ROOT = Path(__file__).resolve().parents[2]
NATIVE_ROUTE_GOAL_LOOP_SPEC = importlib.util.spec_from_file_location(
    "native_route_goal_loop",
    ROOT / "scripts" / "native_route_goal_loop.py",
)
assert NATIVE_ROUTE_GOAL_LOOP_SPEC and NATIVE_ROUTE_GOAL_LOOP_SPEC.loader
native_route_goal_loop = importlib.util.module_from_spec(NATIVE_ROUTE_GOAL_LOOP_SPEC)
sys.modules[NATIVE_ROUTE_GOAL_LOOP_SPEC.name] = native_route_goal_loop
NATIVE_ROUTE_GOAL_LOOP_SPEC.loader.exec_module(native_route_goal_loop)


def test_web_proxy_request_records_web_api_runtime_source(monkeypatch, set_config):
    set_config("runtime", "telemetry_enabled", True)
    captured: list[RuntimeEventCreate] = []

    def fake_record_event(payload: RuntimeEventCreate):
        captured.append(payload)
        return payload

    monkeypatch.setattr(runtime_service, "record_event", fake_record_event)

    client = TestClient(app)
    response = client.get(
        "/api/ping",
        headers={
            "X-Coherence-Web-Proxy": "next-api-proxy",
            "X-Page-View-Id": "view-test",
            "X-Page-Route": "/ideas",
            "X-Web-Route": "/ideas",
        },
    )

    assert response.status_code == 200
    assert captured, "API middleware should record proxied web API calls"
    event = captured[-1]
    assert event.source == "web_api"
    assert event.endpoint == "/api/ping"
    assert event.metadata["tracking_kind"] == "api_route_request"
    assert event.metadata["page_view_id"] == "view-test"
    assert event.metadata["page_route"] == "/ideas"
    assert event.metadata["web_route"] == "/ideas"
    assert event.metadata["web_proxy"] == "next-api-proxy"


def test_runtime_endpoint_summary_filters_web_api_source(set_config):
    set_config("runtime", "telemetry_enabled", True)

    runtime_service.record_event(
        RuntimeEventCreate(
            source="web_api",
            endpoint="/api/ideas",
            method="GET",
            status_code=200,
            runtime_ms=10.0,
            metadata={"tracking_kind": "api_route_request"},
        )
    )
    runtime_service.record_event(
        RuntimeEventCreate(
            source="api",
            endpoint="/api/agent/tasks",
            method="GET",
            status_code=200,
            runtime_ms=20.0,
            metadata={"tracking_kind": "api_route_request"},
        )
    )

    rows = runtime_service.summarize_by_endpoint(seconds=3600, summary_limit=20, source="web_api")
    endpoints = {row.endpoint: row for row in rows}

    assert "/api/ideas" in endpoints
    assert "/api/agent/tasks" not in endpoints
    assert endpoints["/api/ideas"].event_count == 1
    assert endpoints["/api/ideas"].by_source == {"web_api": 1}


def test_native_route_goal_loop_normalizes_web_health_proxy_to_upstream_route():
    payload = {
        "items": [
            {
                "source": "web_api",
                "endpoint": "/api/health-proxy",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 12.5,
                "runtime_cost_estimate": 0.0,
                "metadata": {"health_proxy_mode": "live"},
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    summary, source_effective = native_route_goal_loop._events_to_summary_payload(
        payload,
        seconds=3600,
        source="web_api",
    )

    assert source_effective == "web_api"
    assert summary["endpoints"][0]["endpoint"] == "/api/health"
    assert summary["endpoints"][0]["event_count"] == 1


def test_native_route_goal_loop_sees_workspace_and_task_routes_as_bml():
    native_routes = native_route_goal_loop.load_native_routes()

    expected = ("kernel-native-high-grammar", "BML", True, True)
    header_gated = ("kernel-native-header-gated", "BML", False, False)
    assert native_route_goal_loop.route_status("GET", "/api/inventory/flow", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/_form/inventory-flow-observation", native_routes) == header_gated
    assert native_route_goal_loop.route_status("GET", "/api/workspaces", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/agent/tasks", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/tasks", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/agent/tasks/task_example", native_routes) == expected
    assert native_route_goal_loop.route_status("POST", "/api/graph/edges", native_routes) == expected
    assert (
        native_route_goal_loop.route_status(
            "POST", "/api/substrate/kernel-image/proposals", native_routes
        )
        == expected
    )


def test_inventory_flow_native_route_expresses_lineage_grammar():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        'route("inventory-flow", "GET", "/api/inventory/flow"',
        'route("inventory-flow-observation", "GET", "/api/_form/inventory-flow-observation"',
        "def api_inventory_flow(request)",
        "def api_inventory_flow_observe(request)",
        "inventory-flow-summary-sql",
        "inventory-flow-items-sql",
        "inventory-flow-spec-json",
        "inventory-flow-process-json",
        "inventory-flow-implementation-json",
        "inventory-flow-validation-json",
        "inventory-flow-contributors-json",
        "inventory-flow-contributions-json",
        "inventory-flow-assets-json",
        "inventory-flow-interdependencies-json",
        "inventory-flow-canary-response-json",
        "inventory-flow-observe-response-json",
        "framebuffer-events",
        "handler_total_ms",
        "jit-stats",
        "inventory lineage grammar core",
        'json-node-pair("python_authority", json-node-bool(false))',
    ):
        assert required in route_text
    assert "X-Form-Native-Inventory" in ingress_text
    assert "coherence-api-inventory-flow-observation" in ingress_text
    assert "X-Form-Observe" in ingress_text
