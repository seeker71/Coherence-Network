"""Tests for /api/utils/softmax_weights — the first LIST-returning kernel-served route.

The body runs as a Form recipe (endpoint_softmax_weights_demo.fk) through the
kernel. The source example, domain-service helper, and kernel siblings return
the SAME list of weights for the same inputs — the recipe builds the result via
the append-accumulator idiom (the kernel's value-walk now carries list
construction) and the list round-trips through value_to_py's List arm.
Element-wise CPython==Rust parity is guaranteed by parity_suite.sh.

The test verifies:
  - the route is wired and returns 200 with the list-valued shape
  - the canonical [1,2,3]@1.0 case matches the parity-suite anchor exactly,
    element by element, and the weights sum to 1.0
  - the deterministic branch (temperature 0.0) puts all weight on the max
  - the empty-scores edge returns [] (no division by zero)
  - the single-element edge returns [1.0]
  - the service helper remains element-wise identical to the recipe anchor
  - the runtime field reports which path served the request
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.idea_scoring import _softmax_weights

BASE = "http://test"

# The parity-suite anchor — scores [1,2,3] @ temperature 1.0, shifted by
# max 3.0 → weights [e^-2, e^-1, 1]/total, summing to 1.0.
CANONICAL = [0.09003057317038046, 0.24472847105479764, 0.6652409557748218]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestSoftmaxWeightsEndpoint:
    """Softmax over float scores transmuted to the first list-returning recipe."""

    @pytest.mark.anyio
    async def test_canonical_inputs_match_parity_suite(self, client: AsyncClient):
        """The default-query case [1,2,3]@1.0 matches the parity anchor element-wise."""
        res = await client.get("/api/utils/softmax_weights")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["weights"] == CANONICAL
        assert abs(sum(data["weights"]) - 1.0) < 1e-12
        assert data["scores"] == [1.0, 2.0, 3.0]
        assert data["temperature"] == 1.0
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_deterministic_temperature_zero(self, client: AsyncClient):
        """temperature 0.0 is deterministic — all weight on the max score."""
        res = await client.get(
            "/api/utils/softmax_weights",
            params={"scores": "5.0,1.0,1.0", "temperature": 0.0},
        )
        assert res.status_code == 200, res.text
        assert res.json()["weights"] == [1.0, 0.0, 0.0]

    @pytest.mark.anyio
    async def test_empty_scores_returns_empty(self, client: AsyncClient):
        """No scores → empty weight list, no division by zero."""
        res = await client.get("/api/utils/softmax_weights", params={"scores": ""})
        assert res.status_code == 200, res.text
        assert res.json()["weights"] == []

    @pytest.mark.anyio
    async def test_single_element(self, client: AsyncClient):
        """A single score gets all the weight (softmax of one is [1.0])."""
        res = await client.get("/api/utils/softmax_weights", params={"scores": "3.0"})
        assert res.status_code == 200, res.text
        assert res.json()["weights"] == [1.0]

    @pytest.mark.anyio
    async def test_arbitrary_input_matches_service_helper(self, client: AsyncClient):
        """An off-frozen input serves via binding-injection, matching the service helper."""
        res = await client.get(
            "/api/utils/softmax_weights",
            params={"scores": "0.5,0.5,2.0,1.0", "temperature": 1.0},
        )
        assert res.status_code == 200, res.text
        assert res.json()["weights"] == _softmax_weights([0.5, 0.5, 2.0, 1.0], 1.0)

    @pytest.mark.anyio
    async def test_negative_temperature_rejected(self, client: AsyncClient):
        """temperature is non-negative (ge=0.0); a negative is a 422."""
        res = await client.get(
            "/api/utils/softmax_weights", params={"temperature": -1.0}
        )
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_service_helper_agrees_with_recipe_value(self):
        """The service helper returns the same list the recipe anchor does.

        Direct element-wise parity claim without the kernel — the helper is the
        domain-service arithmetic the recipe was transmuted from.
        """
        assert _softmax_weights([1.0, 2.0, 3.0], 1.0) == CANONICAL
        assert _softmax_weights([5.0, 1.0, 1.0], 0.0) == [1.0, 0.0, 0.0]
        assert _softmax_weights([], 1.0) == []
        assert _softmax_weights([3.0], 1.0) == [1.0]
