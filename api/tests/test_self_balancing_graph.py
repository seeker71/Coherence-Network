"""Tests for Self-Balancing Graph (idea ID: self-balancing-graph).

Validates acceptance criteria from specs/172-fractal-self-balance.md and
specs/fractal-self-balance.md: read-only graph health, anti-collapse signals
(gravity wells, orphan clusters), entropy/concentration metrics, advisory-only
behavior (no automatic graph mutation), and convergence-guard ergonomics.

Parent idea context: fractal-ontology-core. Related implementation:
app.services.graph_health_service, app.routers.graph_health.
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
# Happy path — structural health snapshot and advisory-only contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_balancing_compute_then_get_returns_consistent_snapshot(
    monkeypatch, client
):
    """After compute, GET /api/graph/health returns the same structural metrics as that compute."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "n0", "name": "N0"}, {"id": "n1", "name": "N1"}]
    edges = [{"from": "n0", "to": "n1", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", concepts)
    monkeypatch.setattr(cs, "_edges", edges)
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    post = await client.post("/api/graph/health/compute")
    assert post.status_code == 200
    computed = post.json()

    get = await client.get("/api/graph/health")
    assert get.status_code == 200
    cached = get.json()

    assert cached["balance_score"] == computed["balance_score"]
    assert cached["entropy_score"] == computed["entropy_score"]
    assert cached["concentration_ratio"] == computed["concentration_ratio"]
    assert len(cached["signals"]) == len(computed["signals"])


@pytest.mark.asyncio
async def test_self_balancing_advisory_layer_does_not_mutate_concept_store(
    monkeypatch, client
):
    """MVP is advisory only: health compute must not add/remove concepts or edges."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    concepts = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    edges = [{"from": "a", "to": "b", "type": "related"}]
    monkeypatch.setattr(cs, "_concepts", list(concepts))
    monkeypatch.setattr(cs, "_edges", list(edges))
    monkeypatch.setattr(cs, "_concept_index", {c["id"]: c for c in concepts})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    before_c, before_e = len(cs._concepts), len(cs._edges)
    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    assert len(cs._concepts) == before_c
    assert len(cs._edges) == before_e


# ---------------------------------------------------------------------------
# Edge / error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_balancing_convergence_guard_invalid_body_returns_422(client):
    """POST convergence-guard with missing required fields returns validation error (422)."""
    response = await client.post(
        "/api/graph/concepts/x/convergence-guard",
        json={"reason": "only reason"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_self_balancing_delete_guard_is_idempotent_when_no_guard_exists(client):
    """DELETE convergence-guard when none is set still returns 200 with guard false."""
    response = await client.delete("/api/graph/concepts/never-guarded/convergence-guard")
    assert response.status_code == 200
    data = response.json()
    assert data["concept_id"] == "never-guarded"
    assert data["convergence_guard"] is False


@pytest.mark.asyncio
async def test_self_balancing_empty_graph_compute_returns_200_with_bounded_scores(
    monkeypatch, client
):
    """Empty concept graph: compute must not 500; scores stay in documented ranges."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["balance_score"] <= 1.0
    assert 0.0 <= data["entropy_score"] <= 1.0
    assert 0.0 <= data["concentration_ratio"] <= 1.0
    assert data["gravity_wells"] == []
    assert data["orphan_clusters"] == []
