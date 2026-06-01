"""Tests for /api/utils/shannon_entropy — normalized Shannon entropy as a Form recipe.

The body runs as a Form recipe (endpoint_shannon_entropy_demo.fk) through
form-kernel-rust when available, with the Python fallback
breath_service._shannon_entropy_normalized when the binary is missing. Both
return the same float for the same inputs. Distinct from breath_balance: the
per-term accumulator SUBTRACTS (so a single nonzero phase yields +0.0, not
breath_balance's -0.0), the result is wrapped in round(_, 4), and the empty
guard is `total == 0`. Folds two natives into one recipe — math.log (ln) and
round_ndigits (CPython-exact round). Three-way parity (CPython, Rust,
kernel-bmf) is guaranteed by parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the canonical balanced case (1,1,1) is round(1.0, 4) = 1.0
  - the log-of-zero guard: a single phase yields entropy 0 → 0.0 (ln(0) never hit)
  - the all-zero (total 0) guard returns 0.0
  - a skewed distribution matches the fallback exactly
  - the runtime field reports which path served the request
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.breath_service import _shannon_entropy_normalized

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestShannonEntropyEndpoint:
    """Normalized Shannon entropy transmuted to a Form recipe (ln + round natives)."""

    @pytest.mark.anyio
    async def test_canonical_inputs_balanced(self, client: AsyncClient):
        """The default-query case (1,1,1) — equal thirds, H = ln(3) = H_max, round(1.0, 4) = 1.0."""
        res = await client.get("/api/utils/shannon_entropy")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["entropy"] == 1.0
        assert data["gas"] == 1 and data["water"] == 1 and data["ice"] == 1
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_single_phase_is_log_of_zero_guarded(self, client: AsyncClient):
        """A single nonzero phase has entropy 0 → 0.0, with ln(0) never hit.

        The count>0 guard skips the undefined ln(0) terms; only the one nonzero
        proportion (p=1.0, ln(1.0)=0.0) contributes, so H=0 and entropy=0.0.
        """
        res = await client.get("/api/utils/shannon_entropy", params={"gas": 5, "water": 0, "ice": 0})
        assert res.status_code == 200, res.text
        assert res.json()["entropy"] == 0.0

    @pytest.mark.anyio
    async def test_all_zero_returns_zero(self, client: AsyncClient):
        """Total 0 (no phases) returns 0.0 — nothing to measure."""
        res = await client.get("/api/utils/shannon_entropy", params={"gas": 0, "water": 0, "ice": 0})
        assert res.status_code == 200, res.text
        assert res.json()["entropy"] == 0.0

    @pytest.mark.anyio
    async def test_skewed_distribution_matches_fallback(self, client: AsyncClient):
        """A skewed mix returns the recipe's value, matching the fallback exactly."""
        res = await client.get("/api/utils/shannon_entropy", params={"gas": 10, "water": 5, "ice": 1})
        assert res.status_code == 200, res.text
        assert res.json()["entropy"] == _shannon_entropy_normalized(10, 5, 1)

    @pytest.mark.anyio
    async def test_negative_count_rejected(self, client: AsyncClient):
        """Phase counts are non-negative (ge=0); a negative is a 422."""
        res = await client.get("/api/utils/shannon_entropy", params={"gas": -1})
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_fallback_agrees_with_recipe_value(self):
        """The Python fallback returns the same float the recipe does.

        Direct parity claim without the kernel — the fallback's operation
        order mirrors the .fk so kernel and fallback never diverge.
        """
        assert _shannon_entropy_normalized(1, 1, 1) == 1.0
        assert _shannon_entropy_normalized(5, 0, 0) == 0.0
        assert _shannon_entropy_normalized(0, 0, 0) == 0.0
        assert _shannon_entropy_normalized(1, 2, 3) == 0.9206
