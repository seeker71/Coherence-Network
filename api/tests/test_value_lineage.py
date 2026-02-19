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
        assert data["schema_version"] == "energy-balanced-v1"
        assert data["weights"] == {
            "idea": 0.1,
            "research": 0.2,
            "spec": 0.2,
            "spec_upgrade": 0.15,
            "implementation": 0.5,
            "review": 0.2,
        }
        assert data["objective_weights"] == {
            "coherence": 0.35,
            "energy_flow": 0.2,
            "awareness": 0.2,
            "friction_relief": 0.15,
            "balance": 0.1,
        }
        assert set(data["signals"].keys()) == {
            "coherence",
            "energy_flow",
            "awareness",
            "friction",
            "balance",
        }
        amounts = {row["role"]: row["amount"] for row in data["payouts"]}
        assert amounts["idea"] == 100.0
        assert amounts["spec"] == 200.0
        assert amounts["implementation"] == 500.0
        assert amounts["review"] == 200.0


@pytest.mark.asyncio
async def test_payout_preview_supports_stage_investments(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    payload = {
        "idea_id": "coherence-energy-balance",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": ["PR#29"],
        "contributors": {},
        "investments": [
            {
                "stage": "research",
                "contributor": "alice",
                "energy_units": 3.0,
                "coherence_score": 0.9,
                "awareness_score": 0.9,
                "friction_score": 0.1,
            },
            {
                "stage": "implementation",
                "contributor": "bob",
                "energy_units": 4.0,
                "coherence_score": 0.4,
                "awareness_score": 0.5,
                "friction_score": 0.9,
            },
            {
                "stage": "implementation",
                "contributor": "carol",
                "energy_units": 2.0,
                "coherence_score": 0.9,
                "awareness_score": 0.8,
                "friction_score": 0.1,
            },
            {
                "stage": "spec_upgrade",
                "contributor": "dave",
                "energy_units": 1.5,
                "coherence_score": 0.85,
                "awareness_score": 0.8,
                "friction_score": 0.2,
            },
        ],
        "estimated_cost": 80.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=payload)
        assert created.status_code == 201
        lineage_id = created.json()["id"]

        usage = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "adoption_events", "value": 120.0},
        )
        assert usage.status_code == 201

        payout = await client.post(
            f"/api/value-lineage/links/{lineage_id}/payout-preview",
            json={"payout_pool": 1000.0},
        )
        assert payout.status_code == 200
        data = payout.json()

        rows = {(row["role"], row["contributor"]): row for row in data["payouts"]}
        assert ("research", "alice") in rows
        assert ("spec_upgrade", "dave") in rows
        assert ("implementation", "bob") in rows
        assert ("implementation", "carol") in rows
        assert rows[("implementation", "carol")]["amount"] > rows[("implementation", "bob")]["amount"]
        assert rows[("implementation", "carol")]["effective_weight"] > rows[("implementation", "bob")][
            "effective_weight"
        ]

        total_amount = sum(float(row["amount"]) for row in data["payouts"])
        assert total_amount == pytest.approx(1000.0, abs=0.1)


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


@pytest.mark.asyncio
async def test_minimum_e2e_flow_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run = await client.post("/api/value-lineage/minimum-e2e-flow")
        assert run.status_code == 200
        data = run.json()
        assert data["lineage_id"].startswith("lnk_")
        assert data["usage_event_id"].startswith("evt_")
        assert data["valuation"]["measured_value_total"] == 5.0
        assert data["payout_preview"]["payout_pool"] == 100.0
        assert "lineage_created" in data["checks"]
        assert "usage_event_created" in data["checks"]


@pytest.mark.asyncio
async def test_list_links_endpoint_returns_links_newest_first(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))

    payload_a = {
        "idea_id": "portfolio-governance",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": ["PR#1"],
        "contributors": {"idea": "a", "spec": "b", "implementation": "c", "review": "d"},
        "estimated_cost": 1.0,
    }
    payload_b = {
        "idea_id": "oss-interface-alignment",
        "spec_id": "049-system-lineage-inventory-and-runtime-telemetry",
        "implementation_refs": ["PR#2"],
        "contributors": {"idea": "a", "spec": "b", "implementation": "c", "review": "d"},
        "estimated_cost": 2.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created_a = await client.post("/api/value-lineage/links", json=payload_a)
        assert created_a.status_code == 201
        created_b = await client.post("/api/value-lineage/links", json=payload_b)
        assert created_b.status_code == 201

        listed = await client.get("/api/value-lineage/links")
        assert listed.status_code == 200
        data = listed.json()
        assert "links" in data
        assert isinstance(data["links"], list)
        assert data["links"][0]["spec_id"] == payload_b["spec_id"]
