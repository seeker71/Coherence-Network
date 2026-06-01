"""Tests for /api/utils/cost_vector and /api/utils/value_vector.

The first kernel-served routes to use the round_ndigits native (CPython-exact
round(x, 4), PR #2320). Each body runs as a Form recipe
(endpoint_cost_vector_demo.fk / endpoint_value_vector_demo.fk) through
form-kernel-rust when available, with the Python fallback when the binary is
missing. Both return the SAME named components for the same input — the
recipe returns a LIST of the components in struct order and the route
assembles the named vector.

The decisive cases are the decimal inputs that EXPOSED the old round-half-up
divergence: the half-to-even tie-break the prior shim got wrong, that
round_ndigits gets right. ec=33.333 → human_attention 8.3332 (from 8.33325),
NOT 8.3333; infrastructure 4.9999 (from 4.99995), NOT 5.0. These are the
end-to-end proof the round() unlock is correct in production.

The components must also match idea_scoring._build_cost_vector /
_build_value_vector exactly — those Python functions are the canonical body
the recipes were transmuted from, and remain the value-parity fallback.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.idea import Idea
from app.services.idea_scoring import _build_cost_vector, _build_value_vector

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _idea(ec: float = 0.0, pv: float = 0.0) -> Idea:
    return Idea(id="x", name="t", description="d", estimated_cost=ec, potential_value=pv)


class TestCostVectorEndpoint:
    """Cost-vector decomposition transmuted to a round_ndigits Form recipe."""

    @pytest.mark.anyio
    async def test_default_decimal_case_banker_rounded(self, client: AsyncClient):
        """The default ec=33.333 lands on the half-to-even tie-breaks the old
        round-half-up shim got wrong — round_ndigits gets them right."""
        res = await client.get("/api/utils/cost_vector")
        assert res.status_code == 200, res.text
        data = res.json()
        # 33.333 * 0.15 = 4.99995 → 4.9999 (NOT 5.0); * 0.25 = 8.33325 → 8.3332 (NOT 8.3333)
        assert data["compute_cc"] == 19.9998
        assert data["infrastructure_cc"] == 4.9999
        assert data["human_attention_cc"] == 8.3332
        assert data["opportunity_cc"] == 0.0
        assert data["external_cc"] == 0.0
        assert data["total_cc"] == 33.333
        assert data["estimated_cost"] == 33.333
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_zero_all_components_zero(self, client: AsyncClient):
        res = await client.get("/api/utils/cost_vector", params={"estimated_cost": 0.0})
        assert res.status_code == 200, res.text
        data = res.json()
        assert [data["compute_cc"], data["infrastructure_cc"], data["human_attention_cc"],
                data["opportunity_cc"], data["external_cc"], data["total_cc"]] == [0.0] * 6

    @pytest.mark.anyio
    async def test_integer_input(self, client: AsyncClient):
        res = await client.get("/api/utils/cost_vector", params={"estimated_cost": 100})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["compute_cc"] == 60.0
        assert data["infrastructure_cc"] == 15.0
        assert data["human_attention_cc"] == 25.0
        assert data["total_cc"] == 100.0

    @pytest.mark.anyio
    @pytest.mark.parametrize("ec", [0.0, 100.0, 33.333, 0.125, 7.7775, 9.205, 1234.5678])
    async def test_matches_service_function_per_component(self, client: AsyncClient, ec: float):
        """Every component matches idea_scoring._build_cost_vector exactly."""
        res = await client.get("/api/utils/cost_vector", params={"estimated_cost": ec})
        assert res.status_code == 200, res.text
        data = res.json()
        cv = _build_cost_vector(_idea(ec=ec))
        assert data["compute_cc"] == cv.compute_cc
        assert data["infrastructure_cc"] == cv.infrastructure_cc
        assert data["human_attention_cc"] == cv.human_attention_cc
        assert data["opportunity_cc"] == cv.opportunity_cc
        assert data["external_cc"] == cv.external_cc
        assert data["total_cc"] == cv.total_cc

    @pytest.mark.anyio
    async def test_negative_rejected(self, client: AsyncClient):
        res = await client.get("/api/utils/cost_vector", params={"estimated_cost": -1.0})
        assert res.status_code == 422


class TestValueVectorEndpoint:
    """Value-vector decomposition — sibling of cost_vector, same round unlock."""

    @pytest.mark.anyio
    async def test_default_decimal_case(self, client: AsyncClient):
        res = await client.get("/api/utils/value_vector")
        assert res.status_code == 200, res.text
        data = res.json()
        # pv=9.205: adoption 4.6025, lineage 2.7615, friction_avoided 1.841, total 9.205
        assert data["adoption_cc"] == 4.6025
        assert data["lineage_cc"] == 2.7615
        assert data["friction_avoided_cc"] == 1.841
        assert data["revenue_cc"] == 0.0
        assert data["total_cc"] == 9.205
        assert data["potential_value"] == 9.205
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_zero_all_components_zero(self, client: AsyncClient):
        res = await client.get("/api/utils/value_vector", params={"potential_value": 0.0})
        assert res.status_code == 200, res.text
        data = res.json()
        assert [data["adoption_cc"], data["lineage_cc"], data["friction_avoided_cc"],
                data["revenue_cc"], data["total_cc"]] == [0.0] * 5

    @pytest.mark.anyio
    async def test_decimal_tie_break_banker_rounded(self, client: AsyncClient):
        """pv=33.333 → lineage 33.333*0.30 = 9.9999 (NOT 10.0); the half-to-even case."""
        res = await client.get("/api/utils/value_vector", params={"potential_value": 33.333})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["adoption_cc"] == 16.6665
        assert data["lineage_cc"] == 9.9999
        assert data["friction_avoided_cc"] == 6.6666
        assert data["total_cc"] == 33.333

    @pytest.mark.anyio
    @pytest.mark.parametrize("pv", [0.0, 100.0, 33.333, 0.125, 7.7775, 9.205, 1234.5678])
    async def test_matches_service_function_per_component(self, client: AsyncClient, pv: float):
        """Every component matches idea_scoring._build_value_vector exactly."""
        res = await client.get("/api/utils/value_vector", params={"potential_value": pv})
        assert res.status_code == 200, res.text
        data = res.json()
        vv = _build_value_vector(_idea(pv=pv))
        assert data["adoption_cc"] == vv.adoption_cc
        assert data["lineage_cc"] == vv.lineage_cc
        assert data["friction_avoided_cc"] == vv.friction_avoided_cc
        assert data["revenue_cc"] == vv.revenue_cc
        assert data["total_cc"] == vv.total_cc

    @pytest.mark.anyio
    async def test_negative_rejected(self, client: AsyncClient):
        res = await client.get("/api/utils/value_vector", params={"potential_value": -1.0})
        assert res.status_code == 422
