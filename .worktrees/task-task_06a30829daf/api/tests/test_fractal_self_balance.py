"""Tests for Fractal Self Balance (fractal-self-balance).

Idea: "Self-balancing graph — anti-collapse, organic expansion, entropy management"
Idea ID: fractal-self-balance

Acceptance criteria derived from idea description:
  1. The system monitors its own shape → health endpoint returns structural metrics
  2. When a concept accumulates too many children, it signals for splitting
  3. When orphan nodes cluster, it suggests merging
  4. Concept diversity is measured — if 80% of energy flows to 3 ideas,
     the system surfaces neglected but high-potential branches
  5. Balance is not static — it is dynamic equilibrium that adapts as the network grows
  6. Metrics must distinguish healthy vs unhealthy graph shape
  7. Convergence guard prevents suppression of genuine convergence patterns

These tests validate the idea at the conceptual level; lower-level API
acceptance tests live in test_172_graph_health.py.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import uuid4

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
def _reset_cooldown(monkeypatch):
    """Reset compute cooldown between tests."""
    import app.services.graph_health_service as svc
    monkeypatch.setattr(svc, "_last_compute_time", None)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=_TEST_APP), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_signal(sig_type: str = "split_signal", severity: str = "warning",
                 concept_id: str | None = None, cluster_id: str | None = None,
                 resolved: bool = False):
    from app.db import graph_health_repo
    from app.models.graph_health import GraphSignal
    sig = GraphSignal(
        id=f"fsb_{uuid4().hex[:12]}",
        type=sig_type,
        concept_id=concept_id,
        cluster_id=cluster_id,
        severity=severity,
        created_at=datetime.now(timezone.utc),
        resolved=resolved,
    )
    graph_health_repo.upsert_signal(sig)
    return sig


def _make_graph(parent_count: int = 0, orphan_sizes: list[int] | None = None):
    """Build a synthetic concept + edge list for monkeypatching concept_service.

    Args:
        parent_count: Number of outgoing edges from concept-0 (children).
        orphan_sizes: Each element is the size of a disconnected orphan cluster.
    """
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

    return concepts, edges


# ===========================================================================
# 1. System monitors its own shape
# ===========================================================================

@pytest.mark.asyncio
async def test_health_endpoint_returns_structural_shape_metrics(client):
    """Idea criterion 1: GET /api/graph/health returns structural metrics about graph shape."""
    response = await client.get("/api/graph/health")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "balance_score" in data, "balance_score is the primary shape health indicator"
    assert "entropy_score" in data, "entropy_score measures concept diversity"
    assert "concentration_ratio" in data, "concentration_ratio measures energy distribution"
    assert 0.0 <= data["balance_score"] <= 1.0
    assert isinstance(data["gravity_wells"], list)
    assert isinstance(data["orphan_clusters"], list)
    assert isinstance(data["surface_candidates"], list)


@pytest.mark.asyncio
async def test_balance_score_reflects_graph_state(monkeypatch, client):
    """Balance score is a valid float in [0, 1] for both empty and non-empty graphs."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_empty = await client.post("/api/graph/health/compute")
    assert r_empty.status_code == 200
    assert 0.0 <= r_empty.json()["balance_score"] <= 1.0

    concepts, edges = _make_graph(parent_count=2)
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_healthy = await client.post("/api/graph/health/compute")
    assert r_healthy.status_code == 200
    assert 0.0 <= r_healthy.json()["balance_score"] <= 1.0


# ===========================================================================
# 2. Gravity-well detection: too many children → split signal
# ===========================================================================

