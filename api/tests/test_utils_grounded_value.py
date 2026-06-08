"""Tests for /api/utils/grounded_value — the value/realization/confidence reduction of compute_idea_metrics.

The body runs as a Form recipe (endpoint_grounded_value_demo.fk) that receives
the host-derived scalars for one idea and computes the SECOND and FINAL numeric
slice of compute_idea_metrics: computed_actual_value = max(lineage_measured_value,
usage_revenue, spec_actual_value_sum), computed_estimated_cost =
max(spec_estimated_cost_sum, lineage_estimated_cost), value_realization_pct =
min(value/potential, 1.0) guarded by potential>0, the count→level signals
has_runtime_data/has_commits = min(1.0, count/N) guarded by count>0, and
computed_confidence = clamp(weighted coverage sum, 0.05, 0.95) with weights
0.30/0.25/0.25/0.10/0.10. The boolean-presence levels (has_specs_with_data,
has_lineage, has_friction — any(...)-over-records / len>0 ladders) and the
collection filtering are currently resolved before dispatch; they are visible
next native work.

Three-way parity of the recipe body (CPython, kernel-bmf, Rust) is the
parity_suite gate; these tests verify the route is wired, returns the four
outputs, honors the realization guard + ceiling and the confidence [0.05, 0.95]
clamp at both bounds, and matches the documented recipe anchors.
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


class TestGroundedValueEndpoint:
    """The value/realization/confidence reduction over host-derived scalars."""

    @pytest.mark.anyio
    async def test_canonical_scalars(self, client: AsyncClient):
        """The default scalars fold to the frozen four outputs (all non-integer floats)."""
        res = await client.get("/api/utils/grounded_value")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["computed_actual_value"] == 12.5  # max(12.5, 0.007, 4.25)
        assert data["computed_estimated_cost"] == 6.75  # max(6.75, 5.5)
        assert data["value_realization_pct"] == 0.625  # min(12.5/20.0, 1.0)
        # 1.0*0.30 + 0.7*0.25 + 1.0*0.25 + 0.6*0.10 + 0.3*0.10 = 0.815
        assert data["computed_confidence"] == 0.815
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_realization_guard_zero_potential(self, client: AsyncClient):
        """spec_potential_value_sum=0 takes the guard branch → 0.0 (no division)."""
        res = await client.get(
            "/api/utils/grounded_value", params={"spec_potential_value_sum": 0.0}
        )
        assert res.status_code == 200, res.text
        assert res.json()["value_realization_pct"] == 0.0

    @pytest.mark.anyio
    async def test_realization_ratio_above_one_clamps(self, client: AsyncClient):
        """A ratio > 1 saturates at the min(_, 1.0) ceiling."""
        params = {"lineage_measured_value": 30.0, "spec_potential_value_sum": 20.0}
        res = await client.get("/api/utils/grounded_value", params=params)
        assert res.status_code == 200, res.text
        assert res.json()["value_realization_pct"] == 1.0  # min(1.5, 1.0)

    @pytest.mark.anyio
    async def test_confidence_clamps_to_ceiling(self, client: AsyncClient):
        """All signals present + saturating counts → weighted sum clamped to 0.95."""
        params = {
            "runtime_event_count": 15,  # min(1.0, 1.5) = 1.0
            "commit_count": 8,  # min(1.0, 1.6) = 1.0
            "has_specs_with_data": 1.0,
            "has_lineage": 1.0,
            "has_friction": 1.0,
        }
        res = await client.get("/api/utils/grounded_value", params=params)
        assert res.status_code == 200, res.text
        # raw = 0.30+0.25+0.25+0.10+0.10 = 1.0, clamped to 0.95
        assert res.json()["computed_confidence"] == 0.95

    @pytest.mark.anyio
    async def test_confidence_clamps_to_floor(self, client: AsyncClient):
        """All signals absent → weighted sum 0.0 clamped to the 0.05 floor."""
        params = {
            "runtime_event_count": 0,
            "commit_count": 0,
            "has_specs_with_data": 0.0,
            "has_lineage": 0.0,
            "has_friction": 0.0,
        }
        res = await client.get("/api/utils/grounded_value", params=params)
        assert res.status_code == 200, res.text
        assert res.json()["computed_confidence"] == 0.05

    @pytest.mark.anyio
    async def test_max_of_three_each_candidate_wins(self, client: AsyncClient):
        """computed_actual_value picks the strongest of the three value signals."""
        # usage_revenue wins
        res = await client.get(
            "/api/utils/grounded_value",
            params={
                "lineage_measured_value": 1.5,
                "usage_revenue": 8.75,
                "spec_actual_value_sum": 4.25,
            },
        )
        assert res.json()["computed_actual_value"] == 8.75
        # spec_actual_value_sum wins
        res = await client.get(
            "/api/utils/grounded_value",
            params={
                "lineage_measured_value": 1.5,
                "usage_revenue": 0.007,
                "spec_actual_value_sum": 9.25,
            },
        )
        assert res.json()["computed_actual_value"] == 9.25

    @pytest.mark.anyio
    async def test_distinct_scalars_match_recipe_anchor(self, client: AsyncClient):
        """A distinct scalar set returns the committed recipe reduction."""
        params = {
            "lineage_measured_value": 1.5,
            "usage_revenue": 8.75,
            "spec_actual_value_sum": 4.25,
            "spec_estimated_cost_sum": 3.25,
            "lineage_estimated_cost": 7.5,
            "spec_potential_value_sum": 20.0,
            "runtime_event_count": 4,
            "commit_count": 2,
            "has_specs_with_data": 0.5,
            "has_lineage": 0.5,
            "has_friction": 0.3,
        }
        res = await client.get("/api/utils/grounded_value", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        got = [
            data["computed_actual_value"],
            data["computed_estimated_cost"],
            data["value_realization_pct"],
            data["computed_confidence"],
        ]
        assert got == [8.75, 7.5, 0.4375, 0.44500000000000006]
