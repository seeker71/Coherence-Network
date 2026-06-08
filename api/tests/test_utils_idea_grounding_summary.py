"""Tests for /api/utils/idea_grounding_summary — the first list-of-record-reduction route.

The body runs as a Form recipe (endpoint_idea_grounding_summary_demo.fk) that
receives one idea's pre-fetched specs as a LIST OF RECORDS (marshalled from a
Python list[dict|model]) and FOLDS four integer grounding signals across it:
spec_count, total_event_count, specs_with_value_count, max_event_count. This is
gate #1 ("list-of-record reduction") in API_KERNEL_READINESS — every prior
structure-access route read fields from ONE record; this folds over a list.

Three-way parity of the recipe body (CPython, kernel-bmf, Rust) is the
parity_suite gate; the list-of-record marshalling and model→dict normalization
are covered by test_form_kernel_bridge_structure_access. These tests verify the
route is wired, returns the expected shape, and matches the documented recipe
anchors over the real reduction.
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


class TestIdeaGroundingSummaryEndpoint:
    """Integer grounding signals reduced over a list of spec records."""

    @pytest.mark.anyio
    async def test_canonical_specs(self, client: AsyncClient):
        """The default three specs fold to [3, 10, 2, 7]."""
        res = await client.get("/api/utils/idea_grounding_summary")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_count"] == 3
        assert data["total_event_count"] == 10
        assert data["specs_with_value_count"] == 2
        assert data["max_event_count"] == 7
        assert data["spec_count_in"] == 3
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_distinct_specs_match_parity_reference(self, client: AsyncClient):
        """A distinct spec list returns the recipe's reduction, matching the parity reference."""
        params = {"event_counts": "4,1,9,0", "actual_values": "2.0,0.0,3.5,0.0"}
        res = await client.get("/api/utils/idea_grounding_summary", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert [
            data["spec_count"],
            data["total_event_count"],
            data["specs_with_value_count"],
            data["max_event_count"],
        ] == [4, 14, 2, 9]

    @pytest.mark.anyio
    async def test_empty_specs_fold_to_zeros(self, client: AsyncClient):
        """An empty spec list folds to [0, 0, 0, 0] — the identity accumulators."""
        params = {"event_counts": "", "actual_values": ""}
        res = await client.get("/api/utils/idea_grounding_summary", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["spec_count"] == 0
        assert data["total_event_count"] == 0
        assert data["specs_with_value_count"] == 0
        assert data["max_event_count"] == 0

    @pytest.mark.anyio
    async def test_mismatched_lengths_rejected(self, client: AsyncClient):
        """event_counts and actual_values of different lengths is a 422."""
        params = {"event_counts": "1,2,3", "actual_values": "1.0"}
        res = await client.get("/api/utils/idea_grounding_summary", params=params)
        assert res.status_code == 422
