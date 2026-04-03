"""API contracts for web-consumed panels.

These tests hit the API layer through TestClient and verify the response
shapes used by major API-backed web pages and sub-panels.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _json_get(path: str):
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}: {response.text}"
    return response.json()


def test_automation_page_panel_contracts() -> None:
    usage = _json_get("/api/automation/usage?force_refresh=true")
    readiness = _json_get("/api/automation/usage/readiness?force_refresh=true")
    providers = _json_get("/api/providers/stats")
    nodes = _json_get("/api/federation/nodes")
    network = _json_get("/api/federation/nodes/stats")

    assert "providers" in usage
    assert "tracked_providers" in usage
    assert "providers" in readiness
    assert "all_required_ready" in readiness
    assert "providers" in providers and "summary" in providers
    assert isinstance(nodes, list)
    assert "nodes" in network and "total_measurements" in network


def test_marketplace_and_graph_panel_contracts() -> None:
    marketplace = _json_get("/api/marketplace/browse?page=1&page_size=10")
    nodes = _json_get("/api/graph/nodes")
    edges = _json_get("/api/edges")

    assert {"listings", "total", "page", "page_size"} <= marketplace.keys()
    assert isinstance(nodes, dict) and {"items", "total", "limit", "offset"} <= nodes.keys()
    assert isinstance(edges, dict) and {"items", "total", "limit", "offset"} <= edges.keys()


def test_nodes_page_panel_contracts() -> None:
    nodes = _json_get("/api/federation/nodes")
    providers = _json_get("/api/providers/stats")
    readiness = _json_get("/api/automation/usage/readiness?force_refresh=true")

    assert isinstance(nodes, list)
    assert "providers" in providers and "summary" in providers
    assert "providers" in readiness and "blocking_issues" in readiness


def test_friction_page_panel_contracts() -> None:
    report = _json_get("/api/friction/report?window_days=7")
    events = _json_get("/api/friction/events?limit=20")
    entry_points = _json_get("/api/friction/entry-points?window_days=7&limit=25")

    assert {"total_events", "open_events", "top_block_types", "top_stages"} <= report.keys()
    assert isinstance(events, list)
    assert {"entry_points", "total_entry_points", "open_entry_points"} <= entry_points.keys()


def test_contributions_page_panel_contracts() -> None:
    contributions = _json_get("/api/contributions")
    score = _json_get("/api/coherence/score")
    contributors = _json_get("/api/contributors")
    assets = _json_get("/api/assets")

    assert isinstance(contributions, list) or "items" in contributions
    assert "score" in score
    assert isinstance(contributors, list) or "items" in contributors
    assert isinstance(assets, list) or "items" in assets


def test_identity_and_inventory_panel_contracts() -> None:
    providers = _json_get("/api/identity/providers")
    onboarding = _json_get("/api/onboarding/roi")
    lineage = _json_get("/api/inventory/system-lineage?runtime_window_seconds=3600")
    runtime = _json_get("/api/runtime/endpoints/summary?seconds=3600")

    assert "categories" in providers
    assert "handle_registrations" in onboarding
    assert {"generated_at", "specs", "ideas", "runtime"} <= lineage.keys()
    assert {"window_seconds", "endpoints"} <= runtime.keys()
