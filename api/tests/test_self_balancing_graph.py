"""Tests for idea self-balancing-graph (Self Balancing Graph).

Idea ID: self-balancing-graph
Theme: anti-collapse, organic expansion, entropy management.

Acceptance criteria align with specs/172-fractal-self-balance.md — read-only graph
health snapshot, advisory signals, no automatic graph mutation from health endpoints.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app() -> FastAPI:
    from app.routers.graph_health import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


_TEST_APP = _build_app()


@pytest.fixture(autouse=True)
def _reset_graph_health_state(monkeypatch):
    import app.db.graph_health_repo as repo
    import app.services.graph_health_service as svc

    repo.reset_for_tests()
    monkeypatch.setattr(svc, "_last_compute_time", None)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=_TEST_APP), base_url="http://test"
    ) as c:
        yield c


def _seed_chain(monkeypatch, n: int) -> None:
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": f"n-{i}", "name": f"N{i}"} for i in range(n)]
    edges = [
        {"from": f"n-{i}", "to": f"n-{i + 1}", "type": "related"} for i in range(n - 1)
    ]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)


@pytest.mark.asyncio
async def test_happy_path_compute_exposes_balance_entropy_and_concentration(
    monkeypatch, client
):
    """Health compute returns the core self-balancing metrics for a non-trivial graph."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    edges = [{"from": "a", "to": "b", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r = await client.post("/api/graph/health/compute")
    assert r.status_code == 200, r.text
    data = r.json()

    assert "balance_score" in data
    assert "entropy_score" in data
    assert "concentration_ratio" in data
    assert 0.0 <= data["balance_score"] <= 1.0
    assert 0.0 <= data["entropy_score"] <= 1.0
    assert 0.0 <= data["concentration_ratio"] <= 1.0
    assert isinstance(data["signals"], list)


@pytest.mark.asyncio
async def test_edge_entropy_and_concentration_bounded_for_varied_shapes(
    monkeypatch, client
):
    """Entropy and concentration stay in [0, 1] across several graph shapes."""
    shapes = [2, 5, 12]
    for n in shapes:
        _seed_chain(monkeypatch, n)
        r = await client.post("/api/graph/health/compute")
        assert r.status_code == 200, r.text
        d = r.json()
        assert 0.0 <= d["entropy_score"] <= 1.0, f"entropy out of range for n={n}"
        assert 0.0 <= d["concentration_ratio"] <= 1.0, f"concentration out of range for n={n}"


@pytest.mark.asyncio
async def test_edge_advisory_compute_leaves_concept_inventory_unchanged(
    monkeypatch, client
):
    """MVP is advisory: computing health must not add or remove concepts."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "x", "name": "X"}, {"id": "y", "name": "Y"}]
    edges = [{"from": "x", "to": "y", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    before = len(cs._concepts)
    r = await client.post("/api/graph/health/compute")
    assert r.status_code == 200, r.text
    after = len(cs._concepts)
    assert before == after == 2


@pytest.mark.asyncio
async def test_error_shape_related_only_star_has_no_gravity_split_from_has_child(
    monkeypatch, client
):
    """Gravity wells use has_child counts; a star of only related edges does not imply split by degree."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "root", "name": "Root"}]
    edges = []
    for i in range(12):
        cid = f"leaf-{i}"
        concepts.append({"id": cid, "name": f"L{i}"})
        edges.append({"from": "root", "to": cid, "type": "related"})

    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    r = await client.post("/api/graph/health/compute")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["gravity_wells"] == []
    assert not any(s["type"] == "split_signal" for s in data["signals"])


@pytest.mark.asyncio
async def test_get_health_returns_200_after_compute(monkeypatch, client):
    """GET snapshot is stable HTTP 200 after a compute run (baseline visibility)."""
    _seed_chain(monkeypatch, 4)
    await client.post("/api/graph/health/compute")
    g = await client.get("/api/graph/health")
    assert g.status_code == 200, g.text
    body = g.json()
    assert "computed_at" in body
    assert isinstance(body["orphan_clusters"], list)


@pytest.mark.asyncio
async def test_get_health_baseline_without_prior_compute(client):
    """GET /api/graph/health is always HTTP 200 (shape visible even before first compute)."""
    r = await client.get("/api/graph/health")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "balance_score" in data
    assert 0.0 <= data["balance_score"] <= 1.0
