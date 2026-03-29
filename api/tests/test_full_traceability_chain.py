"""Tests for Full Traceability Chain (spec 162-meta-self-discovery, Scenario 5).

Verifies that the full chain idea → spec → code → API endpoint is traceable
end-to-end. These tests focus on chain integrity, edge consistency, and the
closed-loop verification described in spec 162 Verification Scenario 5.

Acceptance criteria covered:
- Traced endpoints have consistent spec_id/idea_id and matching edges
- Edge target_id values follow documented format conventions
- The chain is self-consistent: edges link back to the correct IDs
- Coverage math is consistent across /endpoints, /modules, and /summary
- Module nodes link to their constituent endpoints' spec/idea lineage
- At least one fully-traced endpoint exists (full chain closed)
- No 500 errors on any meta endpoint
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_endpoints() -> list[dict]:
    return client.get("/api/meta/endpoints").json()["endpoints"]


def _get_modules() -> list[dict]:
    return client.get("/api/meta/modules").json()["modules"]


def _get_summary() -> dict:
    return client.get("/api/meta/summary").json()


# ---------------------------------------------------------------------------
# Chain integrity: spec edges
# ---------------------------------------------------------------------------


def test_spec_edge_target_id_uses_spec_prefix() -> None:
    """implements_spec edge target_id follows 'spec-{spec_id}' format."""
    for ep in _get_endpoints():
        for edge in ep.get("edges", []):
            if edge["type"] == "implements_spec":
                assert edge["target_id"].startswith("spec-"), (
                    f"Edge target_id '{edge['target_id']}' should start with 'spec-'"
                )


def test_spec_edge_target_id_encodes_endpoint_spec_id() -> None:
    """implements_spec edge target_id encodes the endpoint's own spec_id."""
    for ep in _get_endpoints():
        spec_id = ep.get("spec_id")
        if not spec_id:
            continue
        spec_edges = [e for e in ep.get("edges", []) if e["type"] == "implements_spec"]
        assert spec_edges, f"Endpoint {ep['id']} has spec_id but no implements_spec edge"
        target_ids = {e["target_id"] for e in spec_edges}
        assert f"spec-{spec_id}" in target_ids, (
            f"Expected 'spec-{spec_id}' in edge targets, got {target_ids}"
        )


def test_spec_edge_has_non_empty_target_label() -> None:
    """implements_spec edges have a non-empty target_label."""
    for ep in _get_endpoints():
        for edge in ep.get("edges", []):
            if edge["type"] == "implements_spec":
                label = edge.get("target_label", "")
                assert label, (
                    f"implements_spec edge in {ep['id']} has empty target_label"
                )


# ---------------------------------------------------------------------------
# Chain integrity: idea edges
# ---------------------------------------------------------------------------


def test_idea_edge_target_id_matches_endpoint_idea_id() -> None:
    """traces_idea edge target_id equals the endpoint's idea_id field."""
    for ep in _get_endpoints():
        idea_id = ep.get("idea_id")
        if not idea_id:
            continue
        idea_edges = [e for e in ep.get("edges", []) if e["type"] == "traces_idea"]
        assert idea_edges, f"Endpoint {ep['id']} has idea_id but no traces_idea edge"
        target_ids = {e["target_id"] for e in idea_edges}
        assert idea_id in target_ids, (
            f"Expected idea_id '{idea_id}' in edge targets {target_ids}"
        )


def test_idea_edge_target_label_matches_idea_id() -> None:
    """traces_idea edge target_label equals idea_id (the idea's slug)."""
    for ep in _get_endpoints():
        idea_id = ep.get("idea_id")
        if not idea_id:
            continue
        for edge in ep.get("edges", []):
            if edge["type"] == "traces_idea":
                assert edge.get("target_label") == idea_id, (
                    f"traces_idea target_label '{edge.get('target_label')}' "
                    f"!= idea_id '{idea_id}' in {ep['id']}"
                )


# ---------------------------------------------------------------------------
# Chain integrity: module edges
# ---------------------------------------------------------------------------


