"""Tests for Full Traceability Chain (spec 162-meta-self-discovery, Scenario 5).

Verifies that the full chain idea -> spec -> code -> API endpoint is traceable
end-to-end.
"""

from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _get_endpoints():
    return client.get("/api/meta/endpoints").json()["endpoints"]

def _get_modules():
    return client.get("/api/meta/modules").json()["modules"]

def _get_summary():
    return client.get("/api/meta/summary").json()

def test_spec_edge_target_id_uses_spec_prefix():
    for ep in _get_endpoints():
        for edge in ep.get("edges", []):
            if edge["type"] == "implements_spec":
                assert edge["target_id"].startswith("spec-")

def test_spec_edge_encodes_endpoint_spec_id():
    for ep in _get_endpoints():
        spec_id = ep.get("spec_id")
        if not spec_id:
            continue
        spec_edges = [e for e in ep.get("edges", []) if e["type"] == "implements_spec"]
        target_ids = {e["target_id"] for e in spec_edges}
        assert f"spec-{spec_id}" in target_ids

def test_idea_edge_target_id_matches_idea_id():
    for ep in _get_endpoints():
        idea_id = ep.get("idea_id")
        if not idea_id:
            continue
        idea_edges = [e for e in ep.get("edges", []) if e["type"] == "traces_idea"]
        assert idea_edges
        target_ids = {e["target_id"] for e in idea_edges}
        assert idea_id in target_ids

def test_module_edge_target_id_matches_module_field():
    for ep in _get_endpoints():
        module = ep.get("module")
        if not module:
            continue
        module_edges = [e for e in ep.get("edges", []) if e["type"] == "defined_in_module"]
        if module_edges:
            target_ids = {e["target_id"] for e in module_edges}
            assert module in target_ids

def test_at_least_one_endpoint_with_spec_trace():
    assert any(ep.get("spec_id") for ep in _get_endpoints())

def test_at_least_one_endpoint_with_idea_trace():
    assert any(ep.get("idea_id") for ep in _get_endpoints())

def test_ideas_endpoint_appears_in_meta():
    paths = [ep["path"] for ep in _get_endpoints()]
    assert "/api/ideas" in paths

def test_ideas_endpoint_has_spec_053():
    eps = [ep for ep in _get_endpoints() if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert eps
    assert eps[0].get("spec_id") == "053"

def test_ideas_endpoint_has_idea_portfolio_governance():
    eps = [ep for ep in _get_endpoints() if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert eps
    assert eps[0].get("idea_id") == "portfolio-governance"

def test_ideas_endpoint_has_spec_edge_053():
    eps = [ep for ep in _get_endpoints() if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert eps
    targets = {e["target_id"] for e in eps[0].get("edges", []) if e["type"] == "implements_spec"}
    assert "spec-053" in targets

def test_ideas_endpoint_has_idea_edge_portfolio_governance():
    eps = [ep for ep in _get_endpoints() if ep["path"] == "/api/ideas" and ep["method"] == "GET"]
    assert eps
    targets = {e["target_id"] for e in eps[0].get("edges", []) if e["type"] == "traces_idea"}
    assert "portfolio-governance" in targets

def test_summary_traced_count_equals_manual_count():
    endpoints = _get_endpoints()
    summary = _get_summary()
    counted = sum(1 for ep in endpoints if ep.get("spec_id") or ep.get("idea_id"))
    assert summary["traced_count"] == counted

def test_summary_endpoint_count_equals_total():
    total = client.get("/api/meta/endpoints").json()["total"]
    assert _get_summary()["endpoint_count"] == total

def test_summary_module_count_equals_total():
    total = client.get("/api/meta/modules").json()["total"]
    assert _get_summary()["module_count"] == total

def test_coverage_derivable_from_endpoints():
    endpoints = _get_endpoints()
    summary = _get_summary()
    total = len(endpoints)
    if total == 0:
        assert summary["spec_coverage"] == 0.0
        return
    traced = sum(1 for ep in endpoints if ep.get("spec_id") or ep.get("idea_id"))
    expected = round(traced / total, 4)
    assert abs(summary["spec_coverage"] - expected) < 0.001

def test_modules_with_traced_endpoints_carry_spec_ids():
    endpoints = _get_endpoints()
    modules = _get_modules()
    module_has_trace = {}
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
            assert mod.get("spec_ids") or mod.get("idea_ids")

def test_full_chain_is_idempotent():
    r1 = client.get("/api/meta/endpoints").json()
    r2 = client.get("/api/meta/endpoints").json()
    t1 = sum(1 for ep in r1["endpoints"] if ep.get("spec_id") or ep.get("idea_id"))
    t2 = sum(1 for ep in r2["endpoints"] if ep.get("spec_id") or ep.get("idea_id"))
    assert t1 == t2

def test_no_500_meta_endpoints():
    assert client.get("/api/meta/endpoints").status_code == 200

def test_no_500_meta_modules():
    assert client.get("/api/meta/modules").status_code == 200

def test_no_500_meta_summary():
    assert client.get("/api/meta/summary").status_code == 200

def test_traceability_endpoint_returns_200():
    resp = client.get("/api/traceability")
    assert resp.status_code == 200

def test_traceability_registry_has_entries():
    data = client.get("/api/traceability").json()
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("traces", data.get("items", data.get("entries", [])))
    else:
        entries = []
    assert len(entries) > 0

def test_traceability_entries_have_spec_or_idea():
    data = client.get("/api/traceability").json()
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("traces", data.get("items", data.get("entries", [])))
    else:
        entries = []
    for entry in entries:
        assert entry.get("spec") is not None or entry.get("idea") is not None

def test_module_spec_ids_are_strings():
    for mod in _get_modules():
        for sid in mod.get("spec_ids", []):
            assert isinstance(sid, str) and sid

def test_module_idea_ids_are_strings():
    for mod in _get_modules():
        for iid in mod.get("idea_ids", []):
            assert isinstance(iid, str) and iid

def test_summary_idempotent():
    r1 = client.get("/api/meta/summary").json()["spec_coverage"]
    r2 = client.get("/api/meta/summary").json()["spec_coverage"]
    assert r1 == r2

def test_spec_edge_has_non_empty_label():
    for ep in _get_endpoints():
        for edge in ep.get("edges", []):
            if edge["type"] == "implements_spec":
                assert edge.get("target_label"), f"empty label in {ep['id']}"

def test_idea_edge_label_matches_idea_id():
    for ep in _get_endpoints():
        idea_id = ep.get("idea_id")
        if not idea_id:
            continue
        for edge in ep.get("edges", []):
            if edge["type"] == "traces_idea":
                assert edge.get("target_label") == idea_id

def test_at_least_one_fully_traced_endpoint():
    endpoints = _get_endpoints()
    for ep in endpoints:
        edge_types = {e["type"] for e in ep.get("edges", [])}
        if "implements_spec" in edge_types and "traces_idea" in edge_types:
            return
    pytest.fail("No endpoint with both spec and idea edges found")
