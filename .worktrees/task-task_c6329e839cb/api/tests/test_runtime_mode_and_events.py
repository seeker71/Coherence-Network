from __future__ import annotations

import pytest

from app.models.runtime import RuntimeEventCreate
from app.services import idea_service
from app.services.runtime import cache as runtime_cache
from app.services.runtime import events as runtime_events


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
