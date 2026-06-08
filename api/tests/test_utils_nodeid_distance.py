"""Tests for /api/utils/nodeid_distance — transmuted under the habit pattern.

The body of this endpoint runs as a Form recipe through the kernel. The source
example and kernel siblings return the same integer for the same inputs — guaranteed by
form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the integer matches the parity-suite tail value (7) for the canonical
    inputs (NodeID(1,5,4,1) → NodeID(1,4,4,7), Manhattan = 7)
  - the runtime field reports which path served the request
  - the recipe returns the documented NodeID distance
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


class TestNodeIdDistanceEndpoint:
    """Pure-computation endpoint, transmuted to a Form recipe."""

    @pytest.mark.anyio
    async def test_canonical_inputs_match_parity_suite(self, client: AsyncClient):
        """The default-query case matches endpoint_nodeid_distance_demo.py — 7."""
        res = await client.get("/api/utils/nodeid_distance")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["distance"] == 7
        assert data["a"] == [1, 5, 4, 1]
        assert data["b"] == [1, 4, 4, 7]
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_zero_distance(self, client: AsyncClient):
        """Same NodeID twice → distance 0."""
        res = await client.get(
            "/api/utils/nodeid_distance",
            params={
                "a_pkg": 1, "a_lvl": 3, "a_type": 2, "a_inst": 4,
                "b_pkg": 1, "b_lvl": 3, "b_type": 2, "b_inst": 4,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["distance"] == 0

    @pytest.mark.anyio
    async def test_negative_diff_components(self, client: AsyncClient):
        """Distance uses |diff|, never goes negative."""
        # (1, 2, 3, 4) vs (5, 6, 7, 8) → |4|+|4|+|4|+|4| = 16
        res = await client.get(
            "/api/utils/nodeid_distance",
            params={
                "a_pkg": 1, "a_lvl": 2, "a_type": 3, "a_inst": 4,
                "b_pkg": 5, "b_lvl": 6, "b_type": 7, "b_inst": 8,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["distance"] == 16
