"""Tests for contribution_cost_service (spec: normalize-github-commit-cost-estimation).

The service replaces an inflated per-commit cost estimator with a bounded
normalized model. Two pure functions:

  estimate_commit_cost(files_changed, lines_added, submitted_cost?) -> Decimal
  estimate_commit_cost_with_provenance(...) -> (Decimal, provenance dict)

These tests cover the spec's named requirements:

  - Normalized formula: BASE + PER_FILE*files + PER_LINE*lines
  - Bounded range [MIN_COMMIT_COST, MAX_COMMIT_COST]
  - Submitted cost retained as fallback when commit-shape metadata is absent
  - Provenance distinguishes actual_verified / estimated_from_change_shape /
    estimated_from_submitted_cost / estimated_minimum_default

Pure-function tests; no fixtures, no monkeypatch.
"""
from __future__ import annotations

from decimal import Decimal

from app.services.contribution_cost_service import (
    BASE_COST,
    MAX_COMMIT_COST,
    MIN_COMMIT_COST,
    PER_FILE_COST,
    PER_LINE_COST,
    estimate_commit_cost,
    estimate_commit_cost_with_provenance,
)


# ---------------------------------------------------------------------------
# estimate_commit_cost
# ---------------------------------------------------------------------------


def test_estimate_applies_normalized_formula_from_files_and_lines():
    """A small commit: 2 files + 50 lines → BASE + 2*PER_FILE + 50*PER_LINE."""
    cost = estimate_commit_cost(files_changed=2, lines_added=50, submitted_cost=None)
    expected = BASE_COST + (Decimal(2) * PER_FILE_COST) + (Decimal(50) * PER_LINE_COST)
    # _clamp_cost quantizes to two decimal places with ROUND_HALF_UP.
    assert cost == expected.quantize(Decimal("0.01"))


def test_estimate_clamps_to_max_for_large_commits():
    """A massive commit (10000 lines) gets clamped to MAX_COMMIT_COST, not exploded."""
    cost = estimate_commit_cost(files_changed=100, lines_added=10000, submitted_cost=None)
    assert cost == MAX_COMMIT_COST


def test_estimate_clamps_to_min_for_trivial_commits():
    """A 1-file 0-line commit lands at MIN_COMMIT_COST (formula yields below floor)."""
    # BASE 0.10 + 1*0.15 + 0*0.002 = 0.25 — above the 0.05 floor, so floor doesn't bite here.
    # To exercise the floor, use the submitted-cost fallback with a tiny value.
    cost = estimate_commit_cost(
        files_changed=0,
        lines_added=0,
        submitted_cost=Decimal("0.001"),
    )
    assert cost == MIN_COMMIT_COST


def test_estimate_falls_back_to_submitted_cost_when_no_shape_metadata():
    """No files/lines → use submitted cost (clamped)."""
    cost = estimate_commit_cost(
        files_changed=0,
        lines_added=0,
        submitted_cost=Decimal("3.50"),
    )
    assert cost == Decimal("3.50")


def test_estimate_returns_minimum_when_no_inputs():
    """Empty inputs → MIN_COMMIT_COST (graceful default)."""
    cost = estimate_commit_cost(files_changed=0, lines_added=0, submitted_cost=None)
    assert cost == MIN_COMMIT_COST


def test_estimate_treats_negative_or_garbage_as_zero():
    """Non-numeric or negative inputs collapse to 0 — no crash, predictable behavior."""
    cost = estimate_commit_cost(
        files_changed=-5,
        lines_added="not-a-number",
        submitted_cost=Decimal("2.00"),
    )
    # Negatives → 0, garbage → 0; no commit-shape metadata, so submitted_cost is used.
    assert cost == Decimal("2.00")


# ---------------------------------------------------------------------------
# estimate_commit_cost_with_provenance
# ---------------------------------------------------------------------------


def test_provenance_actual_verified_when_evidence_key_present():
    """Invoice or receipt evidence → cost_basis=actual_verified, confidence 1.0."""
    cost, prov = estimate_commit_cost_with_provenance(
        files_changed=10,
        lines_added=500,
        submitted_cost=Decimal("4.25"),
        metadata={"invoice_id": "INV-001"},
    )
    assert cost == Decimal("4.25")
    assert prov["cost_basis"] == "actual_verified"
    assert prov["cost_confidence"] == 1.0
    assert prov["estimation_used"] is False
    assert prov["evidence_keys"] == ["invoice_id"]


def test_provenance_estimated_from_change_shape_when_files_and_lines():
    """Files+lines present and no evidence → estimated_from_change_shape, confidence 0.75."""
    cost, prov = estimate_commit_cost_with_provenance(
        files_changed=3,
        lines_added=80,
        submitted_cost=None,
        metadata={},
    )
    assert prov["cost_basis"] == "estimated_from_change_shape"
    assert prov["cost_confidence"] == 0.75
    assert prov["estimation_used"] is True
    assert prov["files_changed"] == 3
    assert prov["lines_added"] == 80


def test_provenance_change_shape_lower_confidence_with_partial_metadata():
    """Files-only (no lines) → confidence drops to 0.65 (partial shape)."""
    _cost, prov = estimate_commit_cost_with_provenance(
        files_changed=2,
        lines_added=0,
        submitted_cost=None,
        metadata={},
    )
    assert prov["cost_basis"] == "estimated_from_change_shape"
    assert prov["cost_confidence"] == 0.65


def test_provenance_estimated_from_submitted_when_only_submitted_given():
    """No shape, no evidence, just a submitted cost → confidence 0.4."""
    cost, prov = estimate_commit_cost_with_provenance(
        files_changed=0,
        lines_added=0,
        submitted_cost=Decimal("1.50"),
        metadata={},
    )
    assert cost == Decimal("1.50")
    assert prov["cost_basis"] == "estimated_from_submitted_cost"
    assert prov["cost_confidence"] == 0.4
    assert prov["estimation_used"] is True


def test_provenance_minimum_default_when_nothing_given():
    """No inputs at all → cost_basis=estimated_minimum_default, confidence 0.1."""
    cost, prov = estimate_commit_cost_with_provenance(
        files_changed=0,
        lines_added=0,
        submitted_cost=None,
        metadata=None,
    )
    assert cost == MIN_COMMIT_COST
    assert prov["cost_basis"] == "estimated_minimum_default"
    assert prov["cost_confidence"] == 0.1


def test_provenance_evidence_without_submitted_cost_falls_through_to_shape():
    """Evidence key present but no submitted_cost → fall through to change-shape estimation."""
    _cost, prov = estimate_commit_cost_with_provenance(
        files_changed=4,
        lines_added=120,
        submitted_cost=None,
        metadata={"receipt_id": "RCPT-9"},
    )
    # actual_verified requires BOTH evidence and submitted_cost; without cost, we estimate.
    assert prov["cost_basis"] == "estimated_from_change_shape"
    assert prov["estimation_used"] is True
