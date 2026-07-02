from __future__ import annotations

from datetime import datetime, timezone

from app.models.runtime import RuntimeEvent, RuntimeEventCreate
from app.services import runtime_service
from app.services import idea_service
from app.services.runtime import cache as runtime_cache
from app.services.runtime import events as runtime_events
from app.services.runtime import routes as runtime_routes


def test_runtime_cache_meta_key_uses_config_test_context(set_config):
    set_config("api", "testing", True)
    set_config("api", "test_context_id", "case-a")
    set_config("runtime", "events_path", "/tmp/runtime-a.json")

    key_a = runtime_cache.runtime_endpoint_cache_meta_key("runtime_events_list", {"limit": 5})

    set_config("api", "test_context_id", "case-b")
    key_b = runtime_cache.runtime_endpoint_cache_meta_key("runtime_events_list", {"limit": 5})

    assert key_a != key_b


def test_record_event_uses_normalized_endpoint_value(monkeypatch):
    store: dict[str, list[dict]] = {"events": []}

    monkeypatch.setattr(runtime_events.runtime_event_store, "enabled", lambda: False)
    monkeypatch.setattr(runtime_events.runtime_store, "read_store", lambda: store)
    monkeypatch.setattr(runtime_events.runtime_store, "write_store", lambda payload: store.update(payload))
    monkeypatch.setattr(runtime_events.runtime_paths, "estimate_runtime_cost", lambda runtime_ms: 0.0)
    monkeypatch.setattr(runtime_events, "resolve_idea_id", lambda **_: "idea-runtime")
    monkeypatch.setattr(runtime_events, "resolve_origin_idea_id", lambda idea_id: idea_id)
    monkeypatch.setattr(runtime_events, "normalize_endpoint", lambda endpoint, method=None: "/api/ideas/{idea_id}")

    event = runtime_events.record_event(
        RuntimeEventCreate(
            source="api",
            endpoint="/api/ideas/demo-123",
            raw_endpoint="/api/ideas/demo-123?view=full",
            method="GET",
            status_code=200,
            runtime_ms=12.5,
            metadata={"source": "test"},
        )
    )

    assert event.endpoint == "/api/ideas/{idea_id}"
    assert event.raw_endpoint == "/api/ideas/demo-123"
    assert event.metadata["normalized_from"] == "/api/ideas/demo-123"
    assert store["events"], "record_event should persist the event payload"


def test_noisy_activity_runtime_events_flush_as_bucket_summary(monkeypatch):
    from app import main as api_main

    api_main._RUNTIME_AGGREGATE_BUCKETS.clear()
    monkeypatch.setattr(api_main, "_runtime_aggregate_bucket_seconds", lambda: 60)
    monkeypatch.setattr(api_main, "_runtime_aggregate_enabled", lambda: True)

    first = RuntimeEventCreate(
        source="api",
        endpoint="/api/agent/tasks/{task_id}/activity",
        raw_endpoint="/api/agent/tasks/task-a/activity",
        method="POST",
        status_code=201,
        runtime_ms=10.0,
        metadata={"req_id": "req-a"},
    )
    second = first.model_copy(update={"runtime_ms": 20.0})

    assert api_main._record_or_aggregate_runtime_event(first, now_ts=60.0) == []
    assert api_main._record_or_aggregate_runtime_event(second, now_ts=65.0) == []

    flushed = api_main._flush_due_runtime_aggregates(now_ts=120.0)
    api_main._RUNTIME_AGGREGATE_BUCKETS.clear()

    assert len(flushed) == 1
    summary = flushed[0]
    assert summary.endpoint == "/api/agent/tasks/{task_id}/activity"
    assert summary.runtime_ms == 15.0
    assert summary.metadata["tracking_kind"] == "api_route_request_aggregate"
    assert summary.metadata["event_count"] == 2
    assert summary.metadata["total_runtime_ms"] == 30.0


def test_endpoint_summary_weights_aggregate_runtime_events(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        RuntimeEvent(
            id="rt_aggregate",
            source="api",
            endpoint="/api/agent/tasks/{task_id}/activity",
            raw_endpoint="/api/agent/tasks/{task_id}/activity",
            method="POST",
            status_code=201,
            runtime_ms=15.0,
            idea_id="oss-interface-alignment",
            origin_idea_id="oss-interface-alignment",
            metadata={
                "tracking_kind": "api_route_request_aggregate",
                "event_count": 4,
                "total_runtime_ms": 60.0,
            },
            runtime_cost_estimate=0.01,
            recorded_at=now,
        )
    ]

    monkeypatch.setattr(runtime_service, "list_events", lambda **_: rows)
    monkeypatch.setattr(runtime_service, "resolve_origin_idea_id", lambda idea_id: idea_id)

    summary = runtime_service.summarize_by_endpoint(seconds=3600)[0]

    assert summary.event_count == 4
    assert summary.total_runtime_ms == 60.0
    assert summary.average_runtime_ms == 15.0
    assert summary.by_source == {"api": 4}
    assert summary.status_counts == {"201": 4}


def test_runtime_route_registry_covers_live_idea_realization_family():
    assert runtime_routes.normalize_endpoint("/api/health/persistence", "GET") == "/api/health/persistence"
    assert runtime_routes.normalize_endpoint("/api/automation/usage/readiness", "GET") == "/api/automation/usage/readiness"
    assert runtime_routes.normalize_endpoint("/api/views/health", "GET") == "/api/views/health"
    assert runtime_routes.normalize_endpoint("/api/views/archive", "GET") == "/api/views/archive"
    assert runtime_routes.normalize_endpoint("/api/ideas", "GET") == "/api/ideas"
    assert runtime_routes.normalize_endpoint("/api/ideas/demo-123", "GET") == "/api/ideas/{idea_id}"
    assert runtime_routes.normalize_endpoint("/api/ideas/demo-123", "PATCH") == "/api/ideas/{idea_id}"
    assert runtime_routes.normalize_endpoint("/api/ideas/demo-123/questions", "POST") == "/api/ideas/{idea_id}/questions"
    assert (
        runtime_routes.normalize_endpoint("/api/ideas/demo-123/questions/answer", "POST")
        == "/api/ideas/{idea_id}/questions/answer"
    )


def test_domain_discovery_defaults_off_in_test_mode(set_config):
    set_config("api", "testing", True)
    set_config("api", "test_context_id", "idea-domain-test")
    set_config("ideas", "sync_enable_domain_discovery", None)

    assert idea_service._should_discover_registry_domain_ideas() is False

    set_config("ideas", "sync_enable_domain_discovery", "true")
    assert idea_service._should_discover_registry_domain_ideas() is True


def test_route_side_effects_follow_config_in_test_mode(set_config):
    from app.routers import agent_tasks_routes

    set_config("api", "testing", True)
    set_config("api", "test_context_id", "route-side-effects")
    set_config("agent_tasks", "route_side_effects_in_tests", False)
    assert agent_tasks_routes._route_side_effects_enabled_in_tests() is False

    set_config("agent_tasks", "route_side_effects_in_tests", True)
    assert agent_tasks_routes._route_side_effects_enabled_in_tests() is True
