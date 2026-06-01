"""Tests for /api/utils/idea_marginal_from_record — the first structure-access route.

The body runs as a Form recipe (endpoint_idea_marginal_from_record_demo.fk)
that receives the idea as a structured object (a kernel Record marshalled from a
Python dict) and reads its six fields by name, rather than receiving them as
separate scalar bindings. Same arithmetic as marginal_cc_return; the new
capability is field extraction from a record binding. Three-way parity of the
recipe body (CPython, kernel-bmf, Rust) is the parity_suite gate; the bridge
marshalling is covered by test_form_kernel_bridge_structure_access.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the canonical frozen idea computes round((5*0.64)/(3+1), 6) = 0.8
  - the idea object is echoed back
  - a second distinct idea matches the Python computation exactly
  - the runtime field reports which path served the request
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers.utils import _marginal_from_idea_py

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestIdeaMarginalFromRecordEndpoint:
    """Marginal CC return read from a structured record — structure access."""

    @pytest.mark.anyio
    async def test_canonical_idea(self, client: AsyncClient):
        """The default frozen idea computes round((5*0.64)/(3+1), 6) = 0.8."""
        res = await client.get("/api/utils/idea_marginal_from_record")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["marginal_return"] == 0.8
        assert data["idea"]["potential_value"] == 8.0
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_distinct_idea_matches_fallback(self, client: AsyncClient):
        """A distinct idea returns the recipe's value, matching the fallback exactly."""
        params = {"pv": 10.0, "av": 2.0, "conf": 0.9, "ec": 6.0, "ac": 1.0, "rr": 1.0}
        res = await client.get("/api/utils/idea_marginal_from_record", params=params)
        assert res.status_code == 200, res.text
        expected = _marginal_from_idea_py(
            {
                "potential_value": 10.0,
                "actual_value": 2.0,
                "confidence": 0.9,
                "estimated_cost": 6.0,
                "actual_cost": 1.0,
                "resistance_risk": 1.0,
            }
        )
        assert res.json()["marginal_return"] == expected

    @pytest.mark.anyio
    async def test_value_gap_floor(self, client: AsyncClient):
        """When actual_value exceeds potential_value the gap floors at 0 → 0.0 return."""
        params = {"pv": 1.0, "av": 5.0, "conf": 0.8, "ec": 4.0, "ac": 1.0, "rr": 2.0}
        res = await client.get("/api/utils/idea_marginal_from_record", params=params)
        assert res.status_code == 200, res.text
        assert res.json()["marginal_return"] == 0.0