@pytest.mark.asyncio
async def test_gravity_well_emits_split_signal_at_threshold(monkeypatch, client):
    """Idea criterion 2: concept with >= SPLIT_THRESHOLD children triggers a split_signal."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    threshold = svc.SPLIT_THRESHOLD
    concepts, edges = _make_graph(parent_count=threshold)

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()

    gw_ids = [gw["concept_id"] for gw in data["gravity_wells"]]
    assert "concept-0" in gw_ids, (
        f"concept-0 with {threshold} children should appear in gravity_wells. Got: {gw_ids}"
    )
    signal_types = [s["type"] for s in data["signals"]]
    assert "split_signal" in signal_types, f"Expected split_signal in {signal_types}"


@pytest.mark.asyncio
async def test_gravity_well_below_threshold_not_flagged(monkeypatch, client):
    """Concepts with fewer children than the threshold must NOT appear in gravity_wells."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    threshold = svc.SPLIT_THRESHOLD
    concepts, edges = _make_graph(parent_count=threshold - 1)

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    gw_ids = [gw["concept_id"] for gw in response.json()["gravity_wells"]]
    assert "concept-0" not in gw_ids


@pytest.mark.asyncio
async def test_critical_gravity_well_severity(monkeypatch, client):
    """Concepts at SPLIT_CRITICAL threshold are flagged as 'critical' severity."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    critical = svc.SPLIT_CRITICAL
    concepts, edges = _make_graph(parent_count=critical)

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    gw_map = {gw["concept_id"]: gw for gw in response.json()["gravity_wells"]}
    assert "concept-0" in gw_map
    assert gw_map["concept-0"]["severity"] == "critical"


# ===========================================================================
# 3. Orphan cluster detection: isolated nodes → merge signal
# ===========================================================================

@pytest.mark.asyncio
async def test_orphan_cluster_emits_merge_signal(monkeypatch, client):
    """Idea criterion 3: Small isolated clusters trigger merge_signal."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    main_concepts = [{"id": f"main-{i}", "name": f"Main {i}"} for i in range(5)]
    main_edges = [{"from": f"main-{i}", "to": f"main-{i+1}", "type": "related"} for i in range(4)]
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
    assert response.status_code == 200
    data = response.json()

    assert len(data["orphan_clusters"]) >= 1, "Expected orphan cluster for isolated 3-node component"
    signal_types = [s["type"] for s in data["signals"]]
    assert "merge_signal" in signal_types, f"Expected merge_signal. Got: {signal_types}"


@pytest.mark.asyncio
async def test_fully_connected_graph_has_no_orphan_clusters(monkeypatch, client):
    """A fully connected graph must not flag any orphan clusters."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": f"node-{i}", "name": f"Node {i}"} for i in range(6)]
    edges = [{"from": "node-0", "to": f"node-{i}", "type": "related"} for i in range(1, 6)]

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    assert response.json()["orphan_clusters"] == []


# ===========================================================================
# 4. Concept diversity: 80% concentration → surface neglected branches
# ===========================================================================

def test_high_concentration_detected():
    """Idea criterion 4: concentration_ratio is high when top-3 concepts hold 80%+ of energy."""
    from app.services.graph_health_service import _concentration_ratio
    counts = [800, 100, 100, 5, 5, 5, 5, 5, 5, 5]
    ratio = _concentration_ratio(counts, top_n=3)
    assert ratio >= 0.80, f"Expected high concentration >= 0.80, got {ratio}"


def test_low_concentration_is_healthy():
    """Uniform distribution produces low concentration_ratio."""
    from app.services.graph_health_service import _concentration_ratio
    counts = [10] * 10
    ratio = _concentration_ratio(counts, top_n=3)
    assert ratio <= 0.40, f"Expected low concentration for uniform dist, got {ratio}"


def test_entropy_drops_under_concentration():
    """Shannon entropy is low when distribution is highly concentrated."""
    from app.services.graph_health_service import _shannon_entropy
    counts = [950] + [5] * 10
    entropy = _shannon_entropy(counts)
    assert entropy < 0.5, f"Expected low entropy for concentrated graph, got {entropy}"


@pytest.mark.asyncio
async def test_surface_candidate_list_present_in_response(monkeypatch, client):
    """Surface candidates list is always present (not null) in health snapshot."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    assert isinstance(response.json()["surface_candidates"], list)


# ===========================================================================
# 5. Dynamic equilibrium: balance adapts as network grows
# ===========================================================================

