"""Tests for Spec 162: Ucore Meta Nodes Self Describing.

Verifies acceptance criteria:
- GET /api/meta/endpoints returns 200 with total, endpoints list
- Each endpoint entry has required fields: path, method, id, tags, spec_id/idea_id nullable
- GET /api/meta/modules returns 200 with total, modules list
- Each module entry has required fields including endpoint_count
- GET /api/meta/summary returns 200 with coverage stats
- Edge cases: unknown/missing routes return correct structure
- Coverage math is consistent: coverage = traced / total
- No 500 errors on valid inputs
- Meta router is registered under /api prefix with tag 'meta'
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/meta/endpoints
# ---------------------------------------------------------------------------


def test_meta_endpoints_returns_200() -> None:
    """GET /api/meta/endpoints returns HTTP 200."""
    response = client.get("/api/meta/endpoints")
    assert response.status_code == 200


def test_meta_endpoints_response_has_required_keys() -> None:
    """Response includes 'total' and 'endpoints' keys."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    assert "total" in data
    assert "endpoints" in data


def test_meta_endpoints_total_matches_list_length() -> None:
    """total equals len(endpoints)."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    assert data["total"] == len(data["endpoints"])


def test_meta_endpoints_total_is_positive() -> None:
    """total > 0 — system has at least one registered route."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    assert data["total"] > 0


def test_meta_endpoints_each_entry_has_required_fields() -> None:
    """Every endpoint entry has id, method, path, tags, edges, spec_id, idea_id."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    required = {"id", "method", "path", "tags", "edges"}
    nullable = {"spec_id", "idea_id", "module", "summary", "name"}
    for ep in data["endpoints"]:
        for field in required:
            assert field in ep, f"Missing required field '{field}' in endpoint: {ep.get('id')}"
        for field in nullable:
            assert field in ep, f"Missing nullable field '{field}' in endpoint: {ep.get('id')}"


def test_meta_endpoints_method_is_uppercase_string() -> None:
    """method field is a non-empty uppercase string like GET, POST."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert isinstance(ep["method"], str)
        assert ep["method"].upper() == ep["method"]
        assert len(ep["method"]) > 0


def test_meta_endpoints_path_starts_with_slash() -> None:
    """path field starts with '/'."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert ep["path"].startswith("/"), f"Bad path: {ep['path']}"


def test_meta_endpoints_tags_is_list() -> None:
    """tags is always a list (may be empty)."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert isinstance(ep["tags"], list)


def test_meta_endpoints_edges_is_list() -> None:
    """edges is always a list (may be empty)."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert isinstance(ep["edges"], list)


def test_meta_endpoints_spec_id_is_string_or_null() -> None:
    """spec_id is either a string or null."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert ep["spec_id"] is None or isinstance(ep["spec_id"], str)


def test_meta_endpoints_idea_id_is_string_or_null() -> None:
    """idea_id is either a string or null."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        assert ep["idea_id"] is None or isinstance(ep["idea_id"], str)


def test_meta_endpoints_id_format() -> None:
    """id field matches 'METHOD /path' format."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        node_id = ep["id"]
        method = ep["method"]
        path = ep["path"]
        assert node_id == f"{method} {path}", (
            f"id '{node_id}' doesn't match 'METHOD /path' for {method} {path}"
        )


def test_meta_endpoints_traced_endpoint_has_edges() -> None:
    """An endpoint with spec_id or idea_id must have at least one edge."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        if ep.get("spec_id") or ep.get("idea_id"):
            assert len(ep["edges"]) >= 1, (
                f"Traced endpoint {ep['id']} missing edges"
            )


def test_meta_endpoints_contains_meta_endpoint_itself() -> None:
    """The /api/meta/endpoints route is listed in the response."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    paths = [ep["path"] for ep in data["endpoints"]]
    assert "/api/meta/endpoints" in paths


def test_meta_endpoints_no_500_on_repeated_calls() -> None:
    """Repeated calls to /api/meta/endpoints never return 500."""
    for _ in range(3):
        response = client.get("/api/meta/endpoints")
        assert response.status_code != 500


# ---------------------------------------------------------------------------
# GET /api/meta/modules
# ---------------------------------------------------------------------------


def test_meta_modules_returns_200() -> None:
    """GET /api/meta/modules returns HTTP 200."""
    response = client.get("/api/meta/modules")
    assert response.status_code == 200


def test_meta_modules_response_has_required_keys() -> None:
    """Response includes 'total' and 'modules' keys."""
    response = client.get("/api/meta/modules")
    data = response.json()
    assert "total" in data
    assert "modules" in data


def test_meta_modules_total_matches_list_length() -> None:
    """total equals len(modules)."""
    response = client.get("/api/meta/modules")
    data = response.json()
    assert data["total"] == len(data["modules"])


def test_meta_modules_total_is_positive() -> None:
    """total > 0 — system has at least one router module."""
    response = client.get("/api/meta/modules")
    data = response.json()
    assert data["total"] > 0


