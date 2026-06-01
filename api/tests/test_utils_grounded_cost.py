"""Tests for /api/utils/grounded_cost — the grounded-cost reduction of compute_idea_metrics.

The body runs as a Form recipe (endpoint_grounded_cost_demo.fk) that receives one
idea's ALREADY-FILTERED records and folds the grounded cost aggregates: the
spec actual/estimated cost sums, the per-commit clamped commit_cost_sum
(max(0.05, min(10.0, 0.10 + files*0.15 + lines*0.002)) per commit — the
_estimate_commit_cost_sum formula EXACTLY), the lineage estimated-cost sum, and
the computed_actual_cost composition. FILTERING the six collections by idea_id is
cheap host-side collection-narrowing (the host already does it); the reduction is
the kernel computation.

Three-way parity of the recipe body (CPython, kernel-bmf, Rust) is the
parity_suite gate; these tests verify the route is wired, returns the six
outputs, honors the commit clamp at both bounds, and matches the Python fallback.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers.utils import _grounded_cost_py

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestGroundedCostEndpoint:
    """The grounded-cost reduction folded over already-filtered records."""

    @pytest.mark.anyio
    async def test_canonical_records(self, client: AsyncClient):
        """The default records fold to the frozen six outputs (all non-integer floats)."""
        res = await client.get("/api/utils/grounded_cost")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_actual_cost_sum"] == 4.75
        assert data["spec_estimated_cost_sum"] == 6.75
        assert data["runtime_cost"] == 2.25
        assert data["commit_cost_sum"] == 0.75  # 0.10 + 3*0.15 + 100*0.002
        assert data["lineage_estimated_cost"] == 6.75
        assert data["computed_actual_cost"] == 7.75  # 4.75 + 2.25 + 0.75
        assert data["spec_count_in"] == 2
        assert data["commit_count_in"] == 1
        assert data["lineage_count_in"] == 2
        assert data["runtime"] in ("inline", "subprocess", "python-fallback")

    @pytest.mark.anyio
    async def test_distinct_records_match_fallback(self, client: AsyncClient):
        """A distinct record set returns the recipe's reduction, matching the fallback."""
        params = {
            "spec_actual_costs": "2.5,0.25",
            "spec_estimated_costs": "1.0,3.5",
            "commit_change_files": "2,4",
            "commit_lines_added": "10,250",
            "lineage_estimated_costs": "0.75,2.0",
            "runtime_cost": 1.5,
        }
        res = await client.get("/api/utils/grounded_cost", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        specs = [
            {"actual_cost": 2.5, "estimated_cost": 1.0},
            {"actual_cost": 0.25, "estimated_cost": 3.5},
        ]
        commits = [
            {"change_files": 2, "lines_added": 10},
            {"change_files": 4, "lines_added": 250},
        ]
        links = [{"estimated_cost": 0.75}, {"estimated_cost": 2.0}]
        expected = _grounded_cost_py(specs, commits, links, 1.5)
        got = [
            data["spec_actual_cost_sum"],
            data["spec_estimated_cost_sum"],
            data["runtime_cost"],
            data["commit_cost_sum"],
            data["lineage_estimated_cost"],
            data["computed_actual_cost"],
        ]
        assert got == expected

    @pytest.mark.anyio
    async def test_empty_records_fold_to_zero(self, client: AsyncClient):
        """All-empty records with runtime 0.0 fold to all zeros."""
        params = {
            "spec_actual_costs": "",
            "spec_estimated_costs": "",
            "commit_change_files": "",
            "commit_lines_added": "",
            "lineage_estimated_costs": "",
            "runtime_cost": 0.0,
        }
        res = await client.get("/api/utils/grounded_cost", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_actual_cost_sum"] == 0.0
        assert data["spec_estimated_cost_sum"] == 0.0
        assert data["commit_cost_sum"] == 0.0
        assert data["lineage_estimated_cost"] == 0.0
        assert data["computed_actual_cost"] == 0.0

    @pytest.mark.anyio
    async def test_commit_clamp_saturates_at_max(self, client: AsyncClient):
        """A huge commit saturates the per-commit cost at MAX_COST = 10.0."""
        params = {
            "spec_actual_costs": "",
            "spec_estimated_costs": "",
            "commit_change_files": "100",
            "commit_lines_added": "5000",
            "lineage_estimated_costs": "",
            "runtime_cost": 0.0,
        }
        res = await client.get("/api/utils/grounded_cost", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        # 0.10 + 100*0.15 + 5000*0.002 = 25.1, clamped to 10.0
        assert data["commit_cost_sum"] == 10.0
        assert data["computed_actual_cost"] == 10.0

    @pytest.mark.anyio
    async def test_mismatched_spec_lengths_rejected(self, client: AsyncClient):
        """spec_actual_costs and spec_estimated_costs of different lengths is a 422."""
        params = {"spec_actual_costs": "1.0,2.0", "spec_estimated_costs": "1.0"}
        res = await client.get("/api/utils/grounded_cost", params=params)
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_mismatched_commit_lengths_rejected(self, client: AsyncClient):
        """commit_change_files and commit_lines_added of different lengths is a 422."""
        params = {"commit_change_files": "1,2", "commit_lines_added": "10"}
        res = await client.get("/api/utils/grounded_cost", params=params)
        assert res.status_code == 422
