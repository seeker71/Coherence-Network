"""Tests for the value lineage and payout attribution API.

Covers the minimum e2e flow:
  POST /api/value-lineage/links
  -> POST /api/value-lineage/{id}/usage-events
  -> GET  /api/value-lineage/{id}/valuation
  -> POST /api/value-lineage/{id}/payout-preview
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
API_KEY = "dev-key"
HEADERS = {"X-API-Key": API_KEY}


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# ---------------------------------------------------------------------------
# Minimum e2e flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_minimum_e2e_flow_endpoint():
    """Prove idea → spec → implementation → value → payout works end-to-end."""
    async with await _client() as c:
        # 1. POST /api/value-lineage/links
        link_payload = {
            "idea_id": "oss-interface-alignment",
            "spec_id": "value-lineage-and-payout-attribution",
            "implementation_refs": ["api/app/routers/value_lineage.py"],
            "contributors": {
                "idea": "codex-idea",
                "spec": "codex-spec",
                "implementation": "codex-impl",
                "review": "human-review",
            },
            "investments": [
                {
                    "stage": "implementation",
                    "contributor": "codex-impl",
                    "energy_units": 3.0,
                    "coherence_score": 0.9,
                    "awareness_score": 0.8,
                    "friction_score": 0.2,
                }
            ],
            "estimated_cost": 10.0,
        }
        r = await c.post("/api/value-lineage/links", json=link_payload, headers=HEADERS)
        assert r.status_code == 201, r.text
        link = r.json()
        lineage_id = link["id"]
        assert lineage_id.startswith("lnk_")
        assert link["idea_id"] == "oss-interface-alignment"
        assert link["spec_id"] == "value-lineage-and-payout-attribution"

        # 2. POST /api/value-lineage/{id}/usage-events
        event_payload = {
            "source": "api",
            "metric": "minimum_e2e_validated",
            "value": 25.0,
        }
        r = await c.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json=event_payload,
            headers=HEADERS,
        )
        assert r.status_code == 201, r.text
        event = r.json()
        assert event["id"].startswith("evt_")
        assert event["lineage_id"] == lineage_id
        assert event["value"] == 25.0

        # 3. GET /api/value-lineage/{id}/valuation
        r = await c.get(f"/api/value-lineage/links/{lineage_id}/valuation")
        assert r.status_code == 200, r.text
        val = r.json()
        assert val["lineage_id"] == lineage_id
        assert val["measured_value_total"] == 25.0
        assert val["estimated_cost"] == 10.0
        assert val["roi_ratio"] == 2.5
        assert val["event_count"] == 1

        # 4. POST /api/value-lineage/{id}/payout-preview
        r = await c.post(
            f"/api/value-lineage/links/{lineage_id}/payout-preview",
            json={"payout_pool": 100.0},
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        payout = r.json()
        assert payout["lineage_id"] == lineage_id
        assert payout["payout_pool"] == 100.0
        assert len(payout["payouts"]) >= 1
        total_amount = sum(row["amount"] for row in payout["payouts"])
        assert abs(total_amount - 100.0) < 0.01, f"Payouts don't sum to pool: {total_amount}"
        assert "coherence" in payout["signals"]
        assert "energy_flow" in payout["signals"]


# ---------------------------------------------------------------------------
# 404 for unknown lineage id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_valuation_404():
    async with await _client() as c:
        r = await c.get("/api/value-lineage/links/lnk_nonexistent/valuation")
    assert r.status_code == 404
    assert r.json()["detail"] == "Lineage link not found"


@pytest.mark.asyncio
async def test_add_usage_event_404():
    async with await _client() as c:
        r = await c.post(
            "/api/value-lineage/links/lnk_nonexistent/usage-events",
            json={"source": "test", "metric": "hits", "value": 1.0},
            headers=HEADERS,
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "Lineage link not found"


@pytest.mark.asyncio
async def test_payout_preview_404():
    async with await _client() as c:
        r = await c.post(
            "/api/value-lineage/links/lnk_nonexistent/payout-preview",
            json={"payout_pool": 50.0},
            headers=HEADERS,
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "Lineage link not found"


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_link_requires_api_key():
    async with await _client() as c:
        r = await c.post(
            "/api/value-lineage/links",
            json={
                "idea_id": "test",
                "spec_id": "test",
                "contributors": {},
                "estimated_cost": 1.0,
            },
        )
    assert r.status_code == 401