def test_meta_modules_each_entry_has_required_fields() -> None:
    """Each module entry has id, name, module_type, endpoint_count, edges."""
    response = client.get("/api/meta/modules")
    data = response.json()
    required = {"id", "name", "module_type", "endpoint_count", "edges", "spec_ids", "idea_ids"}
    for mod in data["modules"]:
        for field in required:
            assert field in mod, f"Missing field '{field}' in module: {mod.get('id')}"


def test_meta_modules_endpoint_count_is_non_negative_int() -> None:
    """endpoint_count is a non-negative integer."""
    response = client.get("/api/meta/modules")
    data = response.json()
    for mod in data["modules"]:
        assert isinstance(mod["endpoint_count"], int)
        assert mod["endpoint_count"] >= 0


def test_meta_modules_spec_ids_is_list() -> None:
    """spec_ids is always a list."""
    response = client.get("/api/meta/modules")
    data = response.json()
    for mod in data["modules"]:
        assert isinstance(mod["spec_ids"], list)


def test_meta_modules_idea_ids_is_list() -> None:
    """idea_ids is always a list."""
    response = client.get("/api/meta/modules")
    data = response.json()
    for mod in data["modules"]:
        assert isinstance(mod["idea_ids"], list)


def test_meta_modules_module_type_is_valid() -> None:
    """module_type is one of the known category strings."""
    valid_types = {"router", "service", "model", "middleware", "module"}
    response = client.get("/api/meta/modules")
    data = response.json()
    for mod in data["modules"]:
        assert mod["module_type"] in valid_types, (
            f"Unknown module_type '{mod['module_type']}' in module {mod['id']}"
        )


def test_meta_modules_contains_meta_router() -> None:
    """The meta router itself is listed in modules."""
    response = client.get("/api/meta/modules")
    data = response.json()
    module_ids = [m["id"] for m in data["modules"]]
    assert any("meta" in mid for mid in module_ids), (
        f"No meta module found in: {module_ids}"
    )


def test_meta_modules_no_500_on_repeated_calls() -> None:
    """Repeated calls to /api/meta/modules never return 500."""
    for _ in range(3):
        response = client.get("/api/meta/modules")
        assert response.status_code != 500


# ---------------------------------------------------------------------------
# GET /api/meta/summary
# ---------------------------------------------------------------------------


def test_meta_summary_returns_200() -> None:
    """GET /api/meta/summary returns HTTP 200."""
    response = client.get("/api/meta/summary")
    assert response.status_code == 200


def test_meta_summary_response_has_required_keys() -> None:
    """Response includes endpoint_count, module_count, traced_count, spec_coverage."""
    response = client.get("/api/meta/summary")
    data = response.json()
    for key in ("endpoint_count", "module_count", "traced_count", "spec_coverage"):
        assert key in data, f"Missing key '{key}' in summary response"


def test_meta_summary_endpoint_count_is_positive() -> None:
    """endpoint_count > 0."""
    response = client.get("/api/meta/summary")
    data = response.json()
    assert data["endpoint_count"] > 0


def test_meta_summary_traced_count_within_total() -> None:
    """traced_count <= endpoint_count."""
    response = client.get("/api/meta/summary")
    data = response.json()
    assert data["traced_count"] <= data["endpoint_count"]


def test_meta_summary_spec_coverage_is_float_in_range() -> None:
    """spec_coverage is a float between 0.0 and 1.0."""
    response = client.get("/api/meta/summary")
    data = response.json()
    cov = data["spec_coverage"]
    assert isinstance(cov, float)
    assert 0.0 <= cov <= 1.0


def test_meta_summary_coverage_math_consistency() -> None:
    """spec_coverage == traced_count / endpoint_count (within 0.001 tolerance)."""
    response = client.get("/api/meta/summary")
    data = response.json()
    total = data["endpoint_count"]
    traced = data["traced_count"]
    cov = data["spec_coverage"]
    if total > 0:
        expected = traced / total
        assert abs(cov - expected) < 0.001, (
            f"Coverage mismatch: {cov} != {expected} ({traced}/{total})"
        )
    else:
        assert cov == 0.0


def test_meta_summary_consistent_with_endpoints_list() -> None:
    """Summary endpoint_count matches total from /api/meta/endpoints."""
    summary_response = client.get("/api/meta/summary")
    endpoints_response = client.get("/api/meta/endpoints")
    summary = summary_response.json()
    endpoints = endpoints_response.json()
    assert summary["endpoint_count"] == endpoints["total"]


def test_meta_summary_consistent_with_modules_list() -> None:
    """Summary module_count matches total from /api/meta/modules."""
    summary_response = client.get("/api/meta/summary")
    modules_response = client.get("/api/meta/modules")
    summary = summary_response.json()
    modules = modules_response.json()
    assert summary["module_count"] == modules["total"]


def test_meta_summary_module_count_is_positive() -> None:
    """module_count > 0."""
    response = client.get("/api/meta/summary")
    data = response.json()
    assert data["module_count"] > 0


def test_meta_summary_no_500() -> None:
    """GET /api/meta/summary does not return 500."""
    response = client.get("/api/meta/summary")
    assert response.status_code != 500


