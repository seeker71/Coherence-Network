"""Acceptance tests for idea `self-balancing-graph` (spec 172 — fractal self-balance).

Verifies read-only graph health: anti-collapse (gravity wells), organic expansion
(surface candidates), and entropy/concentration metrics. Advisory only — no
automatic concept or edge mutation via health endpoints.
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
def _reset_state(monkeypatch):
    import app.services.graph_health_service as svc
    from app.db import graph_health_repo

    monkeypatch.setattr(svc, "_last_compute_time", None)
    graph_health_repo.reset_for_tests()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=_TEST_APP), base_url="http://test"
    ) as c:
        yield c


def _required_snapshot_keys() -> list[str]:
    return [
        "balance_score",
        "entropy_score",
        "concentration_ratio",
        "gravity_wells",
        "orphan_clusters",
        "surface_candidates",
        "signals",
        "computed_at",
    ]


@pytest.mark.asyncio
async def test_self_balancing_graph_snapshot_happy_path(client):
    """GET /api/graph/health returns 200 with stable snapshot schema (spec 172 requirements)."""
    response = await client.get("/api/graph/health")
    assert response.status_code == 200, response.text
    data = response.json()
    for key in _required_snapshot_keys():
        assert key in data, f"missing field: {key}"
    assert 0.0 <= data["balance_score"] <= 1.0
    assert 0.0 <= data["entropy_score"] <= 1.0
    assert 0.0 <= data["concentration_ratio"] <= 1.0


@pytest.mark.asyncio
async def test_self_balancing_post_compute_empty_graph_edge_case(monkeypatch, client):
    """Empty graph: POST returns 200 with zeros and empty arrays — no 500 (spec 172)."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["balance_score"] == 0.0
    assert data["entropy_score"] == 0.0
    assert data["concentration_ratio"] == 0.0
    assert data["gravity_wells"] == []
    assert data["orphan_clusters"] == []
    assert data["surface_candidates"] == []
    assert data["signals"] == []


@pytest.mark.asyncio
async def test_self_balancing_single_connected_component_no_orphan_clusters_edge(
    monkeypatch, client
):
    """One connected component only: no orphan_clusters (non-main components are orphans)."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": f"n{i}", "name": f"N{i}"} for i in range(4)]
    edges = [{"from": f"n{i}", "to": f"n{i+1}", "type": "related"} for i in range(3)]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["orphan_clusters"] == []
    merge_types = [s["type"] for s in data["signals"] if s["type"] == "merge_signal"]
    assert merge_types == []


@pytest.mark.asyncio
async def test_self_balancing_advisory_only_concepts_unchanged_after_compute(
    monkeypatch, client
):
    """MVP is advisory: health/compute must not add or remove concepts (no auto merge/split)."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    edges = [{"from": "a", "to": "b", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    before = len(cs._concepts)
    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    after = len(cs._concepts)
    assert before == after == 2


@pytest.mark.asyncio
async def test_self_balancing_dangling_edge_endpoints_resilient_edge(monkeypatch, client):
    """Edges referencing unknown endpoints are ignored; computation still returns 200."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "only", "name": "Only"}]
    edges = [{"from": "only", "to": "missing-node", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    data = response.json()
    for key in _required_snapshot_keys():
        assert key in data
