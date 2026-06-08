"""Tests for /api/utils/weighted_average — transmuted under the habit pattern.

The body of this endpoint runs as a Form recipe through the kernel. The source
example and kernel siblings return the same float for the same inputs — guaranteed by
form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the float matches the parity-suite tail value (0.8125) for the canonical
    inputs (values=[0.5,0.75,1.0], weights=[0.25,0.25,0.5])
  - the runtime field reports which path served the request
  - mismatched lengths return 400
  - empty / zero-sum weights return 400
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


class TestWeightedAverageEndpoint:
    """Float-arithmetic combinator transmuted to a Form recipe."""

    @pytest.mark.anyio
    async def test_canonical_inputs_match_parity_suite(self, client: AsyncClient):
        """The default-query case matches endpoint_weighted_average_demo.py — 0.8125."""
        res = await client.get("/api/utils/weighted_average")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["average"] == 0.8125
        assert data["values"] == [0.5, 0.75, 1.0]
        assert data["weights"] == [0.25, 0.25, 0.5]
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_equal_weights_is_arithmetic_mean(self, client: AsyncClient):
        """Equal weights → ordinary arithmetic mean."""
        res = await client.get(
            "/api/utils/weighted_average",
            params={"values": "0.25,0.5,0.75", "weights": "1.0,1.0,1.0"},
        )
        assert res.status_code == 200, res.text
        # (0.25+0.5+0.75)/3 = 0.5
        assert res.json()["average"] == 0.5

    @pytest.mark.anyio
    async def test_mismatched_lengths_returns_400(self, client: AsyncClient):
        res = await client.get(
            "/api/utils/weighted_average",
            params={"values": "0.5,0.5", "weights": "1.0,1.0,1.0"},
        )
        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_zero_weights_returns_400(self, client: AsyncClient):
        res = await client.get(
            "/api/utils/weighted_average",
            params={"values": "0.5,0.5", "weights": "0.0,0.0"},
        )
        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_invalid_float_returns_400(self, client: AsyncClient):
        res = await client.get(
            "/api/utils/weighted_average",
            params={"values": "0.5,abc", "weights": "1.0,1.0"},
        )
        assert res.status_code == 400
