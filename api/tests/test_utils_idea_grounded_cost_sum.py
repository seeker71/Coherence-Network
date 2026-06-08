"""Tests for /api/utils/idea_grounded_cost_sum — the float-field list-of-record reduction.

The body runs as a Form recipe (endpoint_idea_grounded_cost_sum_demo.fk) that
receives one idea's pre-fetched specs as a LIST OF RECORDS and FOLDS two FLOAT
grounding sums across it: spec_actual_cost_sum, spec_actual_value_sum. This is
the float-field fold the integer idea_grounding_summary route named as deferred —
it was blocked by TS's i32-only add/_plus, which the float-add sibling-parity fix
opened. The accumulator seeds at 0.0 so every add walks (float, float).

Three-way parity of the recipe body (CPython, kernel-bmf, Rust) is the
parity_suite gate; these tests verify the route is wired, returns the float pair,
and matches the documented recipe anchors over the real reduction.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestIdeaGroundedCostSumEndpoint:
    """Float grounding sums folded over a list of spec records."""

    @pytest.mark.anyio
    async def test_canonical_specs(self, client: AsyncClient):
        """The default three specs fold to cost 5.25, value 3.75 (non-integer floats)."""
        res = await client.get("/api/utils/idea_grounded_cost_sum")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_actual_cost_sum"] == 5.25
        assert data["spec_actual_value_sum"] == 3.75
        assert data["spec_count_in"] == 3
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_distinct_specs_match_parity_reference(self, client: AsyncClient):
        """A distinct spec list returns the recipe's float reduction, matching the parity reference."""
        params = {"actual_costs": "2.5,0.25,1.0", "actual_values": "0.5,0.0,3.25"}
        res = await client.get("/api/utils/idea_grounded_cost_sum", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert [data["spec_actual_cost_sum"], data["spec_actual_value_sum"]] == [3.75, 3.75]

    @pytest.mark.anyio
    async def test_empty_specs_fold_to_zero(self, client: AsyncClient):
        """An empty spec list folds to [0.0, 0.0] — the float identity accumulators."""
        params = {"actual_costs": "", "actual_values": ""}
        res = await client.get("/api/utils/idea_grounded_cost_sum", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_actual_cost_sum"] == 0.0
        assert data["spec_actual_value_sum"] == 0.0

    @pytest.mark.anyio
    async def test_mismatched_lengths_rejected(self, client: AsyncClient):
        """actual_costs and actual_values of different lengths is a 422."""
        params = {"actual_costs": "1.0,2.0,3.0", "actual_values": "1.0"}
        res = await client.get("/api/utils/idea_grounded_cost_sum", params=params)
        assert res.status_code == 422
