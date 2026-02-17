from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.automation_usage import ProviderReadinessReport, ProviderReadinessRow
from app.services import agent_service, automation_usage_service


@pytest.mark.asyncio
async def test_automation_usage_endpoint_returns_normalized_providers(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Collect automation usage baseline", "task_type": "impl"},
        )
        assert task.status_code == 201
        task_id = task.json()["id"]
        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        assert running.status_code == 200
        completed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "done"},
        )
        assert completed.status_code == 200

        usage = await client.get("/api/automation/usage", params={"force_refresh": True})
        assert usage.status_code == 200
        payload = usage.json()
        assert payload["tracked_providers"] >= 3
        assert "limit_coverage" in payload
        assert payload["limit_coverage"]["providers_considered"] >= 1
        assert "providers_missing_limit_metrics" in payload["limit_coverage"]
        providers = {row["provider"]: row for row in payload["providers"]}
        assert "coherence-internal" in providers
        assert "github" in providers
        assert "openai" in providers
        assert providers["coherence-internal"]["status"] == "ok"
        assert any(m["id"] == "tasks_tracked" for m in providers["coherence-internal"]["metrics"])
        assert providers["coherence-internal"]["actual_current_usage"] is not None
        assert providers["coherence-internal"]["data_source"] == "runtime_events"
        assert len(providers["coherence-internal"]["official_records"]) >= 1
        assert len(providers["github"]["official_records"]) >= 1
        assert providers["github"]["data_source"] in {"configuration_only", "provider_api", "provider_cli", "unknown"}


@pytest.mark.asyncio
async def test_automation_usage_alerts_raise_on_low_remaining_ratio(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get("/api/automation/usage/alerts", params={"threshold_ratio": 1.0})
        assert report.status_code == 200
        payload = report.json()
        assert payload["threshold_ratio"] == 1.0
        assert isinstance(payload["alerts"], list)
        # At least unavailable provider alerts should be present when external creds are missing.
        assert any(alert["provider"] == "github" for alert in payload["alerts"])
        assert any(alert["provider"] == "openai" for alert in payload["alerts"])


@pytest.mark.asyncio
async def test_automation_usage_snapshots_endpoint_returns_persisted_rows(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        collect = await client.get("/api/automation/usage", params={"force_refresh": True})
        assert collect.status_code == 200

        snapshots = await client.get("/api/automation/usage/snapshots", params={"limit": 50})
        assert snapshots.status_code == 200
        payload = snapshots.json()
        assert payload["count"] >= 1
        assert len(payload["snapshots"]) >= 1


@pytest.mark.asyncio
async def test_automation_usage_snapshots_bootstrap_into_db_backend(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots_file = tmp_path / "automation_usage.json"
    snapshots_file.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "id": "provider_bootstrap_1",
                        "provider": "github",
                        "kind": "github",
                        "status": "ok",
                        "collected_at": "2026-02-16T00:00:00Z",
                        "metrics": [],
                        "notes": ["bootstrapped"],
                        "raw": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(snapshots_file))
    monkeypatch.setenv("AUTOMATION_USAGE_USE_DB", "1")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'telemetry.db'}")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        snapshots = await client.get("/api/automation/usage/snapshots", params={"limit": 20})
        assert snapshots.status_code == 200
        payload = snapshots.json()
        ids = {row["id"] for row in payload["snapshots"]}
        assert "provider_bootstrap_1" in ids


@pytest.mark.asyncio
async def test_subscription_estimator_reports_upgrade_cost_and_benefit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_SUBSCRIPTION_TIER", "pro")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CURSOR_CLI_MODEL", "openrouter/free")
    monkeypatch.setenv("CURSOR_SUBSCRIPTION_TIER", "pro")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_SUBSCRIPTION_TIER", "free")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get("/api/automation/usage/subscription-estimator")
        assert report.status_code == 200
        payload = report.json()
        assert payload["detected_subscriptions"] >= 2
        assert payload["estimated_next_monthly_cost_usd"] >= payload["estimated_current_monthly_cost_usd"]
        assert payload["estimated_monthly_upgrade_delta_usd"] >= 0
        assert isinstance(payload["plans"], list)
        assert len(payload["plans"]) >= 4

        openai = next(row for row in payload["plans"] if row["provider"] == "openai")
        assert openai["detected"] is True
        assert openai["current_tier"] == "pro"
        assert openai["next_tier"] == "team"
        assert openai["next_monthly_cost_usd"] >= openai["current_monthly_cost_usd"]
        assert openai["estimated_benefit_score"] >= 0
        assert openai["estimated_roi"] >= 0


