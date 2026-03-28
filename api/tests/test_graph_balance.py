"""Tests for graph self-balance / fractal equilibrium (Spec 170)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_balance_service, graph_service


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_graph_balance_empty_graph():
    """Balance report succeeds with empty or sparse graph."""
    r = graph_balance_service.compute_balance_report()
    assert r.entropy.total_ideas >= 0
    assert r.entropy.total_energy >= 0
    assert 0.0 <= r.entropy.top3_energy_share <= 1.0
    assert isinstance(r.split_signals, list)
    assert isinstance(r.merge_suggestions, list)


@pytest.mark.asyncio
async def test_graph_balance_api_returns_shape():
    """GET /api/graph/balance returns required keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/graph/balance")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "split_signals" in data
    assert "merge_suggestions" in data
    assert "entropy" in data
    assert "parameters" in data
    assert "concentration_alert" in data["entropy"]


@pytest.mark.asyncio
async def test_split_signal_when_many_children():
    """Parent with >= max_children parent-of edges appears in split_signals."""
    root = _uid("root")
    graph_service.create_node(
        id=root,
        type="concept",
        name="Heavy Parent",
        description="",
        properties={},
        strict=True,
    )
    for i in range(10):
        child = _uid("ch")
        graph_service.create_node(
            id=child,
            type="concept",
            name=f"Child {i}",
            description="",
            properties={},
            strict=True,
        )
        graph_service.create_edge(
            from_id=root,
            to_id=child,
            type="parent-of",
            strict=True,
        )
    r = graph_balance_service.compute_balance_report(max_children=10)
    ids = {s.node_id for s in r.split_signals}
    assert root in ids


@pytest.mark.asyncio
async def test_merge_suggestion_orphan_cluster():
    """Two orphan ideas linked by an edge produce a merge suggestion."""
    a = _uid("oa")
    b = _uid("ob")
    graph_service.create_node(
        id=a, type="idea", name="Orphan A", description="", properties={}, strict=True,
    )
    graph_service.create_node(
        id=b, type="idea", name="Orphan B", description="", properties={}, strict=True,
    )
    graph_service.create_edge(from_id=a, to_id=b, type="analogous-to", strict=True)
    r = graph_balance_service.compute_balance_report()
    found = any(set(s.node_ids) == {a, b} for s in r.merge_suggestions)
    assert found


def test_entropy_concentration_neglected_deterministic():
    """Top-3 energy dominance triggers alert; high-potential non-top ideas surface."""
    ideas = [
        {"id": "a", "name": "A", "free_energy_score": 100, "value_gap": 0.1, "roi_cc": 1.0},
        {"id": "b", "name": "B", "free_energy_score": 100, "value_gap": 0.1, "roi_cc": 1.0},
        {"id": "c", "name": "C", "free_energy_score": 100, "value_gap": 0.1, "roi_cc": 1.0},
        {"id": "d", "name": "D", "free_energy_score": 1, "value_gap": 50.0, "roi_cc": 1.0},
    ]
    r = graph_balance_service.compute_entropy_report(ideas, concentration_threshold=0.75)
    assert r.concentration_alert is True
    assert any(nb.idea_id == "d" for nb in r.neglected_branches)
