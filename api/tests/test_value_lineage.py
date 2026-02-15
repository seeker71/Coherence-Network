from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_and_get_lineage_link(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    payload = {
        "idea_id": "oss-interface-alignment",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": ["PR#26", "commit:e616516"],
        "contributors": {
            "idea": "alice",
            "spec": "bob",
            "implementation": "carol",
            "review": "dave",
        },
        "estimated_cost": 120.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=payload)
        assert created.status_code == 201
        link = created.json()
        assert link["idea_id"] == payload["idea_id"]
        assert link["spec_id"] == payload["spec_id"]
        assert link["contributors"]["implementation"] == "carol"

        fetched = await client.get(f"/api/value-lineage/links/{link['id']}")
        assert fetched.status_code == 200
        assert fetched.json() == link


@pytest.mark.asyncio
async def test_usage_events_roll_up_to_valuation(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    payload = {
        "idea_id": "portfolio-governance",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": ["PR#27"],
        "contributors": {"idea": "alice", "spec": "bob", "implementation": "carol"},
        "estimated_cost": 50.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=payload)
        lineage_id = created.json()["id"]

        ev1 = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "adoption_events", "value": 40.0},
        )
        assert ev1.status_code == 201

        ev2 = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "web", "metric": "validated_flows", "value": 10.0},
        )
        assert ev2.status_code == 201

        valuation = await client.get(f"/api/value-lineage/links/{lineage_id}/valuation")
        assert valuation.status_code == 200
        data = valuation.json()
        assert data["measured_value_total"] == 50.0
        assert data["estimated_cost"] == 50.0
        assert data["roi_ratio"] == 1.0
        assert data["event_count"] == 2


@pytest.mark.asyncio
async def test_payout_preview_uses_role_weights(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    payload = {
        "idea_id": "coherence-signal-depth",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": ["PR#28"],
        "contributors": {
            "idea": "alice",
            "spec": "bob",
            "implementation": "carol",
            "review": "dave",
        },
        "estimated_cost": 80.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=payload)
        lineage_id = created.json()["id"]

        ev = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "adoption_events", "value": 100.0},
        )
        assert ev.status_code == 201

        payout = await client.post(
            f"/api/value-lineage/links/{lineage_id}/payout-preview",
            json={"payout_pool": 1000.0},
        )
        assert payout.status_code == 200
        data = payout.json()
        assert data["weights"] == {
            "idea": 0.1,
            "spec": 0.2,
            "implementation": 0.5,
            "review": 0.2,
        }
        amounts = {row["role"]: row["amount"] for row in data["payouts"]}
        assert amounts["idea"] == 100.0
        assert amounts["spec"] == 200.0
        assert amounts["implementation"] == 500.0
        assert amounts["review"] == 200.0


@pytest.mark.asyncio
async def test_lineage_404_contract(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/value-lineage/links/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Lineage link not found"

        missing_usage = await client.post(
            "/api/value-lineage/links/does-not-exist/usage-events",
            json={"source": "api", "metric": "x", "value": 1.0},
        )
        assert missing_usage.status_code == 404
        assert missing_usage.json()["detail"] == "Lineage link not found"
