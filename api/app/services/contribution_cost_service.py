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