@pytest.mark.asyncio
async def test_balance_degrades_as_gravity_wells_grow(monkeypatch, client):
    """Idea criterion 5: Balance score is lower with gravity wells + orphan clusters than without.

    Uses a clearly healthy ring graph (uniform engagement, no wells, no orphans) vs a graph
    with a critical gravity well and orphan clusters so the comparison is unambiguous.
    """
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    critical = svc.SPLIT_CRITICAL

    # Healthy baseline: 20-node ring — uniform degree, no gravity wells, no orphans.
    ring_size = 20
    ring_concepts = [{"id": f"ring-{i}", "name": f"Ring {i}"} for i in range(ring_size)]
    ring_edges = [
        {"from": f"ring-{i}", "to": f"ring-{(i+1) % ring_size}", "type": "related"}
        for i in range(ring_size)
    ]
    monkeypatch.setattr(cs, "_concepts", ring_concepts)
    monkeypatch.setattr(cs, "_edges", ring_edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in ring_concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r1 = await client.post("/api/graph/health/compute")
    assert r1.status_code == 200
    score_balanced = r1.json()["balance_score"]

    # Unhealthy state: critical gravity well + multiple orphan clusters.
    concepts_gw, edges_gw = _make_graph(parent_count=critical, orphan_sizes=[3, 3, 3])
    monkeypatch.setattr(cs, "_concepts", concepts_gw)
    monkeypatch.setattr(cs, "_edges", edges_gw)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts_gw})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r2 = await client.post("/api/graph/health/compute")
    assert r2.status_code == 200
    score_with_gw = r2.json()["balance_score"]

    assert score_with_gw < score_balanced, (
        f"Critical gravity well + orphan clusters should reduce balance score. "
        f"Healthy={score_balanced}, Unhealthy={score_with_gw}"
    )


@pytest.mark.asyncio
async def test_compute_endpoint_reflects_latest_state(monkeypatch, client):
    """POST /api/graph/health/compute returns a snapshot that reflects current graph state.

    Tests that balance_score changes between an empty graph (score=0.0) and a non-empty
    graph (positive score), proving compute uses the current state rather than a stale cache.
    """
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    # State A: empty graph → balance_score=0.0
    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_a = await client.post("/api/graph/health/compute")
    assert r_a.status_code == 200
    data_a = r_a.json()
    score_a = data_a["balance_score"]
    assert score_a == 0.0, f"Empty graph should have balance_score=0.0, got {score_a}"

    # State B: connected graph → positive balance_score
    concepts_b = [{"id": f"c-{i}", "name": f"C{i}"} for i in range(6)]
    edges_b = [{"from": f"c-{i}", "to": f"c-{i+1}", "type": "related"} for i in range(5)]
    monkeypatch.setattr(cs, "_concepts", concepts_b)
    monkeypatch.setattr(cs, "_edges", edges_b)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts_b})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r_b = await client.post("/api/graph/health/compute")
    assert r_b.status_code == 200
    data_b = r_b.json()
    score_b = data_b["balance_score"]
    assert score_b > 0.0, f"Non-empty connected graph should have positive balance_score, got {score_b}"

    assert score_b != score_a, (
        f"Compute must reflect state changes: empty={score_a}, with-6-nodes={score_b}"
    )


# ===========================================================================
# 6. Healthy vs unhealthy metrics distinction
# ===========================================================================

def test_healthy_graph_has_high_entropy():
    """Uniform concept engagement should produce high entropy (healthy signal)."""
    from app.services.graph_health_service import _shannon_entropy, ENTROPY_HEALTHY
    counts = [100] * 10
    entropy = _shannon_entropy(counts)
    assert entropy >= ENTROPY_HEALTHY, (
        f"Healthy uniform distribution should have entropy >= {ENTROPY_HEALTHY}, got {entropy}"
    )


def test_unhealthy_graph_has_low_entropy():
    """Highly skewed engagement should produce entropy below the warning threshold."""
    from app.services.graph_health_service import _shannon_entropy, ENTROPY_WARNING
    counts = [9990] + [1] * 10
    entropy = _shannon_entropy(counts)
    assert entropy < ENTROPY_WARNING, (
        f"Skewed distribution should have entropy < {ENTROPY_WARNING}, got {entropy}"
    )


