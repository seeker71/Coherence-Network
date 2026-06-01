"""Tests for /api/utils/breath_balance — the first kernel-served route to use a transcendental native (ln).

The body runs as a Form recipe (endpoint_breath_balance_demo.fk) through
form-kernel-rust when available, with the Python fallback
vitality_service._breath_balance_py when the binary is missing. Both return
the same float for the same inputs — the recipe's operation order mirrors
the fallback exactly so they agree to the last ULP, including the -0.0 sign
on a single-phase distribution. Three-way parity (CPython, Rust, kernel-bmf)
is guaranteed by parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the canonical balanced case (1,1,1) matches the parity-suite tail value
    (0.9999999999999998 — ln(1/3)*3 vs ln(3) round-off, identical CPython↔Rust)
  - the log-of-zero guard: a single phase yields entropy 0 → balance 0.0
    (the p>0 guard means ln(0) is never evaluated)
  - the all-zero (total 0) guard returns 0.0
  - the fallback body is value-identical to the kernel result element-by-case
  - the runtime field reports which path served the request
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.vitality_service import _breath_balance_py

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestBreathBalanceEndpoint:
    """Normalized Shannon entropy transmuted to a Form recipe using ln."""

    @pytest.mark.anyio
    async def test_canonical_inputs_match_parity_suite(self, client: AsyncClient):
        """The default-query case (1,1,1) matches the parity-suite tail value."""
        res = await client.get("/api/utils/breath_balance")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["balance"] == 0.9999999999999998
        assert data["gas"] == 1 and data["water"] == 1 and data["ice"] == 1
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_single_phase_is_log_of_zero_guarded(self, client: AsyncClient):
        """A single nonzero phase has entropy 0 → balance 0.0, with ln(0) never hit.

        The p>0 guard skips the undefined ln(0) term; only the one nonzero
        proportion (p=1.0, ln(1.0)=0.0) contributes, so H=0 and balance=0.0
        (signed -0.0 in IEEE, which compares == 0.0).
        """
        res = await client.get("/api/utils/breath_balance", params={"gas": 5, "water": 0, "ice": 0})
        assert res.status_code == 200, res.text
        assert res.json()["balance"] == 0.0

    @pytest.mark.anyio
    async def test_all_zero_returns_zero(self, client: AsyncClient):
        """Total 0 (no phases) returns 0.0 — nothing to balance."""
        res = await client.get("/api/utils/breath_balance", params={"gas": 0, "water": 0, "ice": 0})
        assert res.status_code == 200, res.text
        assert res.json()["balance"] == 0.0

    @pytest.mark.anyio
    async def test_skewed_distribution(self, client: AsyncClient):
        """A skewed mix returns the recipe's value, matching the fallback exactly."""
        res = await client.get("/api/utils/breath_balance", params={"gas": 10, "water": 3, "ice": 1})
        assert res.status_code == 200, res.text
        assert res.json()["balance"] == _breath_balance_py(10, 3, 1)

    @pytest.mark.anyio
    async def test_negative_count_rejected(self, client: AsyncClient):
        """Phase counts are non-negative (ge=0); a negative is a 422."""
        res = await client.get("/api/utils/breath_balance", params={"gas": -1})
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_fallback_agrees_with_recipe_value(self):
        """The Python fallback returns the same float the recipe does.

        Direct parity claim without the kernel — the fallback's operation
        order mirrors the .fk so kernel and fallback never diverge.
        """
        assert _breath_balance_py(1, 1, 1) == 0.9999999999999998
        assert _breath_balance_py(5, 0, 0) == 0.0  # -0.0 == 0.0
        assert _breath_balance_py(0, 0, 0) == 0.0
