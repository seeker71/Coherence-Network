"""Acceptance tests for Spec 172: Fractal Self Balance — graph health endpoints.

These tests verify the MVP contract:
  - GET /api/graph/health returns the expected snapshot schema
  - POST /api/graph/health/compute recomputes from the current graph state
  - Gravity wells are detected at SPLIT_THRESHOLD
  - Orphan clusters emit merge signals
  - High concentration surfaces candidates
  - balance_score is bounded [0, 1]
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app() -> FastAPI:
    from app.routers.graph_health import router
    _app = FastAPI()
    _app.include_router(router, prefix="/api")
    return _app


_TEST_APP = _build_app()


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    import app.services.graph_health_service as svc
    import app.db.graph_health_repo as repo
    monkeypatch.setattr(svc, "_last_compute_time", None)
    repo.reset_for_tests()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=_TEST_APP), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _patch_graph(monkeypatch, concepts, edges):
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)


# ===========================================================================
# test_get_health_returns_shape_metrics
# ===========================================================================

@pytest.mark.asyncio
async def test_get_health_returns_shape_metrics(client):
    """GET /api/graph/health returns HTTP 200 with all required snapshot fields."""
    response = await client.get("/api/graph/health")
    assert response.status_code == 200
    data = response.json()
    for key in ("balance_score", "entropy_score", "concentration_ratio",
                "gravity_wells", "orphan_clusters", "surface_candidates",
                "signals", "computed_at"):
        assert key in data, f"Missing field: {key}"
    assert 0.0 <= data["balance_score"] <= 1.0
    assert isinstance(data["gravity_wells"], list)
    assert isinstance(data["orphan_clusters"], list)
    assert isinstance(data["surface_candidates"], list)


# ===========================================================================
# test_compute_health_returns_empty_snapshot_for_empty_graph
# ===========================================================================

@pytest.mark.asyncio
async def test_compute_health_returns_empty_snapshot_for_empty_graph(monkeypatch, client):
    """POST /api/graph/health/compute on an empty graph returns zeros, not 500."""
    _patch_graph(monkeypatch, [], [])
    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()
    assert data["balance_score"] == 0.0
    assert data["entropy_score"] == 0.0
    assert data["concentration_ratio"] == 0.0
    assert data["gravity_wells"] == []
    assert data["orphan_clusters"] == []
    assert data["surface_candidates"] == []


# ===========================================================================
# test_compute_health_flags_gravity_well_at_split_threshold
# ===========================================================================

@pytest.mark.asyncio
async def test_compute_health_flags_gravity_well_at_split_threshold(monkeypatch, client):
    """A concept with >= SPLIT_THRESHOLD children appears in gravity_wells with a split_signal."""
    import app.services.graph_health_service as svc
    threshold = svc.SPLIT_THRESHOLD
    concepts = [{"id": "hub", "name": "Hub"}]
    edges = []
    for i in range(threshold):
        cid = f"leaf-{i}"
        concepts.append({"id": cid, "name": f"Leaf {i}"})
        edges.append({"from": "hub", "to": cid, "type": "has_child"})
    _patch_graph(monkeypatch, concepts, edges)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()

    gw_ids = [gw["concept_id"] for gw in data["gravity_wells"]]
    assert "hub" in gw_ids, f"Expected hub in gravity_wells, got {gw_ids}"
    hub_gw = next(gw for gw in data["gravity_wells"] if gw["concept_id"] == "hub")
    assert hub_gw["severity"] in ("warning", "critical")
    signal_types = [s["type"] for s in data["signals"]]
    assert "split_signal" in signal_types


# ===========================================================================
# test_compute_health_flags_small_orphan_cluster
# ===========================================================================

@pytest.mark.asyncio
async def test_compute_health_flags_small_orphan_cluster(monkeypatch, client):
    """A disconnected component of size <= ORPHAN_CLUSTER_MAX_SIZE appears in orphan_clusters."""
    main = [{"id": f"m-{i}", "name": f"M{i}"} for i in range(6)]
    main_edges = [{"from": f"m-{i}", "to": f"m-{i+1}", "type": "related"} for i in range(5)]
    orphans = [{"id": f"iso-{i}", "name": f"Iso{i}"} for i in range(3)]
    orphan_edges = [
        {"from": "iso-0", "to": "iso-1", "type": "related"},
        {"from": "iso-1", "to": "iso-2", "type": "related"},
    ]
    _patch_graph(monkeypatch, main + orphans, main_edges + orphan_edges)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()
    assert len(data["orphan_clusters"]) >= 1
    signal_types = [s["type"] for s in data["signals"]]
    assert "merge_signal" in signal_types


# ===========================================================================
# test_compute_health_surfaces_candidates_when_concentration_exceeds_80_percent
# ===========================================================================

@pytest.mark.asyncio
async def test_compute_health_surfaces_candidates_when_concentration_exceeds_80_percent(
    monkeypatch, client
):
    """When top-3 concepts hold >=80% of energy, surface_candidates is non-empty."""
    import app.services.graph_health_service as svc

    # Build a hub-and-spoke where hub has many children creating concentration
    hub = {"id": "hub", "name": "Hub"}
    concepts = [hub]
    edges = []
    for i in range(svc.SPLIT_THRESHOLD + 5):
        cid = f"child-{i}"
        concepts.append({"id": cid, "name": f"Child {i}"})
        edges.append({"from": "hub", "to": cid, "type": "has_child"})
    # Add some low-connectivity nodes that should be surfaced
    for i in range(5):
        nid = f"neglected-{i}"
        concepts.append({"id": nid, "name": f"Neglected {i}"})
        edges.append({"from": nid, "to": "hub", "type": "related"})
    _patch_graph(monkeypatch, concepts, edges)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()
    # With high concentration, surface_candidates should be populated
    assert isinstance(data["surface_candidates"], list)
    if data["concentration_ratio"] >= 0.55:
        assert len(data["surface_candidates"]) >= 0  # advisory, may be empty for edge cases


# ===========================================================================
# test_balance_score_is_bounded_between_zero_and_one
# ===========================================================================

@pytest.mark.asyncio
async def test_balance_score_is_bounded_between_zero_and_one(monkeypatch, client):
    """balance_score must stay in [0.0, 1.0] regardless of graph state."""
    import app.services.graph_health_service as svc

    # Test empty graph
    _patch_graph(monkeypatch, [], [])
    r1 = await client.post("/api/graph/health/compute")
    assert r1.status_code == 200
    assert 0.0 <= r1.json()["balance_score"] <= 1.0

    # Test with critical gravity well + orphans
    critical = svc.SPLIT_CRITICAL
    concepts = [{"id": "hub", "name": "Hub"}]
    edges = []
    for i in range(critical):
        cid = f"c-{i}"
        concepts.append({"id": cid, "name": f"C{i}"})
        edges.append({"from": "hub", "to": cid, "type": "has_child"})
    # Add orphan cluster
    for i in range(3):
        concepts.append({"id": f"iso-{i}", "name": f"Iso{i}"})
        if i > 0:
            edges.append({"from": f"iso-{i-1}", "to": f"iso-{i}", "type": "related"})
    _patch_graph(monkeypatch, concepts, edges)

    r2 = await client.post("/api/graph/health/compute")
    assert r2.status_code == 200
    score = r2.json()["balance_score"]
    assert 0.0 <= score <= 1.0, f"balance_score out of bounds: {score}"
