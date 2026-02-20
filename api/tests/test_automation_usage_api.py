from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.automation_usage import (
    ProviderReadinessReport,
    ProviderReadinessRow,
    UsageMetric,
    ProviderUsageOverview,
    ProviderUsageSnapshot,
)
from app.services import agent_service, automation_usage_service, telemetry_persistence_service


def test_configured_status_openai_codex_accepts_oauth_session(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {})

    configured, missing, present, notes = automation_usage_service._configured_status("openai-codex")
    assert configured is True
    assert missing == []
    assert "codex_oauth_session" in present
    assert any("Codex OAuth session" in note for note in notes)


def test_probe_openai_codex_accepts_oauth_without_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {})

    ok, detail = automation_usage_service._probe_openai_codex()
    assert ok is True
    assert detail.startswith("ok_via_codex_oauth_session:")


def test_evaluate_usage_alerts_skips_optional_unavailable_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_cursor_test",
                provider="cursor",
                kind="custom",
                status="unavailable",
                data_source="configuration_only",
                notes=["missing_env=one_of(CURSOR_API_KEY,CURSOR_CLI_MODEL)"],
            )
        ],
        unavailable_providers=["cursor"],
        tracked_providers=1,
        limit_coverage={},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=True: overview,
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_required_providers_from_env",
        lambda: ["coherence-internal", "openai", "github"],
    )
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {"cursor": 0})

    report = automation_usage_service.evaluate_usage_alerts(threshold_ratio=0.2)
    assert all(
        not (alert.provider == "cursor" and alert.metric_id == "provider_status")
        for alert in report.alerts
    )


def test_evaluate_usage_alerts_suppresses_openai_permission_only_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_openai_test",
                provider="openai",
                kind="openai",
                status="degraded",
                data_source="provider_api",
                notes=[
                    (
                        "OpenAI usage/cost fetch failed: usage=Client error '403 Forbidden' "
                        "for url 'https://api.openai.com/v1/organization/usage/completions'; "
                        "costs=Client error '403 Forbidden' for url 'https://api.openai.com/v1/organization/costs'"
                    )
                ],
            )
        ],
        unavailable_providers=["openai"],
        tracked_providers=1,
        limit_coverage={},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=True: overview,
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_required_providers_from_env",
        lambda: ["coherence-internal", "openai", "github"],
    )
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {"openai": 3})

    report = automation_usage_service.evaluate_usage_alerts(threshold_ratio=0.2)
    assert all(
        not (alert.provider == "openai" and alert.metric_id == "provider_status")
        for alert in report.alerts
    )


def test_evaluate_usage_alerts_flags_remaining_tracking_gap_for_required_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_openrouter_test",
                provider="openrouter",
                kind="custom",
                status="ok",
                data_source="provider_api",
                metrics=[],
            )
        ],
        unavailable_providers=[],
        tracked_providers=1,
        limit_coverage={},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: overview,
    )
    monkeypatch.setattr(
        automation_usage_service,
        "provider_readiness_report",
        lambda force_refresh=False: ProviderReadinessReport(
            required_providers=["openrouter"],
            all_required_ready=True,
            blocking_issues=[],
            recommendations=[],
            providers=[
                ProviderReadinessRow(
                    provider="openrouter",
                    kind="custom",
                    status="ok",
                    required=True,
                    configured=True,
                    severity="info",
                    missing_env=[],
                    notes=[],
                )
            ],
        ),
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_required_providers_from_env",
        lambda: ["coherence-internal", "openrouter"],
    )
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {})

    report = automation_usage_service.evaluate_usage_alerts(threshold_ratio=0.2)
    assert any(
        alert.provider == "openrouter" and alert.metric_id == "remaining_tracking_gap"
        for alert in report.alerts
    )