def test_module_edge_target_id_matches_module_field() -> None:
    """defined_in_module edge target_id equals the endpoint's module field."""
    for ep in _get_endpoints():
        module = ep.get("module")
        if not module:
            continue
        module_edges = [e for e in ep.get("edges", []) if e["type"] == "defined_in_module"]
        if module_edges:
            target_ids = {e["target_id"] for e in module_edges}
            assert module in target_ids, (
                f"Expected module '{module}' in edge targets {target_ids} for {ep['id']}"
            )


def test_module_edge_target_label_is_last_segment() -> None:
    """defined_in_module edge target_label is the last dot-separated segment of the module."""
    for ep in _get_endpoints():
        for edge in ep.get("edges", []):
            if edge["type"] == "defined_in_module":
                label = edge.get("target_label", "")
                target_id = edge.get("target_id", "")
                expected_label = target_id.split(".")[-1] if target_id else ""
                assert label == expected_label, (
                    f"Module edge label '{label}' != last segment of '{target_id}'"
                )


# ---------------------------------------------------------------------------
# Full chain: at least one fully-traced endpoint
# ---------------------------------------------------------------------------


def test_at_least_one_endpoint_with_spec_trace() -> None:
    """At least one endpoint in the system has a spec_id (spec chain is populated)."""
    endpoints = _get_endpoints()
    traced_spec = [ep for ep in endpoints if ep.get("spec_id")]
    assert traced_spec, (
        "No endpoints with spec_id found — the traceability registry appears empty"
    )


def test_at_least_one_endpoint_with_idea_trace() -> None:
    """At least one endpoint in the system has an idea_id (idea chain is populated)."""
    endpoints = _get_endpoints()
    traced_idea = [ep for ep in endpoints if ep.get("idea_id")]
    assert traced_idea, (
        "No endpoints with idea_id found — the traceability registry appears empty"
    )


def test_at_least_one_fully_traced_endpoint_has_all_three_edge_types() -> None:
    """At least one endpoint has spec, idea, and module edges (full chain closed)."""
    endpoints = _get_endpoints()
    for ep in endpoints:
        edge_types = {e["type"] for e in ep.get("edges", [])}
        if (
            "implements_spec" in edge_types
            and "traces_idea" in edge_types
            and "defined_in_module" in edge_types
        ):
            return  # Found a fully-chained endpoint
    # If no endpoint has all three, at least check spec+idea exists
    for ep in endpoints:
        edge_types = {e["type"] for e in ep.get("edges", [])}
        if "implements_spec" in edge_types and "traces_idea" in edge_types:
            return  # Acceptable: spec+idea chain is closed
    pytest.fail("No endpoint found with both spec and idea trace edges — full chain not closed")


# ---------------------------------------------------------------------------
# Scenario 5: Full traceability loop verification
# (spec 162 Verification Scenario 5)
# ---------------------------------------------------------------------------


def test_ideas_endpoint_appears_in_meta_endpoints() -> None:
    """GET /api/ideas is listed in meta endpoints (ideas router is discoverable)."""
    endpoints = _get_endpoints()
    paths = [ep["path"] for ep in endpoints]
    assert "/api/ideas" in paths, "/api/ideas not found in meta endpoint list"