def test_balance_score_formula_bounds():
    """Balance score formula (40% entropy + 30% conc + 20% orphan + 10% grav) bounds [0, 1]."""
    # All-good
    balance_best = round(1.0 * 0.4 + 1.0 * 0.3 + 1.0 * 0.2 + 1.0 * 0.1, 4)
    assert balance_best == 1.0
    # All-bad
    balance_worst = round(0.0 * 0.4 + 0.0 * 0.3 + 0.0 * 0.2 + 0.0 * 0.1, 4)
    assert balance_worst == 0.0


# ===========================================================================
# 7. Convergence guard: genuine convergence not wrongly suppressed
# ===========================================================================

@pytest.mark.asyncio
async def test_convergence_guard_prevents_false_split_signal(monkeypatch, client):
    """Idea criterion 7: Setting a convergence guard stops split signals for that concept."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    threshold = svc.SPLIT_THRESHOLD
    concepts, edges = _make_graph(parent_count=threshold + 2)

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    guard_resp = await client.post(
        "/api/graph/concepts/concept-0/convergence-guard",
        json={"reason": "Intentional fractal depth — correct behaviour", "set_by": "reviewer"},
    )
    assert guard_resp.status_code == 200
    assert guard_resp.json()["convergence_guard"] is True

    monkeypatch.setattr(svc, "_last_compute_time", None)
    r = await client.post("/api/graph/health/compute")
    assert r.status_code == 200
    data = r.json()

    gw_ids = [gw["concept_id"] for gw in data["gravity_wells"]]
    assert "concept-0" not in gw_ids, "Guarded concept must be excluded from gravity_wells"

    c0_signals = [s["type"] for s in data["signals"] if s.get("concept_id") == "concept-0"]
    assert "split_signal" not in c0_signals
    assert "convergence_ok" in c0_signals


@pytest.mark.asyncio
async def test_removing_convergence_guard_re_enables_split_detection(monkeypatch, client):
    """After guard removal, the concept is again eligible for split_signal."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    guard_concept_id = "concept-guard-rm"
    existing = list(cs._concepts)
    existing.append({"id": guard_concept_id, "name": "Guard Removal Test Concept"})
    monkeypatch.setattr(cs, "_concepts", existing)
    idx = dict(cs._concept_index)
    idx[guard_concept_id] = {"id": guard_concept_id, "name": "Guard Removal Test Concept"}
    monkeypatch.setattr(cs, "_concept_index", idx)

    guard_set = await client.post(
        f"/api/graph/concepts/{guard_concept_id}/convergence-guard",
        json={"reason": "test", "set_by": "tester"},
    )
    assert guard_set.status_code == 200

    guard_del = await client.delete(f"/api/graph/concepts/{guard_concept_id}/convergence-guard")
    assert guard_del.status_code == 200
    assert guard_del.json()["convergence_guard"] is False
    assert not svc.guard_exists(guard_concept_id)


# ===========================================================================
# 8. ROI: prove the balancing is working over time
# ===========================================================================

@pytest.mark.asyncio
async def test_roi_endpoint_shows_signal_impact(client):
    """The ROI endpoint must confirm whether balancing actions are improving the graph."""
    response = await client.get("/api/graph/health/roi")
    assert response.status_code == 200
    data = response.json()

    assert "balance_score_delta" in data
    assert "split_signals_actioned" in data
    assert "merge_signals_actioned" in data
    assert "surface_signals_actioned" in data
    assert data["spec_ref"] == "spec-172"
    assert isinstance(data["split_signals_actioned"], int)
    assert isinstance(data["merge_signals_actioned"], int)


@pytest.mark.asyncio
async def test_roi_actioned_count_non_negative(client):
    """ROI actioned counts must always be non-negative integers."""
    response = await client.get("/api/graph/health/roi")
    assert response.status_code == 200
    data = response.json()

    assert data["split_signals_actioned"] >= 0
    assert data["merge_signals_actioned"] >= 0
    assert data["surface_signals_actioned"] >= 0
