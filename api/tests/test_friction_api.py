from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_friction_events_create_list_and_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events_file = tmp_path / "friction_events.jsonl"
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(events_file))

    payload_open = {
        "id": "fric-1",
        "timestamp": "2026-02-15T00:00:00Z",
        "stage": "validation",
        "block_type": "missing_evidence",
        "severity": "high",
        "owner": "release-manager",
        "unblock_condition": "Run production e2e",
        "energy_loss_estimate": 5.0,
        "cost_of_delay": 2.0,
        "status": "open",
    }
    payload_resolved = {
        "id": "fric-2",
        "timestamp": "2026-02-15T00:30:00Z",
        "stage": "deploy",
        "block_type": "pending_checks",
        "severity": "medium",
        "owner": "ci",
        "unblock_condition": "Checks green",
        "energy_loss_estimate": 3.0,
        "cost_of_delay": 1.0,
        "status": "resolved",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c1 = await client.post("/api/friction/events", json=payload_open)
        c2 = await client.post("/api/friction/events", json=payload_resolved)
        listed = await client.get("/api/friction/events")
        only_open = await client.get("/api/friction/events?status=open")

    assert c1.status_code == 201
    assert c2.status_code == 201
    assert listed.status_code == 200
    assert only_open.status_code == 200
    assert len(listed.json()) == 2
    assert len(only_open.json()) == 1
    assert only_open.json()[0]["id"] == "fric-1"


@pytest.mark.asyncio
async def test_friction_report_aggregates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events_file = tmp_path / "friction_events.jsonl"
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(events_file))

    payload = {
        "id": "fric-3",
        "timestamp": "2026-02-15T01:00:00Z",
        "stage": "validation",
        "block_type": "missing_evidence",
        "severity": "high",
        "owner": "release-manager",
        "unblock_condition": "Run production e2e",
        "energy_loss_estimate": 7.5,
        "cost_of_delay": 2.5,
        "status": "open",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/friction/events", json=payload)
        report = await client.get("/api/friction/report?window_days=365")

    assert report.status_code == 200
    body = report.json()
    assert body["total_events"] >= 1
    assert body["total_energy_loss"] >= 7.5
    assert isinstance(body["top_block_types"], list)
    assert body["source_file"].endswith("friction_events.jsonl")