# ---------------------------------------------------------------------------
# Meta router registration checks
# ---------------------------------------------------------------------------


def test_meta_endpoints_are_under_api_prefix() -> None:
    """/api/meta/endpoints, /api/meta/modules, /api/meta/summary are all registered."""
    for path in ("/api/meta/endpoints", "/api/meta/modules", "/api/meta/summary"):
        response = client.get(path)
        assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"


def test_meta_endpoints_tagged_with_meta() -> None:
    """At least one endpoint in /api/meta/endpoints carries the 'meta' tag."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    meta_tagged = [ep for ep in data["endpoints"] if "meta" in ep.get("tags", [])]
    assert len(meta_tagged) > 0, "No endpoints with tag 'meta' found"


# ---------------------------------------------------------------------------
# Edge classification: traced vs untraced
# ---------------------------------------------------------------------------


def test_untraced_endpoints_have_null_spec_and_idea() -> None:
    """Endpoints with no trace edges must have null spec_id and idea_id."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        has_trace_edge = any(
            e["type"] in ("implements_spec", "traces_idea") for e in ep.get("edges", [])
        )
        if not has_trace_edge:
            assert ep.get("spec_id") is None, (
                f"Untraced endpoint {ep['id']} has spec_id={ep.get('spec_id')}"
            )
            assert ep.get("idea_id") is None, (
                f"Untraced endpoint {ep['id']} has idea_id={ep.get('idea_id')}"
            )


def test_endpoints_with_spec_id_have_implements_spec_edge() -> None:
    """Endpoints with a spec_id must have an 'implements_spec' edge."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        if ep.get("spec_id"):
            edge_types = [e["type"] for e in ep.get("edges", [])]
            assert "implements_spec" in edge_types, (
                f"Endpoint {ep['id']} has spec_id but no implements_spec edge"
            )


def test_endpoints_with_idea_id_have_traces_idea_edge() -> None:
    """Endpoints with an idea_id must have a 'traces_idea' edge."""
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        if ep.get("idea_id"):
            edge_types = [e["type"] for e in ep.get("edges", [])]
            assert "traces_idea" in edge_types, (
                f"Endpoint {ep['id']} has idea_id but no traces_idea edge"
            )


# ---------------------------------------------------------------------------
# Service unit tests (no HTTP)
# ---------------------------------------------------------------------------


def test_meta_service_list_endpoints_standalone() -> None:
    """meta_service.list_endpoints() can be called with app directly."""
    from app.services import meta_service

    result = meta_service.list_endpoints(app)
    assert result.total >= 0
    assert isinstance(result.endpoints, list)
    assert result.total == len(result.endpoints)


def test_meta_service_list_modules_standalone() -> None:
    """meta_service.list_modules() can be called with app directly."""
    from app.services import meta_service

    result = meta_service.list_modules(app)
    assert result.total >= 0
    assert isinstance(result.modules, list)


def test_meta_service_get_summary_standalone() -> None:
    """meta_service.get_summary() returns MetaSummaryResponse with valid fields."""
    from app.services import meta_service

    result = meta_service.get_summary(app)
    assert result.endpoint_count >= 0
    assert result.module_count >= 0
    assert result.traced_count >= 0
    assert 0.0 <= result.spec_coverage <= 1.0


def test_meta_service_returns_typed_models() -> None:
    """meta_service returns typed Pydantic model instances, not dicts."""
    from app.models.meta import MetaEndpointsResponse, MetaModulesResponse, MetaSummaryResponse
    from app.services import meta_service

    ep = meta_service.list_endpoints(app)
    mod = meta_service.list_modules(app)
    summ = meta_service.get_summary(app)

    assert isinstance(ep, MetaEndpointsResponse)
    assert isinstance(mod, MetaModulesResponse)
    assert isinstance(summ, MetaSummaryResponse)


def test_meta_service_idempotent_multiple_calls() -> None:
    """Calling meta_service.list_endpoints twice returns the same total."""
    from app.services import meta_service

    first = meta_service.list_endpoints(app)
    second = meta_service.list_endpoints(app)
    assert first.total == second.total


# ---------------------------------------------------------------------------
# Edge type validation
# ---------------------------------------------------------------------------


def test_edge_types_are_known_values() -> None:
    """All edge type strings are from the allowed vocabulary."""
    allowed = {"implements_spec", "traces_idea", "defined_in_module"}
    response = client.get("/api/meta/endpoints")
    data = response.json()
    for ep in data["endpoints"]:
        for edge in ep.get("edges", []):
            assert edge["type"] in allowed, (
                f"Unknown edge type '{edge['type']}' in endpoint {ep['id']}"
            )


def test_module_edges_type_is_known() -> None:
    """Module edges use known type strings."""
    allowed = {"implements_spec", "traces_idea"}
    response = client.get("/api/meta/modules")
    data = response.json()
    for mod in data["modules"]:
        for edge in mod.get("edges", []):
            assert edge["type"] in allowed, (
                f"Unknown edge type '{edge['type']}' in module {mod['id']}"
            )
