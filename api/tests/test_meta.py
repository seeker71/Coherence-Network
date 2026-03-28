from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_endpoints():
    response = client.get("/api/meta/endpoints")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "endpoints" in data
    assert len(data["endpoints"]) > 0
    # Check shape
    ep = data["endpoints"][0]
    expected_keys = {"path", "method", "path_hash", "tag", "summary", "spec_ids", "idea_ids", "contributors", "call_count_30d", "last_called_at", "status"}
    assert set(ep.keys()).issuperset(expected_keys)

def test_list_endpoints_filter_tag():
    # Find a tag that exists
    full_response = client.get("/api/meta/endpoints")
    all_eps = full_response.json()["endpoints"]
    if not all_eps:
        return
    
    tag = all_eps[0]["tag"]
    response = client.get(f"/api/meta/endpoints?tag={tag}")
    assert response.status_code == 200
    data = response.json()
    for ep in data["endpoints"]:
        assert ep["tag"] == tag

def test_get_endpoint_by_hash():
    full_response = client.get("/api/meta/endpoints")
    ep = full_response.json()["endpoints"][0]
    path_hash = ep["path_hash"]
    
    response = client.get(f"/api/meta/endpoints/{path_hash}")
    assert response.status_code == 200
    assert response.json()["path_hash"] == path_hash

def test_get_endpoint_not_found():
    response = client.get("/api/meta/endpoints/nonexistenthash123")
    assert response.status_code == 404

def test_list_modules():
    response = client.get("/api/meta/modules")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "modules" in data
    assert len(data["modules"]) > 0
    # Check shape
    mod = data["modules"][0]
    expected_keys = {"name", "path", "type", "spec_ids", "idea_ids", "contributors", "line_count", "last_modified", "test_file"}
    assert set(mod.keys()).issuperset(expected_keys)

def test_summary():
    response = client.get("/api/meta/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["system"] == "Coherence Network"
    assert "traceability_score" in data
    assert isinstance(data["traceability_score"], float)
    assert "counts" in data
    assert "coverage" in data

def test_trace_spec():
    # Use spec 053 which is known to be in some traces
    response = client.get("/api/meta/trace/053")
    if response.status_code == 404:
        # If 053 is not traced in this environment, try to find one that is
        all_eps = client.get("/api/meta/endpoints").json()["endpoints"]
        traced_ep = next((ep for ep in all_eps if ep["spec_ids"]), None)
        if traced_ep:
            spec_id = traced_ep["spec_ids"][0]
            response = client.get(f"/api/meta/trace/{spec_id}")
        else:
            return # Skip if nothing is traced

    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert "modules" in data
    assert "id" in data
    assert "type" in data

def test_trace_not_found():
    response = client.get("/api/meta/trace/nonexistent-entity-id-xyz")
    assert response.status_code == 404
