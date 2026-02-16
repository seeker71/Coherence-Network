from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# Cost model v2 (normalized):
# - keep commit costs comparable and bounded
# - avoid line-count explosions from large commits
BASE_COST = Decimal("0.10")
PER_FILE_COST = Decimal("0.15")
PER_LINE_COST = Decimal("0.002")
MIN_COMMIT_COST = Decimal("0.05")
MAX_COMMIT_COST = Decimal("10.00")
ESTIMATOR_VERSION = "v2_normalized"
ACTUAL_VERIFICATION_KEYS = (
    "invoice_id",
    "receipt_id",
    "billing_reference",
    "payment_tx_hash",
    "cost_evidence_url",
    "vendor_invoice_id",
)


def _to_non_negative_int(value: Any) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, out)


def _clamp_cost(value: Decimal) -> Decimal:
    clamped = max(MIN_COMMIT_COST, min(MAX_COMMIT_COST, value))
    return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def estimate_commit_cost(
    *,
    files_changed: Any,
    lines_added: Any,
    submitted_cost: Decimal | None = None,
) -> Decimal:
    """Return normalized cost for a commit.

    Preference order:
    1. If commit-shape metadata exists, use normalized formula from files/lines.
    2. Otherwise, fallback to submitted cost (clamped).
    3. If no usable inputs, return minimum cost.
    """
    files = _to_non_negative_int(files_changed)
    lines = _to_non_negative_int(lines_added)

    if files > 0 or lines > 0:
        estimated = BASE_COST + (Decimal(files) * PER_FILE_COST) + (Decimal(lines) * PER_LINE_COST)
        return _clamp_cost(estimated)

    if submitted_cost is not None:
        return _clamp_cost(Decimal(submitted_cost))

    return _clamp_cost(MIN_COMMIT_COST)


def estimate_commit_cost_with_provenance(
    *,
    files_changed: Any,
    lines_added: Any,
    submitted_cost: Decimal | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[Decimal, dict[str, Any]]:
    """Return normalized commit cost plus provenance metadata.

    Preference order:
    1. If verifiable billing evidence keys are present, use submitted cost as actual (clamped).
    2. If commit-shape metadata exists, estimate from files/lines.
    3. Otherwise fallback to submitted cost (clamped estimate).
    4. If no usable inputs, minimum default estimate.
    """
    meta = metadata or {}
    files = _to_non_negative_int(files_changed)
    lines = _to_non_negative_int(lines_added)
    evidence_keys = [key for key in ACTUAL_VERIFICATION_KEYS if meta.get(key)]

    if evidence_keys and submitted_cost is not None:
        normalized = _clamp_cost(Decimal(submitted_cost))
        return normalized, {
            "cost_basis": "actual_verified",
            "cost_confidence": 1.0,
            "estimation_used": False,
            "evidence_keys": evidence_keys,
            "files_changed": files,
            "lines_added": lines,
        }

    if files > 0 or lines > 0:
        normalized = estimate_commit_cost(
            files_changed=files,
            lines_added=lines,
            submitted_cost=submitted_cost,
        )
        has_full_shape = files > 0 and lines > 0
        return normalized, {
            "cost_basis": "estimated_from_change_shape",
            "cost_confidence": 0.75 if has_full_shape else 0.65,
            "estimation_used": True,
            "evidence_keys": evidence_keys,
            "files_changed": files,
            "lines_added": lines,
        }

    if submitted_cost is not None:
        normalized = _clamp_cost(Decimal(submitted_cost))
        return normalized, {
            "cost_basis": "estimated_from_submitted_cost",
            "cost_confidence": 0.4,
            "estimation_used": True,
            "evidence_keys": evidence_keys,
            "files_changed": files,
            "lines_added": lines,
        }

    normalized = _clamp_cost(MIN_COMMIT_COST)
    return normalized, {
        "cost_basis": "estimated_minimum_default",
        "cost_confidence": 0.1,
        "estimation_used": True,
        "evidence_keys": evidence_keys,
        "files_changed": files,
        "lines_added": lines,
    }
