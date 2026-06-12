"""Runtime telemetry preserves web API provenance for route-frequency promotion."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.runtime import RuntimeEventCreate
from app.services import idea_service, runtime_service


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


def test_dynamic_idea_route_records_route_template_after_dispatch(monkeypatch, set_config):
    set_config("runtime", "telemetry_enabled", True)
    captured: list[RuntimeEventCreate] = []

    def fake_record_event(payload: RuntimeEventCreate):
        captured.append(payload)
        return payload

    monkeypatch.setattr(runtime_service, "record_event", fake_record_event)
    idea_service.create_idea(
        idea_id="runtime-route-template-proof",
        name="Runtime Route Template Proof",
        description="Proves middleware records the resolved route template.",
        potential_value=1.0,
        estimated_cost=1.0,
    )

    client = TestClient(app)
    response = client.get("/api/ideas/runtime-route-template-proof")

    assert response.status_code == 200
    assert captured, "API middleware should record dynamic idea detail calls"
    event = captured[-1]
    assert event.endpoint == "/api/ideas/{idea_id}"
    assert event.raw_endpoint == "/api/ideas/runtime-route-template-proof"
    assert event.method == "GET"


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
    assert native_route_goal_loop.route_status("GET", "/api/spec-registry", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/spec-registry/spec-one", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/ideas/idea-one", native_routes) == expected
    assert native_route_goal_loop.route_status("PATCH", "/api/ideas/idea-one", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/ideas/idea-one/specs", native_routes) == expected
    assert native_route_goal_loop.route_status("POST", "/api/ideas/idea-one/questions", native_routes) == expected
    assert (
        native_route_goal_loop.route_status(
            "POST", "/api/ideas/idea-one/questions/answer", native_routes
        )
        == expected
    )
    assert native_route_goal_loop.route_status("GET", "/api/agent/tasks", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/tasks", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/household/events", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/agent/tasks/task_example", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/health/persistence", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/automation/usage/readiness", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/sensings", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/sensings/sensing-example", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/graph/nodes/example-node", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/translations/page/flow", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/translations/concept/lc-example", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/views/health", native_routes) == expected
    assert native_route_goal_loop.route_status("GET", "/api/views/archive", native_routes) == expected
    assert native_route_goal_loop.route_status("POST", "/api/graph/edges", native_routes) == expected
    assert (
        native_route_goal_loop.route_status(
            "POST", "/api/substrate/kernel-image/proposals", native_routes
        )
        == expected
    )


def test_native_route_goal_loop_sees_method_specific_form_mutation_routes():
    native_routes = native_route_goal_loop.load_native_routes()

    expected = ("kernel-native-form-needs-source-lift", "Form", True, False)
    assert native_route_goal_loop.route_status("POST", "/api/ideas", native_routes) == expected
    assert native_route_goal_loop.route_status("POST", "/api/spec-registry", native_routes) == expected
    assert native_route_goal_loop.route_status("PATCH", "/api/spec-registry/spec-one", native_routes) == expected
    assert native_route_goal_loop.route_status("DELETE", "/api/spec-registry/spec-one", native_routes) == expected


def test_native_route_goal_loop_counts_form_mutations_as_native_executable():
    state = native_route_goal_loop.build_goal_state(
        payload={
            "measurement_source": "test",
            "endpoints": [
                {
                    "endpoint": "/api/ideas",
                    "method": "POST",
                    "event_count": 2,
                    "total_runtime_ms": 10.0,
                    "average_runtime_ms": 5.0,
                    "by_source": {"api": 2},
                }
            ],
        },
        source_requested="api",
        source_effective="api",
        seconds=3600,
        target_share=0.9,
    )

    assert state["routes"][0]["status"] == "kernel-native-form-needs-source-lift"
    assert state["routes"][0]["current_handler"] == "route_ideas_create_native_default"
    assert state["native_executable_events"] == 2
    assert state["native_executable_share"] == 1.0
    assert state["goal_native_events"] == 0
    assert "--source api" in state["next_task_card"]["commands"][0]


def test_native_route_goal_loop_task_card_preserves_all_source():
    state = native_route_goal_loop.build_goal_state(
        payload={
            "measurement_source": "test",
            "endpoints": [
                {
                    "endpoint": "/api/not-yet-native",
                    "method": "GET",
                    "event_count": 2,
                    "total_runtime_ms": 10.0,
                    "average_runtime_ms": 5.0,
                    "by_source": {"api": 2},
                }
            ],
        },
        source_requested=None,
        source_effective=None,
        seconds=3600,
        target_share=0.9,
    )

    assert "--source all" in state["next_task_card"]["commands"][0]


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


def test_household_events_native_route_releases_empty_calendar_fanout():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )
    deploy_text = (ROOT / "deploy" / "hostinger" / "auto-deploy.sh").read_text(encoding="utf-8")

    for required in (
        'route("household-events", "GET", "/api/household/events"',
        "def api_household_events(request)",
        "api-household-events-empty-json",
        'kh-header("X-Form-Handler", "api_household_events")',
        'kh-header("X-Form-Python-Authority", "false")',
        "limit must be between 1 and 200",
    ):
        assert required in route_text

    assert "coherence-api-household-events" in ingress_text
    assert "Path(`/api/household/events`)" in ingress_text
    assert "api_household_events" in deploy_text


def test_graph_node_detail_native_route_preserves_slug_lookup_without_swallowing_count():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )
    deploy_verify_text = (ROOT / "scripts" / "verify_web_api_deploy.sh").read_text(encoding="utf-8")
    auto_deploy_text = (ROOT / "deploy" / "hostinger" / "auto-deploy.sh").read_text(encoding="utf-8")

    for required in (
        'route("graph-node-detail", "GET", "/api/graph/nodes/{node_id}"',
        "def api_graph_node_detail(request)",
        "api-graph-node-detail-sql",
        "api-node-json-projected",
        "properties->>'slug' = $1",
        "id = 'contributor:' || $1",
        "entity_views",
        'api-native-ok-json("api_graph_node_detail"',
    ):
        assert required in route_text

    assert "(PathRegexp(`^/api/graph/nodes/[^/]+$`) && !Path(`/api/graph/nodes/count`))" in ingress_text
    assert "api_graph_node_detail" in deploy_verify_text
    assert "/api/graph/nodes/urs" in deploy_verify_text
    assert "api_graph_node_detail" in auto_deploy_text
    assert "/api/graph/nodes/urs" in auto_deploy_text


def test_idea_detail_native_route_preserves_static_idea_reads():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )
    deploy_verify_text = (ROOT / "scripts" / "verify_web_api_deploy.sh").read_text(encoding="utf-8")
    auto_deploy_text = (ROOT / "deploy" / "hostinger" / "auto-deploy.sh").read_text(encoding="utf-8")

    for required in (
        'route("idea-detail", "GET", "/api/ideas/{idea_id}"',
        "def api_idea_detail(request)",
        "api-idea-detail-sql",
        "entity_views WHERE entity_type = 'idea'",
        "COALESCE(NULLIF(properties->>'slug',''), id) = $1",
        'api-native-ok-json("api_idea_detail"',
    ):
        assert required in route_text

    expected_ingress = (
        "(PathRegexp(`^/api/ideas/[^/]+$`) && !Path(`/api/ideas/storage`) && !Path(`/api/ideas/tags`) "
        "&& !Path(`/api/ideas/cards`) && !Path(`/api/ideas/health`) && !Path(`/api/ideas/right-sizing`) "
        "&& !Path(`/api/ideas/showcase`) && !Path(`/api/ideas/resonance`) && !Path(`/api/ideas/count`) "
        "&& !Path(`/api/ideas/progress`) && !Path(`/api/ideas/portfolio-summary`) "
        "&& !Path(`/api/ideas/breath-overview`))"
    )
    assert expected_ingress in ingress_text
    assert "api_idea_detail" in deploy_verify_text
    assert "/api/ideas/user-surfaces" in deploy_verify_text
    assert "api_idea_detail" in auto_deploy_text
    assert "/api/ideas/user-surfaces" in auto_deploy_text


def test_idea_question_native_routes_preserve_question_flow_contract():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        'route("idea-question-create", "POST", "/api/ideas/{idea_id}/questions"',
        'route("idea-question-answer", "POST", "/api/ideas/{idea_id}/questions/answer"',
        "def api_idea_question_create(request)",
        "def api_idea_question_answer(request)",
        "api-idea-question-duplicate-sql",
        "api-idea-question-create-sql",
        "api-idea-question-exists-sql",
        "api-idea-question-answer-sql",
        'api-native-ok-json("api_idea_question_create"',
        'api-native-ok-json("api_idea_question_answer"',
    ):
        assert required in route_text

    assert "PathRegexp(`^/api/ideas/[^/]+/questions$`)" in ingress_text
    assert "PathRegexp(`^/api/ideas/[^/]+/questions/answer$`)" in ingress_text


def test_idea_update_native_route_preserves_patch_flow_contract():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")
    ingress_text = (ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        'route("idea-update", "PATCH", "/api/ideas/{idea_id}"',
        "def api_idea_update(request)",
        "api-idea-update-sql",
        "api-idea-update-parent-remove-child-sql",
        "api-idea-update-parent-add-child-sql",
        "At least one field required",
        'api-native-ok-json("api_idea_update"',
    ):
        assert required in route_text

    assert 'Method(`PATCH`) && PathRegexp(`^/api/ideas/[^/]+$`)' in ingress_text


def test_bml_front_door_captures_query_errors_before_pg_close():
    route_text = (ROOT / "deploy" / "front-door" / "api.bml").read_text(encoding="utf-8")

    assert "let closed = pg_close(conn);\n        if api-query-failed?()" not in route_text
    assert "let query_error = pg_last_error();" in route_text
    assert "let query_failed = gt(str_len(query_error), 0);" in route_text
    assert 'if query_failed then api-service-unavailable("persistence", "' not in route_text
    assert 'if query_failed then api-service-unavailable("persistence", query_error)' in route_text