@pytest.mark.asyncio
async def test_provider_readiness_reports_blocking_required_provider_gaps(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("AUTOMATION_REQUIRED_PROVIDERS", "coherence-internal,openai,github")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GH_TOKEN", "")
    monkeypatch.setenv("GITHUB_BILLING_OWNER", "")
    monkeypatch.setenv("GITHUB_BILLING_SCOPE", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get("/api/automation/usage/readiness")
        assert report.status_code == 200
        payload = report.json()
        assert payload["all_required_ready"] is False
        providers = {row["provider"]: row for row in payload["providers"]}
        assert providers["openai"]["severity"] == "critical"
        assert providers["github"]["severity"] == "critical"
        assert providers["coherence-internal"]["severity"] in {"info", "warning"}


@pytest.mark.asyncio
async def test_provider_readiness_accepts_overridden_required_provider_list(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AUTOMATION_REQUIRE_KEYS_FOR_ACTIVE_PROVIDERS", "0")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get(
            "/api/automation/usage/readiness",
            params={"required_providers": "coherence-internal,openrouter"},
        )
        assert report.status_code == 200
        payload = report.json()
        assert payload["all_required_ready"] is True


@pytest.mark.asyncio
async def test_provider_in_active_use_requires_key_for_readiness(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("AUTOMATION_REQUIRE_KEYS_FOR_ACTIVE_PROVIDERS", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_BILLING_OWNER", "")
    monkeypatch.setenv("GITHUB_BILLING_SCOPE", "")

    monkeypatch.setattr(
        agent_service,
        "get_usage_summary",
        lambda: {
            "by_model": {"openrouter/free": {"count": 4, "by_status": {"completed": 4}, "last_used": None}},
            "execution": {
                "tracked_runs": 4,
                "failed_runs": 0,
                "success_runs": 4,
                "success_rate": 1.0,
                "by_executor": {},
                "coverage": {"completed_or_failed_tasks": 4, "tracked_task_runs": 4, "coverage_rate": 1.0},
                "recent_runs": [],
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get(
            "/api/automation/usage/readiness",
            params={"required_providers": "coherence-internal", "force_refresh": True},
        )
        assert report.status_code == 200
        payload = report.json()
        providers = {row["provider"]: row for row in payload["providers"]}
        assert payload["all_required_ready"] is False
        assert providers["openrouter"]["required"] is True
        assert providers["openrouter"]["severity"] == "critical"
        assert providers["openrouter"]["configured"] is False


@pytest.mark.asyncio
async def test_automation_usage_includes_runtime_task_runs_metric_for_active_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_BILLING_OWNER", "")
    monkeypatch.setenv("GITHUB_BILLING_SCOPE", "")

    monkeypatch.setattr(
        agent_service,
        "get_usage_summary",
        lambda: {
            "by_model": {"openrouter/free": {"count": 3, "by_status": {"completed": 3}, "last_used": None}},
            "execution": {
                "tracked_runs": 3,
                "failed_runs": 0,
                "success_runs": 3,
                "success_rate": 1.0,
                "by_executor": {},
                "coverage": {"completed_or_failed_tasks": 3, "tracked_task_runs": 3, "coverage_rate": 1.0},
                "recent_runs": [],
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        usage = await client.get("/api/automation/usage", params={"force_refresh": True})
        assert usage.status_code == 200
        payload = usage.json()
        providers = {row["provider"]: row for row in payload["providers"]}
        assert "openrouter" in providers
        assert any(metric["id"] == "runtime_task_runs" for metric in providers["openrouter"]["metrics"])


@pytest.mark.asyncio
async def test_provider_validation_contract_blocks_without_execution_events(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    required = ["coherence-internal", "openai-codex", "github", "railway", "claude"]
    monkeypatch.setattr(
        automation_usage_service,
        "provider_readiness_report",
        lambda **kwargs: ProviderReadinessReport(
            required_providers=required,
            all_required_ready=True,
            blocking_issues=[],
            recommendations=[],
            providers=[
                ProviderReadinessRow(
                    provider=provider,
                    kind="custom",
                    status="ok",
                    required=True,
                    configured=True,
                    severity="info",
                    missing_env=[],
                    notes=[],
                )
                for provider in required
            ],
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get(
            "/api/automation/usage/provider-validation",
            params={"required_providers": ",".join(required), "force_refresh": False},
        )
        assert report.status_code == 200
        payload = report.json()
        assert payload["all_required_validated"] is False
        assert len(payload["blocking_issues"]) == len(required)
        for row in payload["providers"]:
            assert row["usage_events"] == 0
            assert row["successful_events"] == 0
            assert row["validated_execution"] is False


@pytest.mark.asyncio
async def test_provider_validation_run_creates_execution_evidence_and_passes_contract(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    required = ["coherence-internal", "openai-codex", "github", "railway", "claude"]
    monkeypatch.setattr(
        automation_usage_service,
        "provider_readiness_report",
        lambda **kwargs: ProviderReadinessReport(
            required_providers=required,
            all_required_ready=True,
            blocking_issues=[],
            recommendations=[],
            providers=[
                ProviderReadinessRow(
                    provider=provider,
                    kind="custom",
                    status="ok",
                    required=True,
                    configured=True,
                    severity="info",
                    missing_env=[],
                    notes=[],
                )
                for provider in required
            ],
        ),
    )
    monkeypatch.setattr(automation_usage_service, "_probe_internal", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_probe_openai_codex", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_probe_github", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_probe_railway", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_probe_claude", lambda: (True, "ok"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run = await client.post(
            "/api/automation/usage/provider-validation/run",
            params={"required_providers": ",".join(required)},
        )
        assert run.status_code == 200
        run_payload = run.json()
        assert len(run_payload["probes"]) == len(required)
        assert all(item["ok"] for item in run_payload["probes"])

        report = await client.get(
            "/api/automation/usage/provider-validation",
            params={
                "required_providers": ",".join(required),
                "runtime_window_seconds": 86400,
                "min_execution_events": 1,
                "force_refresh": False,
            },
        )
        assert report.status_code == 200
        payload = report.json()
        assert payload["all_required_validated"] is True
        for row in payload["providers"]:
            assert row["usage_events"] >= 1
            assert row["successful_events"] >= 1
            assert row["validated_execution"] is True


@pytest.mark.asyncio
async def test_automation_usage_endpoints_trace_back_to_spec_100(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")

    expected_paths = {
        "/api/automation/usage",
        "/api/automation/usage/snapshots",
        "/api/automation/usage/alerts",
        "/api/automation/usage/subscription-estimator",
        "/api/automation/usage/readiness",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        traceability = await client.get("/api/inventory/endpoint-traceability")
        assert traceability.status_code == 200
        items = traceability.json()["items"]

    rows = [row for row in items if row["path"] in expected_paths]
    assert len(rows) == len(expected_paths)
    for row in rows:
        assert row["spec"]["tracked"] is True
        assert "100" in row["spec"]["spec_ids"]
