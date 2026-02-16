from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import metrics_service


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


@pytest.mark.asyncio
async def test_friction_entry_points_include_monitor_and_failed_cost_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events_file = tmp_path / "friction_events.jsonl"
    monitor_file = tmp_path / "monitor_issues.json"
    gha_file = tmp_path / "github_actions_health.json"
    metrics_file = tmp_path / "metrics.jsonl"
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(events_file))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(monitor_file))
    monkeypatch.setenv("GITHUB_ACTIONS_HEALTH_PATH", str(gha_file))
    monkeypatch.setattr(metrics_service, "METRICS_FILE", str(metrics_file))

    monitor_file.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "issue-1",
                        "condition": "github_actions_high_failure_rate",
                        "severity": "high",
                        "message": "too many failed runs",
                        "suggested_action": "https://github.com/seeker71/Coherence-Network/actions",
                    }
                ],
                "last_check": "2026-02-16T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    gha_file.write_text(
        json.dumps(
            {
                "available": True,
                "repo": "seeker71/Coherence-Network",
                "completed_runs": 12,
                "failed_runs": 6,
                "failure_rate": 0.5,
                "wasted_minutes_failed": 31.2,
                "official_records": [
                    "https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository"
                ],
                "sample_failed_run_links": ["https://github.com/seeker71/Coherence-Network/actions/runs/1"],
            }
        ),
        encoding="utf-8",
    )
    metrics_file.write_text(
        json.dumps(
            {
                "task_id": "task-1",
                "task_type": "impl",
                "model": "openai-codex",
                "duration_seconds": 600.0,
                "status": "failed",
                "created_at": "2026-02-16T01:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get("/api/friction/entry-points?window_days=365&limit=50")

    assert report.status_code == 200
    body = report.json()
    assert body["total_entry_points"] >= 2
    keys = {row["key"] for row in body["entry_points"]}
    assert "monitor:github_actions_high_failure_rate" in keys
    assert "github-actions:failure-rate" in keys


@pytest.mark.asyncio
async def test_friction_events_bootstrap_into_db_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events_file = tmp_path / "friction_events.jsonl"
    events_file.write_text(
        json.dumps(
            {
                "id": "fric-db-1",
                "timestamp": "2026-02-16T00:00:00Z",
                "stage": "ci",
                "block_type": "test_failure",
                "severity": "high",
                "owner": "ci",
                "unblock_condition": "Fix failing checks",
                "energy_loss_estimate": 4.0,
                "cost_of_delay": 2.0,
                "status": "open",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(events_file))
    monkeypatch.setenv("FRICTION_USE_DB", "1")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'telemetry.db'}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/friction/events?limit=20")

    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert "fric-db-1" in ids
