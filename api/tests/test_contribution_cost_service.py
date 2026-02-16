from __future__ import annotations

from decimal import Decimal

from app.services.contribution_cost_service import estimate_commit_cost


def test_estimate_commit_cost_uses_metadata_formula() -> None:
    cost = estimate_commit_cost(files_changed=3, lines_added=120, submitted_cost=Decimal("342.50"))
    assert cost == Decimal("0.79")


def test_estimate_commit_cost_clamps_large_metadata() -> None:
    cost = estimate_commit_cost(files_changed=200, lines_added=50000, submitted_cost=Decimal("1.00"))
    assert cost == Decimal("10.00")


def test_estimate_commit_cost_falls_back_to_submitted_when_metadata_missing() -> None:
    cost = estimate_commit_cost(files_changed=0, lines_added=0, submitted_cost=Decimal("7.25"))
    assert cost == Decimal("7.25")


def test_estimate_commit_cost_clamps_submitted_when_metadata_missing() -> None:
    cost = estimate_commit_cost(files_changed=None, lines_added=None, submitted_cost=Decimal("342.50"))
    assert cost == Decimal("10.00")
