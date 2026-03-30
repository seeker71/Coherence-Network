from __future__ import annotations

from decimal import Decimal

from app.services.contribution_cost_service import estimate_commit_cost, estimate_commit_cost_with_provenance


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


def test_estimate_commit_cost_with_provenance_marks_actual_when_evidence_present() -> None:
    cost, meta = estimate_commit_cost_with_provenance(
        files_changed=0,
        lines_added=0,
        submitted_cost=Decimal("7.25"),
        metadata={"invoice_id": "inv_123"},
    )
    assert cost == Decimal("7.25")
    assert meta["cost_basis"] == "actual_verified"
    assert meta["estimation_used"] is False
    assert "invoice_id" in meta["evidence_keys"]


def test_estimate_commit_cost_with_provenance_marks_shape_estimate() -> None:
    cost, meta = estimate_commit_cost_with_provenance(
        files_changed=3,
        lines_added=120,
        submitted_cost=Decimal("342.50"),
        metadata={},
    )
    assert cost == Decimal("0.79")
    assert meta["cost_basis"] == "estimated_from_change_shape"
    assert meta["estimation_used"] is True