def test_provider_limit_guard_decision_blocks_low_monthly_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_openai_guard_test",
                provider="openai",
                kind="openai",
                status="ok",
                data_source="provider_api",
                metrics=[
                    UsageMetric(
                        id="credits",
                        label="OpenAI monthly credits",
                        unit="usd",
                        used=96.0,
                        remaining=4.0,
                        limit=100.0,
                        window="monthly",
                    )
                ],
            )
        ],
        unavailable_providers=[],
        tracked_providers=1,
        limit_coverage={},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: overview,
    )
    monkeypatch.setenv("AUTOMATION_PROVIDER_WINDOW_GUARD_ENABLED", "1")
    monkeypatch.setenv("AUTOMATION_PROVIDER_MIN_REMAINING_RATIO_MONTHLY", "0.1")

    decision = automation_usage_service.provider_limit_guard_decision("openai")
    assert decision["allowed"] is False
    assert decision["provider"] == "openai"
    assert decision["blocked_metrics"][0]["window"] == "monthly"
    assert decision["blocked_metrics"][0]["remaining_ratio"] == pytest.approx(0.04, rel=1e-6)


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
        assert "openrouter" in providers
        assert "supabase" in providers
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
async def test_external_tool_usage_events_endpoint_returns_persisted_rows(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'telemetry.db'}")
    telemetry_persistence_service.append_external_tool_usage_event(
        {
            "event_id": "tool_evt_1",
            "occurred_at": "2026-02-17T00:00:00Z",
            "tool_name": "github-api",
            "provider": "github-actions",
            "operation": "get_check_runs",
            "resource": "seeker71/Coherence-Network/commits/abc/check-runs",
            "status": "error",
            "http_status": 500,
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/automation/usage/external-tools",
            params={"limit": 20, "provider": "github-actions", "tool_name": "github-api"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] >= 1
        assert any(row.get("event_id") == "tool_evt_1" for row in payload["events"])


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
    monkeypatch.setattr(
        automation_usage_service,
        "_build_openrouter_snapshot",
        lambda: ProviderUsageSnapshot(
            id="provider_openrouter_test",
            provider="openrouter",
            kind="custom",
            status="ok",
            data_source="provider_api",
            metrics=[],
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get(
            "/api/automation/usage/readiness",
            params={"required_providers": "coherence-internal,openrouter", "force_refresh": True},
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

    required = ["coherence-internal", "openai-codex", "openclaw", "github", "railway", "claude"]
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

    required = ["coherence-internal", "openai-codex", "openclaw", "github", "railway", "claude"]
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
    monkeypatch.setattr(automation_usage_service, "_probe_openclaw", lambda: (True, "ok"))
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


def test_provider_validation_run_supports_openrouter_and_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automation_usage_service, "_probe_openrouter", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_probe_supabase", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_record_provider_probe_event", lambda **kwargs: None)

    report = automation_usage_service.run_provider_validation_probes(
        required_providers=["openrouter", "supabase"],
    )
    assert report["required_providers"] == ["openrouter", "supabase"]
    providers = {row["provider"]: row for row in report["probes"]}
    assert providers["openrouter"]["ok"] is True
    assert providers["supabase"]["ok"] is True


def test_provider_validation_run_supports_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automation_usage_service, "_probe_openai", lambda: (True, "ok"))
    monkeypatch.setattr(automation_usage_service, "_record_provider_probe_event", lambda **kwargs: None)

    report = automation_usage_service.run_provider_validation_probes(
        required_providers=["openai"],
    )
    assert report["required_providers"] == ["openai"]
    assert len(report["probes"]) == 1
    row = report["probes"][0]
    assert row["provider"] == "openai"
    assert row["ok"] is True
    assert row["detail"] == "ok"
    assert float(row["runtime_ms"]) >= 0.0


def test_provider_auto_heal_uses_multiple_strategies(monkeypatch: pytest.MonkeyPatch) -> None:
    probe_calls = {"count": 0}

    def _probe_openrouter():
        probe_calls["count"] += 1
        if probe_calls["count"] == 1:
            return False, "openrouter_probe_failed:temporary"
        return True, "ok"

    monkeypatch.setenv("AUTOMATION_PROVIDER_HEAL_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(automation_usage_service, "_probe_openrouter", _probe_openrouter)
    monkeypatch.setattr(automation_usage_service, "_record_provider_heal_event", lambda **kwargs: None)
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=True: ProviderUsageOverview(
            providers=[],
            unavailable_providers=[],
            tracked_providers=0,
            limit_coverage={},
        ),
    )
    monkeypatch.setattr(
        automation_usage_service,
        "provider_readiness_report",
        lambda **kwargs: ProviderReadinessReport(
            required_providers=["openrouter"],
            all_required_ready=False,
            blocking_issues=["openrouter"],
            recommendations=[],
            providers=[
                ProviderReadinessRow(
                    provider="openrouter",
                    kind="custom",
                    status="degraded",
                    required=True,
                    configured=True,
                    severity="warning",
                    missing_env=[],
                    notes=[],
                )
            ],
        ),
    )

    report = automation_usage_service.run_provider_auto_heal(
        required_providers=["openrouter"],
        max_rounds=2,
    )
    assert report["all_healthy"] is True
    assert report["blocking_issues"] == []
    row = report["providers"][0]
    assert row["provider"] == "openrouter"
    assert row["healed"] is True
    assert row["status"] == "ok"
    assert row["strategies_tried"] == ["direct_probe", "refresh_and_reprobe"]
    assert probe_calls["count"] == 2


@pytest.mark.asyncio
async def test_provider_auto_heal_run_endpoint_passes_query_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_auto_heal(
        *,
        required_providers: list[str] | None = None,
        max_rounds: int = 2,
        runtime_window_seconds: int = 86400,
        min_execution_events: int = 1,
    ) -> dict:
        captured["required_providers"] = required_providers
        captured["max_rounds"] = max_rounds
        captured["runtime_window_seconds"] = runtime_window_seconds
        captured["min_execution_events"] = min_execution_events
        return {
            "required_providers": required_providers or [],
            "external_provider_count": len(required_providers or []),
            "max_rounds": max_rounds,
            "all_healthy": True,
            "blocking_issues": [],
            "providers": [],
        }

    monkeypatch.setattr(automation_usage_service, "run_provider_auto_heal", _fake_auto_heal)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/automation/usage/provider-heal/run",
            params={
                "required_providers": "openrouter,github",
                "max_rounds": 3,
                "runtime_window_seconds": 7200,
                "min_execution_events": 2,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["all_healthy"] is True
    assert captured == {
        "required_providers": ["openrouter", "github"],
        "max_rounds": 3,
        "runtime_window_seconds": 7200,
        "min_execution_events": 2,
    }


@pytest.mark.asyncio
async def test_provider_validation_infers_openclaw_and_openai_codex_from_runtime_event_metadata(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    required = ["openai-codex", "openclaw"]
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
        event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 1500.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "task_id": "task_openclaw_infer",
                    "executor": "openclaw",
                    "model": "openclaw/gpt-5.1-codex",
                    "repeatable_tool_call": 'codex exec "demo" --json',
                    "tracking_kind": "agent_task_completion",
                },
            },
        )
        assert event.status_code == 201

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
        rows = {row["provider"]: row for row in payload["providers"]}
        assert rows["openai-codex"]["usage_events"] >= 1
        assert rows["openai-codex"]["validated_execution"] is True
        assert rows["openclaw"]["usage_events"] >= 1
        assert rows["openclaw"]["validated_execution"] is True


@pytest.mark.asyncio
async def test_provider_validation_infers_clawwork_executor_alias_as_openclaw(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", str(tmp_path / "automation_usage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    required = ["openai-codex", "openclaw"]
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
        event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 1500.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "task_id": "task_clawwork_infer",
                    "executor": "clawwork",
                    "model": "clawwork/gpt-5.1-codex",
                    "repeatable_tool_call": 'codex exec "demo" --json',
                    "tracking_kind": "agent_task_completion",
                },
            },
        )
        assert event.status_code == 201

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
        rows = {row["provider"]: row for row in payload["providers"]}
        assert rows["openai-codex"]["usage_events"] >= 1
        assert rows["openai-codex"]["validated_execution"] is True
        assert rows["openclaw"]["usage_events"] >= 1
        assert rows["openclaw"]["validated_execution"] is True


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
