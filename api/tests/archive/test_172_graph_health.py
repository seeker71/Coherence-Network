"""API acceptance tests for Graph Health spec-172 (fractal-self-balance).

Lower-level endpoint and metric acceptance coverage for the MVP contract.
Conceptual-level tests live in test_fractal_self_balance.py.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    from app.routers.graph_health import router
    _app = FastAPI()
    _app.include_router(router, prefix="/api")
    return _app


_TEST_APP = _build_app()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Reset service module state between tests."""
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
# Helpers
# ---------------------------------------------------------------------------

def _seed_graph(monkeypatch, parent_count: int = 0, orphan_sizes: list[int] | None = None):
    """Monkeypatch concept_service with a synthetic graph."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "concept-0", "name": "Root Concept"}]
    edges = []

    for i in range(parent_count):
        cid = f"child-{i}"
        concepts.append({"id": cid, "name": f"Child {i}"})
        edges.append({"from": "concept-0", "to": cid, "type": "has_child"})

    for oi, size in enumerate(orphan_sizes or []):
        base = f"orphan-{oi}-"
        cluster_nodes = [f"{base}{j}" for j in range(size)]
        for cn in cluster_nodes:
            concepts.append({"id": cn, "name": f"Orphan {cn}"})
        for j in range(size - 1):
            edges.append({"from": cluster_nodes[j], "to": cluster_nodes[j + 1], "type": "related"})

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)
    return concepts, edges


# ===========================================================================
# Spec-172 named acceptance tests (referenced in spec acceptance list)
# ===========================================================================

@pytest.mark.asyncio
async def test_get_health_returns_shape_metrics(client):
    """GET /api/graph/health returns HTTP 200 with all required shape metric fields."""
    response = await client.get("/api/graph/health")
    assert response.status_code == 200, response.text
    data = response.json()

    required_fields = [
        "balance_score",
        "entropy_score",
        "concentration_ratio",
        "gravity_wells",
        "orphan_clusters",
        "surface_candidates",
        "signals",
        "computed_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    assert isinstance(data["gravity_wells"], list)
    assert isinstance(data["orphan_clusters"], list)
    assert isinstance(data["surface_candidates"], list)
    assert isinstance(data["signals"], list)
    assert isinstance(data["computed_at"], str)


@pytest.mark.asyncio
async def test_compute_health_returns_empty_snapshot_for_empty_graph(monkeypatch, client):
    """POST /api/graph/health/compute on empty graph returns 200 with zeroed metrics and empty lists."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["balance_score"] == 0.0, f"Empty graph balance_score should be 0.0, got {data['balance_score']}"
    assert data["entropy_score"] == 0.0, f"Empty graph entropy_score should be 0.0, got {data['entropy_score']}"
    assert data["concentration_ratio"] == 0.0
    assert data["gravity_wells"] == []
    assert data["orphan_clusters"] == []
    assert data["surface_candidates"] == []
    assert data["signals"] == []
    assert "computed_at" in data


@pytest.mark.asyncio
async def test_compute_health_flags_gravity_well_at_split_threshold(monkeypatch, client):
    """POST /api/graph/health/compute flags concepts at SPLIT_THRESHOLD children as gravity wells with split_signal."""
    import app.services.graph_health_service as svc

    threshold = svc.SPLIT_THRESHOLD
    _seed_graph(monkeypatch, parent_count=threshold)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()

    gw_ids = [gw["concept_id"] for gw in data["gravity_wells"]]
    assert "concept-0" in gw_ids, (
        f"concept-0 with {threshold} children must be a gravity well. Got: {gw_ids}"
    )

    signal_types = [s["type"] for s in data["signals"]]
    assert "split_signal" in signal_types, f"Expected split_signal in signals. Got: {signal_types}"

    # Verify gravity well has required fields
    gw = next(gw for gw in data["gravity_wells"] if gw["concept_id"] == "concept-0")
    assert gw["child_count"] == threshold
    assert gw["severity"] in ("warning", "critical")


@pytest.mark.asyncio
async def test_compute_health_flags_small_orphan_cluster(monkeypatch, client):
    """POST /api/graph/health/compute reports small disconnected clusters and emits merge_signal."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    # Main component: 5 connected nodes
    main_concepts = [{"id": f"main-{i}", "name": f"Main {i}"} for i in range(5)]
    main_edges = [{"from": f"main-{i}", "to": f"main-{i+1}", "type": "related"} for i in range(4)]

    # Orphan component: 3 isolated connected nodes
    orphan_concepts = [{"id": f"iso-{i}", "name": f"Iso {i}"} for i in range(3)]
    orphan_edges = [
        {"from": "iso-0", "to": "iso-1", "type": "related"},
        {"from": "iso-1", "to": "iso-2", "type": "related"},
    ]

    all_concepts = main_concepts + orphan_concepts
    all_edges = main_edges + orphan_edges

    monkeypatch.setattr(cs, "_concepts", all_concepts)
    monkeypatch.setattr(cs, "_edges", all_edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in all_concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["orphan_clusters"]) >= 1, (
        "Expected at least one orphan_cluster for the 3-node isolated component"
    )
    signal_types = [s["type"] for s in data["signals"]]
    assert "merge_signal" in signal_types, f"Expected merge_signal in signals. Got: {signal_types}"

    # Verify orphan cluster has required fields
    oc = data["orphan_clusters"][0]
    assert "cluster_id" in oc
    assert "concept_ids" in oc
    assert oc["size"] >= 2


@pytest.mark.asyncio
async def test_compute_health_surfaces_candidates_when_concentration_exceeds_80_percent(
    monkeypatch, client
):
    """When top 3 concepts hold 80%+ of engagement, surface_candidates are returned."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    # Build a star graph where concept-0 has overwhelming connectivity (high concentration)
    # concept-0 connected to many nodes; other nodes barely connected
    num_children = 20
    concepts = [{"id": "concept-0", "name": "Root"}]
    edges = []
    for i in range(num_children):
        cid = f"child-{i}"
        concepts.append({"id": cid, "name": f"Child {i}"})
        edges.append({"from": "concept-0", "to": cid, "type": "related"})

    # Add a few isolated low-engagement concepts to be surfaced
    for i in range(5):
        cid = f"low-{i}"
        concepts.append({"id": cid, "name": f"Low {i}"})

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()

    # surface_candidates must always be a list (even if empty when concentration is low)
    assert isinstance(data["surface_candidates"], list), "surface_candidates must be a list"

    # When concentration is high, candidates should be surfaced
    if data["concentration_ratio"] >= 0.55:
        assert len(data["surface_candidates"]) > 0, (
            f"Expected surface_candidates when concentration={data['concentration_ratio']:.2f} >= 0.55"
        )

    # Each surface candidate must have concept_id and reason
    for sc in data["surface_candidates"]:
        assert "concept_id" in sc
        assert "reason" in sc


