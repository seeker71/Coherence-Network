"""Tests for the distribution engine (spec: distribution-engine).

Validates the core algorithm and three edge cases the spec names:

  R2/R3 — payout proportional to cost_amount × (0.5 + coherence_score)
  R4    — zero contributions → empty payout list
  R5    — zero weighted cost → empty payout list
  R6    — payouts rounded to 2 decimal places, ROUND_HALF_UP

The engine reads contribution edges from the graph service; we
monkeypatch graph_service.get_edges to return controlled inputs so
the algorithm is tested in isolation from graph state.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.services import graph_service
from app.services.distribution_engine import DistributionEngine


def _edge(contributor_id, cost_amount, coherence_score):
    """Build a graph edge dict shaped like the engine expects."""
    return {
        "properties": {
            "contributor_id": str(contributor_id),
            "cost_amount": str(cost_amount),
            "coherence_score": coherence_score,
        }
    }


@pytest.mark.asyncio
async def test_distribute_weights_by_cost_and_coherence(monkeypatch):
    """Two contributors with equal cost but different coherence get different shares.

    contributor_a: cost=100, coherence=0.5 → weight = 1.0   → weighted_cost = 100
    contributor_b: cost=100, coherence=1.0 → weight = 1.5   → weighted_cost = 150
    total_weighted = 250; value_amount = 100.00
    contributor_a payout = (100 / 250) × 100 = 40.00
    contributor_b payout = (150 / 250) × 100 = 60.00
    """
    asset_id = uuid4()
    asset_node_id = f"asset:{asset_id}"
    a, b = uuid4(), uuid4()

    monkeypatch.setattr(
        graph_service,
        "get_edges",
        lambda node_id, direction, edge_type: [
            _edge(a, "100", 0.5),
            _edge(b, "100", 1.0),
        ],
    )

    distribution = await DistributionEngine().distribute(
        asset_id=asset_id,
        asset_node_id=asset_node_id,
        value_amount=Decimal("100.00"),
    )

    payouts = {p.contributor_id: p.amount for p in distribution.payouts}
    assert payouts[a] == Decimal("40.00")
    assert payouts[b] == Decimal("60.00")
    assert distribution.asset_id == asset_id
    assert distribution.value_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_distribute_zero_contributions_returns_empty_payouts(monkeypatch):
    """R4 — no contribution edges → Distribution with empty payouts."""
    asset_id = uuid4()
    monkeypatch.setattr(graph_service, "get_edges", lambda *a, **k: [])

    distribution = await DistributionEngine().distribute(
        asset_id=asset_id,
        asset_node_id=f"asset:{asset_id}",
        value_amount=Decimal("100.00"),
    )

    assert distribution.payouts == []
    assert distribution.value_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_distribute_zero_weighted_cost_returns_empty_payouts(monkeypatch):
    """R5 — contributions exist but all have cost=0 → no positive weighted cost → empty payouts."""
    asset_id = uuid4()
    a = uuid4()

    monkeypatch.setattr(
        graph_service,
        "get_edges",
        lambda *args, **kw: [_edge(a, "0", 0.8)],
    )

    distribution = await DistributionEngine().distribute(
        asset_id=asset_id,
        asset_node_id=f"asset:{asset_id}",
        value_amount=Decimal("100.00"),
    )

    assert distribution.payouts == []


@pytest.mark.asyncio
async def test_distribute_rounds_half_up_to_two_decimals(monkeypatch):
    """R6 — payout amounts rounded to 2 decimals with ROUND_HALF_UP.

    Pick inputs that produce a .005 third digit so ROUND_HALF_UP actually
    fires (rounding up rather than truncating). Two equal contributors
    splitting 33.33 → each gets 16.665 → ROUND_HALF_UP → 16.67.
    """
    asset_id = uuid4()
    a, b = uuid4(), uuid4()

    monkeypatch.setattr(
        graph_service,
        "get_edges",
        lambda *args, **kw: [
            _edge(a, "100", 0.5),
            _edge(b, "100", 0.5),
        ],
    )

    distribution = await DistributionEngine().distribute(
        asset_id=asset_id,
        asset_node_id=f"asset:{asset_id}",
        value_amount=Decimal("33.33"),
    )

    amounts = sorted(p.amount for p in distribution.payouts)
    # 16.665 → ROUND_HALF_UP → 16.67 for both.
    assert amounts == [Decimal("16.67"), Decimal("16.67")]
    # All amounts have exactly 2 decimal places (Decimal exponent -2).
    for amount in amounts:
        assert amount.as_tuple().exponent == -2


@pytest.mark.asyncio
async def test_distribute_skips_edges_with_no_contributor_id(monkeypatch):
    """Edges without contributor_id are dropped silently; the engine continues.

    Defends against malformed graph data without crashing distribution.
    """
    asset_id = uuid4()
    a = uuid4()

    monkeypatch.setattr(
        graph_service,
        "get_edges",
        lambda *args, **kw: [
            {"properties": {"cost_amount": "50", "coherence_score": 0.5}},  # missing contributor_id
            _edge(a, "100", 0.5),
        ],
    )

    distribution = await DistributionEngine().distribute(
        asset_id=asset_id,
        asset_node_id=f"asset:{asset_id}",
        value_amount=Decimal("100.00"),
    )

    # Only the well-formed edge contributed; that contributor gets the whole pool.
    assert len(distribution.payouts) == 1
    assert distribution.payouts[0].contributor_id == a
    assert distribution.payouts[0].amount == Decimal("100.00")