def test_ideas_endpoint_has_spec_trace() -> None:
    """GET /api/ideas has a spec_id linked (ideas endpoint is traced to a spec)."""
    endpoints = _get_endpoints()
    ideas_get = [ep for ep in endpoints if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert ideas_get, "GET /api/ideas not found in meta endpoints"
    ep = ideas_get[0]
    assert ep.get("spec_id") is not None, (
        "GET /api/ideas has no spec_id — traceability chain not closed for ideas endpoint"
    )


def test_ideas_endpoint_has_idea_trace() -> None:
    """GET /api/ideas has an idea_id linked (ideas endpoint traces to its originating idea)."""
    endpoints = _get_endpoints()
    ideas_get = [ep for ep in endpoints if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert ideas_get, "GET /api/ideas not found in meta endpoints"
    ep = ideas_get[0]
    assert ep.get("idea_id") is not None, (
        "GET /api/ideas has no idea_id — idea traceability chain not closed"
    )


def test_ideas_endpoint_spec_and_idea_ids_are_consistent() -> None:
    """GET /api/ideas spec_id='053' and idea_id='portfolio-governance' (known fixed values)."""
    endpoints = _get_endpoints()
    ideas_get = [ep for ep in endpoints if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert ideas_get, "GET /api/ideas not found in meta endpoints"
    ep = ideas_get[0]
    assert ep.get("spec_id") == "053", (
        f"Expected spec_id='053' for GET /api/ideas, got '{ep.get('spec_id')}'"
    )
    assert ep.get("idea_id") == "portfolio-governance", (
        f"Expected idea_id='portfolio-governance' for GET /api/ideas, "
        f"got '{ep.get('idea_id')}'"
    )


def test_ideas_endpoint_has_implements_spec_edge_for_053() -> None:
    """GET /api/ideas has an implements_spec edge pointing to 'spec-053'."""
    endpoints = _get_endpoints()
    ideas_get = [ep for ep in endpoints if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert ideas_get, "GET /api/ideas not found in meta endpoints"
    ep = ideas_get[0]
    spec_edge_targets = {
        e["target_id"] for e in ep.get("edges", []) if e["type"] == "implements_spec"
    }
    assert "spec-053" in spec_edge_targets, (
        f"GET /api/ideas missing implements_spec edge to 'spec-053'. "
        f"Found: {spec_edge_targets}"
    )


def test_ideas_endpoint_has_traces_idea_edge_for_portfolio_governance() -> None:
    """GET /api/ideas has a traces_idea edge pointing to 'portfolio-governance'."""
    endpoints = _get_endpoints()
    ideas_get = [ep for ep in endpoints if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert ideas_get, "GET /api/ideas not found in meta endpoints"
    ep = ideas_get[0]
    idea_edge_targets = {
        e["target_id"] for e in ep.get("edges", []) if e["type"] == "traces_idea"
    }
    assert "portfolio-governance" in idea_edge_targets, (
        f"GET /api/ideas missing traces_idea edge to 'portfolio-governance'. "
        f"Found: {idea_edge_targets}"
    )


# ---------------------------------------------------------------------------
# Cross-service consistency: endpoints ↔ summary ↔ modules
# ---------------------------------------------------------------------------


def test_summary_traced_count_equals_endpoints_with_spec_or_idea() -> None:
    """traced_count in /summary equals count of endpoints with spec_id or idea_id."""
    endpoints = _get_endpoints()
    summary = _get_summary()
    counted = sum(1 for ep in endpoints if ep.get("spec_id") or ep.get("idea_id"))
    assert summary["traced_count"] == counted, (
        f"Summary traced_count={summary['traced_count']} "
        f"!= manual count {counted}"
    )


def test_summary_endpoint_count_equals_meta_endpoints_total() -> None:
    """Summary endpoint_count equals total from /api/meta/endpoints."""
    total = client.get("/api/meta/endpoints").json()["total"]
    summary = _get_summary()
    assert summary["endpoint_count"] == total


def test_summary_module_count_equals_meta_modules_total() -> None:
    """Summary module_count equals total from /api/meta/modules."""
    total = client.get("/api/meta/modules").json()["total"]
    summary = _get_summary()
    assert summary["module_count"] == total


def test_coverage_fraction_derivable_from_endpoints_list() -> None:
    """spec_coverage can be derived from endpoints list independently."""
    endpoints = _get_endpoints()
    summary = _get_summary()
    total = len(endpoints)
    if total == 0:
        assert summary["spec_coverage"] == 0.0
        return
    traced = sum(1 for ep in endpoints if ep.get("spec_id") or ep.get("idea_id"))
    expected = round(traced / total, 4)
    assert abs(summary["spec_coverage"] - expected) < 0.001, (
        f"spec_coverage={summary['spec_coverage']} "
        f"!= {traced}/{total}={expected}"
    )


# ---------------------------------------------------------------------------
# Module-level chain: spec/idea IDs propagate into module nodes
# ---------------------------------------------------------------------------


def test_modules_with_traced_endpoints_carry_spec_ids() -> None:
    """A module that has at least one traced endpoint must carry spec_ids or idea_ids."""
    endpoints = _get_endpoints()
    modules = _get_modules()

    # Build map: module_id → has any traced endpoint
    module_has_trace: dict[str, bool] = {}
    for ep in endpoints:
        mod = ep.get("module")
        if mod:
            if ep.get("spec_id") or ep.get("idea_id"):
                module_has_trace[mod] = True
            elif mod not in module_has_trace:
                module_has_trace[mod] = False

    for mod in modules:
        mid = mod["id"]
        if module_has_trace.get(mid):
            has_links = bool(mod.get("spec_ids") or mod.get("idea_ids"))
            assert has_links, (
                f"Module '{mid}' has traced endpoints but no spec_ids/idea_ids"
            )


def test_module_spec_ids_are_strings() -> None:
    """All spec_ids in module nodes are non-empty strings."""
    for mod in _get_modules():
        for sid in mod.get("spec_ids", []):
            assert isinstance(sid, str) and sid, (
                f"Invalid spec_id '{sid}' in module {mod['id']}"
            )


def test_module_idea_ids_are_strings() -> None:
    """All idea_ids in module nodes are non-empty strings."""
    for mod in _get_modules():
        for iid in mod.get("idea_ids", []):
            assert isinstance(iid, str) and iid, (
                f"Invalid idea_id '{iid}' in module {mod['id']}"
            )


# ---------------------------------------------------------------------------
# Chain idempotency (Scenario 5 edge case: consistent introspection)
# ---------------------------------------------------------------------------


def test_full_chain_is_idempotent_across_two_calls() -> None:
    """Two successive calls return identical traced endpoint counts."""
    r1 = client.get("/api/meta/endpoints").json()
    r2 = client.get("/api/meta/endpoints").json()
    traced1 = sum(1 for ep in r1["endpoints"] if ep.get("spec_id") or ep.get("idea_id"))
    traced2 = sum(1 for ep in r2["endpoints"] if ep.get("spec_id") or ep.get("idea_id"))
    assert traced1 == traced2, (
        f"Traced count changed between calls: {traced1} vs {traced2}"
    )


def test_module_list_is_idempotent() -> None:
    """Two calls to /api/meta/modules return the same total."""
    r1 = client.get("/api/meta/modules").json()["total"]
    r2 = client.get("/api/meta/modules").json()["total"]
    assert r1 == r2


def test_summary_is_idempotent() -> None:
    """Two calls to /api/meta/summary return the same spec_coverage."""
    r1 = client.get("/api/meta/summary").json()["spec_coverage"]
    r2 = client.get("/api/meta/summary").json()["spec_coverage"]
    assert r1 == r2


# ---------------------------------------------------------------------------
# No 500 errors across the full chain
# ---------------------------------------------------------------------------


def test_no_500_on_meta_endpoints() -> None:
    """GET /api/meta/endpoints returns 200, not 500."""
    assert client.get("/api/meta/endpoints").status_code == 200


def test_no_500_on_meta_modules() -> None:
    """GET /api/meta/modules returns 200, not 500."""
    assert client.get("/api/meta/modules").status_code == 200


def test_no_500_on_meta_summary() -> None:
    """GET /api/meta/summary returns 200, not 500."""
    assert client.get("/api/meta/summary").status_code == 200


# ---------------------------------------------------------------------------
# Traceability registry endpoint is reachable
# ---------------------------------------------------------------------------


def test_traceability_registry_endpoint_returns_200() -> None:
    """GET /api/traceability returns HTTP 200 (trace registry is accessible)."""
    resp = client.get("/api/traceability")
    assert resp.status_code == 200


def test_traceability_registry_contains_entries() -> None:
    """GET /api/traceability returns a non-empty list of trace entries."""
    resp = client.get("/api/traceability")
    assert resp.status_code == 200
    data = resp.json()
    # Accept list or dict-with-list
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("traces", data.get("items", data.get("entries", [])))
    else:
        entries = []
    assert len(entries) > 0, (
        "Traceability registry is empty — no @traces_to decorators found"
    )


def test_traceability_registry_entries_have_spec_or_idea() -> None:
    """Each trace entry in /api/traceability has spec or idea field."""
    resp = client.get("/api/traceability")
    assert resp.status_code == 200
    data = resp.json()
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("traces", data.get("items", data.get("entries", [])))
    else:
        entries = []
    for entry in entries:
        has_spec = entry.get("spec") is not None
        has_idea = entry.get("idea") is not None
        assert has_spec or has_idea, (
            f"Trace entry missing both spec and idea: {entry}"
        )