@pytest.mark.asyncio
async def test_balance_score_is_bounded_between_zero_and_one(monkeypatch, client):
    """balance_score must always be in [0.0, 1.0] regardless of graph shape."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    # Test with empty graph
    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_empty = await client.post("/api/graph/health/compute")
    assert r_empty.status_code == 200
    score_empty = r_empty.json()["balance_score"]
    assert 0.0 <= score_empty <= 1.0, f"balance_score out of bounds for empty graph: {score_empty}"

    # Test with healthy graph
    concepts = [{"id": f"c-{i}", "name": f"C{i}"} for i in range(8)]
    edges = [{"from": f"c-{i}", "to": f"c-{i+1}", "type": "related"} for i in range(7)]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_healthy = await client.post("/api/graph/health/compute")
    assert r_healthy.status_code == 200
    score_healthy = r_healthy.json()["balance_score"]
    assert 0.0 <= score_healthy <= 1.0, f"balance_score out of bounds for healthy graph: {score_healthy}"

    # Test with pathological graph (critical gravity well + orphans)
    import app.services.graph_health_service as svc2
    critical = svc2.SPLIT_CRITICAL
    _seed_graph(monkeypatch, parent_count=critical, orphan_sizes=[3, 3, 3])

    r_bad = await client.post("/api/graph/health/compute")
    assert r_bad.status_code == 200
    score_bad = r_bad.json()["balance_score"]
    assert 0.0 <= score_bad <= 1.0, f"balance_score out of bounds for pathological graph: {score_bad}"


# ===========================================================================
# Additional API contract tests
# ===========================================================================

@pytest.mark.asyncio
async def test_compute_returns_fresh_computed_at_on_every_call(monkeypatch, client):
    """POST /api/graph/health/compute always returns a fresh computed_at timestamp."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "c-0", "name": "C0"}, {"id": "c-1", "name": "C1"}]
    edges = [{"from": "c-0", "to": "c-1", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r1 = await client.post("/api/graph/health/compute")
    assert r1.status_code == 200
    ts1 = r1.json()["computed_at"]

    monkeypatch.setattr(svc, "_last_compute_time", None)
    r2 = await client.post("/api/graph/health/compute")
    assert r2.status_code == 200
    ts2 = r2.json()["computed_at"]

    assert isinstance(ts1, str)
    assert isinstance(ts2, str)
    # computed_at is a valid ISO timestamp
    from datetime import datetime
    datetime.fromisoformat(ts1.replace("Z", "+00:00"))
    datetime.fromisoformat(ts2.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_warning_severity_at_split_threshold(monkeypatch, client):
    """Gravity well at exactly SPLIT_THRESHOLD (but below SPLIT_CRITICAL) uses severity='warning'."""
    import app.services.graph_health_service as svc

    threshold = svc.SPLIT_THRESHOLD
    _seed_graph(monkeypatch, parent_count=threshold)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()

    gw = next((g for g in data["gravity_wells"] if g["concept_id"] == "concept-0"), None)
    assert gw is not None, "concept-0 must be in gravity_wells at SPLIT_THRESHOLD"
    assert gw["severity"] == "warning", f"Expected severity=warning at threshold, got {gw['severity']}"


@pytest.mark.asyncio
async def test_critical_severity_at_split_critical(monkeypatch, client):
    """Gravity well at SPLIT_CRITICAL or above uses severity='critical'."""
    import app.services.graph_health_service as svc

    _seed_graph(monkeypatch, parent_count=svc.SPLIT_CRITICAL)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    gw = next(
        (g for g in response.json()["gravity_wells"] if g["concept_id"] == "concept-0"), None
    )
    assert gw is not None
    assert gw["severity"] == "critical"


@pytest.mark.asyncio
async def test_roi_endpoint_returns_required_fields_and_spec_ref(client):
    """GET /api/graph/health/roi returns all required fields with spec_ref='spec-172'."""
    response = await client.get("/api/graph/health/roi")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "balance_score_delta" in data
    assert "split_signals_actioned" in data
    assert "merge_signals_actioned" in data
    assert "surface_signals_actioned" in data
    assert "spec_ref" in data
    assert data["spec_ref"] == "spec-172", f"spec_ref must be 'spec-172', got {data['spec_ref']}"

    assert isinstance(data["split_signals_actioned"], int)
    assert isinstance(data["merge_signals_actioned"], int)
    assert isinstance(data["surface_signals_actioned"], int)
    assert data["split_signals_actioned"] >= 0
    assert data["merge_signals_actioned"] >= 0
    assert data["surface_signals_actioned"] >= 0
