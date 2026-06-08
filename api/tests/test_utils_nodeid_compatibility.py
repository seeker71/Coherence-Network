"""Tests for /api/utils/nodeid_compatibility — transmuted under the habit pattern.

The body of this endpoint runs as a Form recipe through the kernel. The source
example and kernel siblings return the same integer for the same inputs — the coordinate-agreement score
0..4 between two NodeIDs (how many of package, level, type, instance match).

Sibling of test_utils_nodeid_distance: distance measures L1 separation, this
measures coordinate agreement. The test verifies the route is wired, the score
is correct, and the runtime field reports which path served.
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


class TestNodeIdCompatibilityEndpoint:
    """Pure-computation endpoint, transmuted to a Form recipe."""

    @pytest.mark.anyio
    async def test_canonical_inputs_two_match(self, client: AsyncClient):
        """Default query: NodeID(1,5,4,1) vs (1,4,4,7) — package and type match → 2."""
        res = await client.get("/api/utils/nodeid_compatibility")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["compatibility"] == 2
        assert data["a"] == [1, 5, 4, 1]
        assert data["b"] == [1, 4, 4, 7]
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_all_coordinates_match(self, client: AsyncClient):
        """Same NodeID twice → full compatibility 4."""
        res = await client.get(
            "/api/utils/nodeid_compatibility",
            params={
                "a_pkg": 1, "a_lvl": 3, "a_type": 2, "a_inst": 4,
                "b_pkg": 1, "b_lvl": 3, "b_type": 2, "b_inst": 4,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["compatibility"] == 4

    @pytest.mark.anyio
    async def test_no_coordinates_match(self, client: AsyncClient):
        """Fully disjoint NodeIDs → compatibility 0."""
        res = await client.get(
            "/api/utils/nodeid_compatibility",
            params={
                "a_pkg": 1, "a_lvl": 2, "a_type": 3, "a_inst": 4,
                "b_pkg": 5, "b_lvl": 6, "b_type": 7, "b_inst": 8,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["compatibility"] == 0
