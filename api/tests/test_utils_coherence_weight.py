"""Tests for /api/utils/coherence_weight — the first transmuted endpoint.

The body of this endpoint runs as a Form recipe through a Form-kernel carrier.
The canonical source example and kernel siblings return the same integer for the
same inputs — guaranteed by form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the expected shape
  - the integer matches the parity-suite tail value (16185) for the
    canonical inputs
  - the runtime field reports which path served the request
  - bad input (non-integer in values) returns 400
  - empty values + any threshold returns 0
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.form_kernel_bridge import (
    inline_available,
    kernel_available,
    load_recipe,
)

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestCoherenceWeightEndpoint:
    """The route's body is a Form recipe; this test confirms the gesture."""

    @pytest.mark.anyio
    async def test_canonical_inputs_match_parity_suite(self, client: AsyncClient):
        """The default-query case matches endpoint_coherence_weight_demo.py — 16185."""
        res = await client.get("/api/utils/coherence_weight")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["weight"] == 16185
        assert data["threshold"] == 50
        assert data["values"] == [72, 38, 91, 55, 28, 67, 84, 45, 95, 12]
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_custom_inputs(self, client: AsyncClient):
        """Custom values + threshold still pass through the kernel."""
        res = await client.get(
            "/api/utils/coherence_weight",
            params={"values": "10,20,30,40,50", "threshold": 25},
        )
        assert res.status_code == 200, res.text
        # Above-threshold: 30, 40, 50 (positions 0,1,2)
        # weighted: 30*100 + 40*50 + 50*25 = 3000 + 2000 + 1250 = 6250
        # count_above = 3 → bonus = 300
        # total = 300 + 6250 = 6550
        assert res.json()["weight"] == 6550

    @pytest.mark.anyio
    async def test_empty_values_returns_zero(self, client: AsyncClient):
        res = await client.get(
            "/api/utils/coherence_weight",
            params={"values": "", "threshold": 0},
        )
        assert res.status_code == 200, res.text
        assert res.json()["weight"] == 0

    @pytest.mark.anyio
    async def test_invalid_integer_returns_400(self, client: AsyncClient):
        res = await client.get(
            "/api/utils/coherence_weight",
            params={"values": "1,2,abc", "threshold": 0},
        )
        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_recipe_resolves_so_image_serves_kernel_side(self):
        """The endpoint's .fk resolves on disk — the kernel-served precondition.

        The prod regression this guards: the kernel is present (inline PyO3 or
        the binary) but the recipe .fk is absent from the image. That must now
        fail loudly rather than silently executing Python. CI may have no kernel
        built, so we assert the recipe FILE resolves (the part that fails when
        an image drops the .fk) rather than requiring the kernel.
        """
        # Does not raise FileNotFoundError → the recipe is where the bridge looks.
        source = load_recipe("endpoint_coherence_weight_demo.fk")
        assert source.strip().startswith("(do"), "recipe is a (do ...) form"

    @pytest.mark.anyio
    async def test_when_kernel_present_endpoint_is_kernel_served(
        self, client: AsyncClient
    ):
        """When a kernel is reachable AND the recipe resolves, serve kernel-side.

        This is the direct guard for the production gap that motivated the fix:
        kernel loaded (/api/health shows inline) but endpoints served
        Python because the recipe was missing from the image. If no kernel is
        built in this env, the precondition is absent and we skip — the
        test_recipe_resolves test above still catches the missing-recipe
        regression without a kernel.
        """
        if not (inline_available() or kernel_available()):
            pytest.skip("no kernel reachable in this env — recipe-resolution test covers it")
        res = await client.get("/api/utils/coherence_weight")
        assert res.status_code == 200, res.text
        runtime = res.json()["runtime"]
        assert runtime in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_kernel_status_visibility(self, client: AsyncClient):
        """The status endpoint reports which path will serve requests."""
        res = await client.get("/api/utils/kernel_status")
        assert res.status_code == 200, res.text
        data = res.json()
        assert "available" in data
        assert "binary_path" in data
        assert isinstance(data["available"], bool)
