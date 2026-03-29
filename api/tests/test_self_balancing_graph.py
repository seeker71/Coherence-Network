"""Tests for Self-Balancing Graph (idea ID: self-balancing-graph).

Maps to spec `172-fractal-self-balance` / `fractal-self-balance`: anti-collapse diagnostics,
entropy and concentration visibility, advisory signals only (no automatic graph edits).

Acceptance criteria exercised here:
  - GET /api/graph/health returns HTTP 200 with balance, entropy, concentration, wells,
    orphans, surfaces, signals, computed_at
  - POST /api/graph/health/compute succeeds on empty graph (zeros / empty lists)
  - Convergence guard requests with invalid bodies are rejected (validation)
  - Data model rejects out-of-range scores (edge)
  - DELETE convergence-guard is safe when no guard exists (edge)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


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


@pytest.mark.asyncio
async def test_self_balancing_get_health_returns_spec_snapshot_fields(client):
    """Happy path: stable snapshot schema for self-balancing diagnostics (spec-172)."""
    response = await client.get("/api/graph/health")
    assert response.status_code == 200, response.text
    data = response.json()

    required = (
        "balance_score",
        "entropy_score",
        "concentration_ratio",
        "gravity_wells",
        "orphan_clusters",
        "surface_candidates",
        "signals",
        "computed_at",
    )
    for key in required:
        assert key in data, f"missing {key}"

    assert 0.0 <= data["balance_score"] <= 1.0
    assert 0.0 <= data["entropy_score"] <= 1.0
    assert 0.0 <= data["concentration_ratio"] <= 1.0
    assert isinstance(data["gravity_wells"], list)
    assert isinstance(data["orphan_clusters"], list)
    assert isinstance(data["surface_candidates"], list)
    assert isinstance(data["signals"], list)


@pytest.mark.asyncio
async def test_self_balancing_compute_empty_graph_returns_zeros_without_error(monkeypatch, client):
    """Happy path: empty concept graph yields zeroed metrics and empty advisory lists (no failure)."""
    import app.services.concept_service as cs
    import app.services.graph_health_service as svc

    monkeypatch.setattr(cs, "_concepts", [])
    monkeypatch.setattr(cs, "_edges", [])
    monkeypatch.setattr(cs, "_concept_index", {})
    monkeypatch.setattr(svc, "_last_compute_time", None)

    response = await client.post("/api/graph/health/compute")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["balance_score"] == 0.0
    assert body["entropy_score"] == 0.0
    assert body["concentration_ratio"] == 0.0
    assert body["gravity_wells"] == []
    assert body["orphan_clusters"] == []
    assert body["surface_candidates"] == []
    assert body["signals"] == []


@pytest.mark.asyncio
async def test_self_balancing_convergence_guard_missing_body_returns_422(client):
    """Edge/error: convergence guard requires JSON body with reason and set_by."""
    response = await client.post(
        "/api/graph/concepts/c-1/convergence-guard",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_self_balancing_delete_guard_when_none_present_returns_200(client):
    """Edge: deleting a guard for a concept that never had one still succeeds (advisory, idempotent)."""
    response = await client.delete("/api/graph/concepts/unknown-concept/convergence-guard")
    assert response.status_code == 200
    data = response.json()
    assert data["concept_id"] == "unknown-concept"
    assert data["convergence_guard"] is False


def test_self_balancing_graph_health_snapshot_rejects_out_of_range_scores():
    """Edge: Pydantic model enforces [0, 1] bounds for balance / entropy (anti-collapse metrics)."""
    from app.models.graph_health import GraphHealthSnapshot

    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        GraphHealthSnapshot(
            balance_score=1.5,
            entropy_score=0.5,
            concentration_ratio=0.5,
            gravity_wells=[],
            orphan_clusters=[],
            surface_candidates=[],
            signals=[],
            computed_at=now,
        )
