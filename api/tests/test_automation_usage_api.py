from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import TaskStatus, TaskType
from app.models.automation_usage import (
    ProviderReadinessReport,
    ProviderReadinessRow,
    UsageMetric,
    ProviderUsageOverview,
    ProviderUsageSnapshot,
)
from app.services import agent_service, automation_usage_service, quality_awareness_service, telemetry_persistence_service


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


def test_codex_oauth_access_context_reads_access_token_and_account(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text(
        json.dumps(
            {
                "auth_mode": "oauth",
                "tokens": {
                    "access_token": "access-token-123",
                    "account_id": "account-456",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))

    token, account_id, source = automation_usage_service._codex_oauth_access_context()
    assert token == "access-token-123"
    assert account_id == "account-456"
    assert source == f"session_file:{session_file}"


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


def test_limit_coverage_summary_marks_required_provider_without_validated_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = [
        ProviderUsageSnapshot(
            id="provider_openrouter_limit_gap",
            provider="openrouter",
            kind="custom",
            status="ok",
            data_source="provider_api",
            metrics=[
                UsageMetric(
                    id="requests_quota",
                    label="OpenRouter request quota",
                    unit="requests",
                    used=40.0,
                    remaining=60.0,
                    limit=100.0,
                    window="daily",
                    validation_state="derived",
                    evidence_source="runtime_events+env_limits",
                )
            ],
        ),
        ProviderUsageSnapshot(
            id="provider_openai_hard_ready",
            provider="openai",
            kind="openai",
            status="ok",
            data_source="provider_api",
            metrics=[
                UsageMetric(
                    id="requests_quota",
                    label="OpenAI request quota",
                    unit="requests",
                    used=10.0,
                    remaining=90.0,
                    limit=100.0,
                    window="minute",
                    validation_state="validated",
                    evidence_source="provider_rate_limit_headers",
                )
            ],
        ),
    ]
    monkeypatch.setattr(automation_usage_service, "_required_providers_from_env", lambda: ["openrouter"])
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {"openrouter": 2})

    summary = automation_usage_service._limit_coverage_summary(
        providers,
        required_providers=["openrouter"],
        active_usage_counts={"openrouter": 2},
    )

    assert summary["providers_with_validated_remaining_metrics"] == 1
    assert summary["hard_limit_claim_ready"] is False
    assert "openrouter" in summary["required_or_active_missing_hard_limit_telemetry"]
    status = summary["required_or_active_provider_status"]["openrouter"]
    assert status["required"] is True
    assert status["state"] == "derived_or_unvalidated"
    assert status["has_validated_remaining"] is False


def test_provider_readiness_can_block_on_limit_telemetry_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_openrouter_limit_gap",
                provider="openrouter",
                kind="custom",
                status="ok",
                data_source="provider_api",
                metrics=[
                    UsageMetric(
                        id="requests_quota",
                        label="OpenRouter request quota",
                        unit="requests",
                        used=80.0,
                        remaining=20.0,
                        limit=100.0,
                        window="daily",
                        validation_state="derived",
                        evidence_source="runtime_events+env_limits",
                    )
                ],
            )
        ],
        unavailable_providers=[],
        tracked_providers=1,
        limit_coverage={},
    )
    monkeypatch.setenv("AUTOMATION_PROVIDER_READINESS_BLOCK_ON_LIMIT_TELEMETRY", "1")
    monkeypatch.setenv("AUTOMATION_REQUIRE_KEYS_FOR_ACTIVE_PROVIDERS", "0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: overview,
    )
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {"openrouter": 1})

    report = automation_usage_service.provider_readiness_report(
        required_providers=["openrouter"],
        force_refresh=False,
    )

    assert report.all_required_ready is False
    assert "openrouter: limit_telemetry_state=derived_or_unvalidated" in report.blocking_issues
    assert "openrouter" in report.limit_telemetry["required_or_active_missing_hard_limit_telemetry"]
    provider_row = next(row for row in report.providers if row.provider == "openrouter")
    assert "limit_telemetry_state=derived_or_unvalidated" in provider_row.notes


def test_required_providers_include_cursor_when_cursor_executor_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOMATION_REQUIRED_PROVIDERS", "coherence-internal,openai")
    monkeypatch.setenv("AGENT_EXECUTOR_DEFAULT", "cursor")
    required = automation_usage_service._required_providers_from_env()
    assert "cursor" in required


def test_build_cursor_snapshot_includes_subscription_window_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        automation_usage_service,
        "_configured_status",
        lambda provider: (True, [], ["CURSOR_CLI_MODEL"], []) if provider == "cursor" else (False, [], [], []),
    )
    monkeypatch.setenv("CURSOR_SUBSCRIPTION_8H_LIMIT", "100")
    monkeypatch.setenv("CURSOR_SUBSCRIPTION_WEEK_LIMIT", "700")
    monkeypatch.setattr(automation_usage_service.shutil, "which", lambda name: "/usr/local/bin/agent" if name == "agent" else None)
    monkeypatch.setattr(automation_usage_service, "_cli_output", lambda command: (True, "agent 1.2.3"))

    def _fake_window_counts(window_seconds: int) -> int:
        if window_seconds == 8 * 60 * 60:
            return 70
        if window_seconds == 7 * 24 * 60 * 60:
            return 280
        return 0

    monkeypatch.setattr(automation_usage_service, "_cursor_events_within_window", _fake_window_counts)

    snapshot = automation_usage_service._build_cursor_snapshot()
    metrics = {row.id: row for row in snapshot.metrics}
    assert snapshot.provider == "cursor"
    assert snapshot.status == "ok"
    assert "cursor_subscription_8h" in metrics
    assert "cursor_subscription_week" in metrics
    assert metrics["cursor_subscription_8h"].remaining == pytest.approx(30.0, rel=1e-6)
    assert metrics["cursor_subscription_week"].remaining == pytest.approx(420.0, rel=1e-6)
    assert snapshot.data_source == "provider_cli"


def test_append_codex_subscription_metrics_includes_5h_and_week_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = ProviderUsageSnapshot(
        id="provider_openai_codex_test",
        provider="openai-codex",
        kind="custom",
        status="ok",
        data_source="runtime_events",
        metrics=[],
    )
    monkeypatch.setenv("CODEX_SUBSCRIPTION_5H_LIMIT", "100")
    monkeypatch.setenv("CODEX_SUBSCRIPTION_WEEK_LIMIT", "700")

    def _fake_codex_counts(window_seconds: int) -> int:
        if window_seconds == 5 * 60 * 60:
            return 40
        if window_seconds == 7 * 24 * 60 * 60:
            return 280
        return 0

    monkeypatch.setattr(
        automation_usage_service,
        "_codex_provider_usage_payload",
        lambda force_refresh=False: {"status": "unavailable", "windows": [], "error": ""},
    )
    monkeypatch.setattr(automation_usage_service, "_codex_events_within_window", _fake_codex_counts)
    automation_usage_service._append_codex_subscription_metrics(snapshot)
    metrics = {row.id: row for row in snapshot.metrics}
    assert "codex_subscription_5h" in metrics
    assert "codex_subscription_week" in metrics
    assert metrics["codex_subscription_5h"].remaining == pytest.approx(60.0, rel=1e-6)
    assert metrics["codex_subscription_week"].remaining == pytest.approx(420.0, rel=1e-6)
    assert metrics["codex_subscription_5h"].validation_state == "derived"
    assert metrics["codex_subscription_5h"].evidence_source == "runtime_events+env_limits"


def test_append_codex_subscription_metrics_tracks_usage_without_limit_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = ProviderUsageSnapshot(
        id="provider_openai_codex_usage_only",
        provider="openai",
        kind="openai",
        status="ok",
        data_source="runtime_events",
        metrics=[],
    )
    monkeypatch.delenv("CODEX_SUBSCRIPTION_5H_LIMIT", raising=False)
    monkeypatch.delenv("CODEX_SUBSCRIPTION_WEEK_LIMIT", raising=False)

    def _fake_codex_counts(window_seconds: int) -> int:
        if window_seconds == 5 * 60 * 60:
            return 11
        if window_seconds == 7 * 24 * 60 * 60:
            return 52
        return 0

    monkeypatch.setattr(
        automation_usage_service,
        "_codex_provider_usage_payload",
        lambda force_refresh=False: {"status": "unavailable", "windows": [], "error": ""},
    )
    monkeypatch.setattr(automation_usage_service, "_codex_events_within_window", _fake_codex_counts)
    automation_usage_service._append_codex_subscription_metrics(snapshot)

    metrics = {row.id: row for row in snapshot.metrics}
    assert "codex_subscription_5h" in metrics
    assert "codex_subscription_week" in metrics
    assert metrics["codex_subscription_5h"].used == pytest.approx(11.0, rel=1e-6)
    assert metrics["codex_subscription_week"].used == pytest.approx(52.0, rel=1e-6)
    assert metrics["codex_subscription_5h"].limit is None
    assert metrics["codex_subscription_5h"].remaining is None
    assert metrics["codex_subscription_5h"].validation_state == "derived"
    assert metrics["codex_subscription_5h"].evidence_source == "runtime_events"
    assert any("Codex subscription limits vary by plan and demand" in note for note in snapshot.notes)


def test_append_codex_subscription_metrics_adds_provider_api_windows_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = ProviderUsageSnapshot(
        id="provider_openai_codex_provider_windows",
        provider="openai",
        kind="openai",
        status="ok",
        data_source="provider_api",
        metrics=[],
    )
    monkeypatch.delenv("CODEX_SUBSCRIPTION_5H_LIMIT", raising=False)
    monkeypatch.delenv("CODEX_SUBSCRIPTION_WEEK_LIMIT", raising=False)
    monkeypatch.setattr(
        automation_usage_service,
        "_codex_provider_usage_payload",
        lambda force_refresh=False: {
            "status": "ok",
            "usage_url": "https://chatgpt.com/backend-api/wham/usage",
            "auth_source": "session_file:/tmp/codex-auth.json",
            "plan": "plus",
            "windows": [
                {
                    "metric_id": "codex_provider_window_primary",
                    "source_key": "primary_window",
                    "label": "5h",
                    "window": "5h",
                    "used_percent": 25.0,
                    "remaining_percent": 75.0,
                    "limit_window_seconds": 5 * 60 * 60,
                    "reset_at_unix": 1_700_000_000,
                    "reset_at_iso": "2023-11-14T22:13:20Z",
                },
                {
                    "metric_id": "codex_provider_window_secondary",
                    "source_key": "secondary_window",
                    "label": "7d",
                    "window": "7d",
                    "used_percent": 40.0,
                    "remaining_percent": 60.0,
                    "limit_window_seconds": 7 * 24 * 60 * 60,
                    "reset_at_unix": 1_700_060_000,
                    "reset_at_iso": "2023-11-15T14:53:20Z",
                },
            ],
            "error": "",
        },
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_codex_events_within_window",
        lambda window_seconds: 8 if window_seconds == 5 * 60 * 60 else 20,
    )

    automation_usage_service._append_codex_subscription_metrics(snapshot)

    metrics = {row.id: row for row in snapshot.metrics}
    assert metrics["codex_provider_window_primary"].validation_state == "validated"
    assert metrics["codex_provider_window_primary"].limit == pytest.approx(100.0, rel=1e-6)
    assert metrics["codex_provider_window_primary"].remaining == pytest.approx(75.0, rel=1e-6)
    assert metrics["codex_provider_window_primary"].evidence_source == "provider_api_wham_usage"
    assert metrics["codex_provider_window_secondary"].remaining == pytest.approx(60.0, rel=1e-6)
    assert metrics["codex_subscription_5h"].used == pytest.approx(8.0, rel=1e-6)
    assert metrics["codex_subscription_week"].used == pytest.approx(20.0, rel=1e-6)
    assert not any("Set CODEX_SUBSCRIPTION_5H_LIMIT" in note for note in snapshot.notes)
    assert snapshot.raw["codex_usage_plan"] == "plus"
    assert len(snapshot.raw["codex_usage_windows"]) == 2


def test_parse_codex_usage_windows_maps_primary_and_secondary() -> None:
    payload = {
        "rate_limit": {
            "primary_window": {
                "limit_window_seconds": 18_000,
                "used_percent": 12,
                "reset_at": 1_700_000_100,
            },
            "secondary_window": {
                "limit_window_seconds": 604_800,
                "used_percent": 55.5,
                "reset_at": 1_700_700_100,
            },
        }
    }
    windows = automation_usage_service._parse_codex_usage_windows(payload)
    assert len(windows) == 2
    primary = next(row for row in windows if row["metric_id"] == "codex_provider_window_primary")
    secondary = next(row for row in windows if row["metric_id"] == "codex_provider_window_secondary")
    assert primary["label"] == "5h"
    assert primary["remaining_percent"] == pytest.approx(88.0, rel=1e-6)
    assert secondary["label"] == "7d"
    assert secondary["remaining_percent"] == pytest.approx(44.5, rel=1e-6)
    assert primary["reset_at_iso"].endswith("Z")
    assert secondary["reset_at_iso"].endswith("Z")


def test_codex_events_within_window_ignores_agent_completion_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        SimpleNamespace(
            endpoint="/tool:codex",
            metadata={"is_openai_codex": True, "task_id": "task-1"},
        ),
        SimpleNamespace(
            endpoint="/tool:agent-task-completion",
            metadata={"is_openai_codex": True, "task_id": "task-1"},
        ),
        SimpleNamespace(
            endpoint="/tool:codex",
            metadata={
                "provider": "openai-codex",
                "model": "openclaw/gpt-5.3-codex-spark",
                "task_id": "task-2",
            },
        ),
        SimpleNamespace(
            endpoint="/tool:agent-task-completion",
            metadata={"provider": "openai-codex", "task_id": "task-2"},
        ),
        SimpleNamespace(
            endpoint="/tool:agent",
            metadata={"model": "gpt-5.3-codex", "executor": "codex"},
        ),
    ]
    monkeypatch.setattr(
        automation_usage_service,
        "_runtime_events_within_window",
        lambda window_seconds, source=None, limit=5000: events,
    )

    assert automation_usage_service._codex_events_within_window(5 * 60 * 60) == 3


def test_build_db_host_snapshot_includes_window_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example.net:5432/coherence")
    monkeypatch.setenv("DB_HOST_5H_LIMIT", "1000")
    monkeypatch.setenv("DB_HOST_WEEK_LIMIT", "5000")
    monkeypatch.setattr(
        automation_usage_service,
        "_build_db_host_monthly_egress_metric",
        lambda **kwargs: (None, {"egress_measurement_mode": "runtime_event_proxy"}, []),
    )

    def _fake_runtime_events_within_window(*, window_seconds: int, source: str | None = None, limit: int = 5000):
        assert source == "api"
        if window_seconds == 5 * 60 * 60:
            return [object()] * 125
        if window_seconds == 7 * 24 * 60 * 60:
            return [object()] * 640
        return [object()] * 320

    monkeypatch.setattr(automation_usage_service, "_runtime_events_within_window", _fake_runtime_events_within_window)

    snapshot = automation_usage_service._build_db_host_snapshot()
    assert snapshot.provider == "db-host"
    assert snapshot.status == "ok"
    metrics = {row.id: row for row in snapshot.metrics}
    assert "api_events_24h" in metrics
    assert "db_host_window_5h" in metrics
    assert "db_host_window_week" in metrics
    assert metrics["db_host_window_5h"].remaining == pytest.approx(875.0, rel=1e-6)
    assert metrics["db_host_window_week"].remaining == pytest.approx(4360.0, rel=1e-6)


def test_build_db_host_snapshot_includes_monthly_egress_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example.net:5432/coherence")
    monkeypatch.setenv("DB_HOST_5H_LIMIT", "1000")
    monkeypatch.setenv("DB_HOST_WEEK_LIMIT", "5000")

    monthly_metric = UsageMetric(
        id="db_host_egress_monthly_estimated",
        label="DB host estimated egress (monthly)",
        unit="gb",
        used=3.5,
        remaining=1.5,
        limit=5.0,
        window="monthly",
        validation_state="inferred",
        evidence_source="pg_stat_database+telemetry_meta",
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_build_db_host_monthly_egress_metric",
        lambda **kwargs: (
            monthly_metric,
            {"egress_measurement_mode": "pg_stat_database_delta_estimate"},
            ["monthly estimator active"],
        ),
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_runtime_events_within_window",
        lambda **kwargs: [object()] * 10,
    )

    snapshot = automation_usage_service._build_db_host_snapshot()
    metrics = {row.id: row for row in snapshot.metrics}
    assert snapshot.data_source == "provider_api"
    assert "db_host_egress_monthly_estimated" in metrics
    assert metrics["db_host_egress_monthly_estimated"].remaining == pytest.approx(1.5, rel=1e-6)
    assert snapshot.raw["egress_measurement_mode"] == "pg_stat_database_delta_estimate"


def test_summary_metric_prefers_limit_window_over_runtime_total() -> None:
    runtime = UsageMetric(
        id="runtime_task_runs",
        label="Runtime task runs",
        unit="tasks",
        used=180.0,
        remaining=None,
        limit=None,
        window="rolling",
    )
    limited = UsageMetric(
        id="codex_subscription_5h",
        label="Codex task runs (5h)",
        unit="requests",
        used=180.0,
        remaining=320.0,
        limit=500.0,
        window="hourly",
    )
    selected = automation_usage_service._summary_metric([runtime, limited])
    assert selected is not None
    assert selected.id == "codex_subscription_5h"


def test_summary_metric_prefers_validated_limited_metric_over_derived_limit() -> None:
    derived = UsageMetric(
        id="codex_subscription_5h",
        label="Codex task runs (5h)",
        unit="requests",
        used=16.0,
        remaining=484.0,
        limit=500.0,
        window="hourly",
        validation_state="derived",
        evidence_source="runtime_events+env_limits",
    )
    validated = UsageMetric(
        id="requests_quota",
        label="OpenAI request quota",
        unit="requests",
        used=20.0,
        remaining=980.0,
        limit=1000.0,
        window="minute",
        validation_state="validated",
        evidence_source="provider_rate_limit_headers",
    )
    selected = automation_usage_service._summary_metric([derived, validated])
    assert selected is not None
    assert selected.id == "requests_quota"


def test_summary_metric_prefers_db_monthly_egress_over_db_window_proxy() -> None:
    monthly = UsageMetric(
        id="db_host_egress_monthly_estimated",
        label="DB host estimated egress (monthly)",
        unit="gb",
        used=4.2,
        remaining=0.8,
        limit=5.0,
        window="monthly",
        validation_state="inferred",
    )
    proxy_window = UsageMetric(
        id="db_host_window_5h",
        label="DB host request window (5h)",
        unit="requests",
        used=200.0,
        remaining=50.0,
        limit=250.0,
        window="hourly",
        validation_state="derived",
    )
    selected = automation_usage_service._summary_metric([proxy_window, monthly])
    assert selected is not None
    assert selected.id == "db_host_egress_monthly_estimated"


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
        assert "supabase" not in providers
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
async def test_automation_usage_endpoint_compact_mode_trims_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = [
        UsageMetric(
            id=f"metric_{idx}",
            label=f"Metric {idx}",
            unit="requests",
            used=float(idx),
            remaining=100.0 - float(idx),
            limit=100.0,
            window="daily",
            validation_detail="x" * 320,
        )
        for idx in range(30)
    ]
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(
                id="provider_dbhost_compact_test",
                provider="db-host",
                kind="custom",
                status="ok",
                data_source="provider_api",
                metrics=metrics,
                notes=["note " + ("n" * 220)] * 8,
                official_records=[f"https://example.com/doc/{idx}" for idx in range(8)],
                raw={
                    "database_host": "db.internal",
                    "database_name": "coherence",
                    "database_engine": "postgres",
                    "monthly_limit_gb": 5.0,
                    "extra_large_blob": "y" * 1000,
                },
            )
        ],
        unavailable_providers=[],
        tracked_providers=1,
        limit_coverage={"providers_considered": 1},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: overview,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compact = await client.get("/api/automation/usage", params={"compact": True, "include_raw": False})
        assert compact.status_code == 200
        compact_payload = compact.json()
        compact_provider = compact_payload["providers"][0]
        assert len(compact_provider["metrics"]) == 16
        assert all(len(str(row.get("validation_detail") or "")) <= 200 for row in compact_provider["metrics"])
        assert len(compact_provider["notes"]) == 4
        assert all(len(note) <= 180 for note in compact_provider["notes"])
        assert len(compact_provider["official_records"]) == 4
        assert compact_provider["raw"] == {}

        compact_with_raw = await client.get("/api/automation/usage", params={"compact": True, "include_raw": True})
        assert compact_with_raw.status_code == 200
        raw_payload = compact_with_raw.json()
        raw_provider = raw_payload["providers"][0]
        assert "database_host" in raw_provider["raw"]
        assert "extra_large_blob" not in raw_provider["raw"]


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
    monkeypatch.setattr(automation_usage_service, "_codex_oauth_available", lambda: (False, "missing_codex_oauth_session"))
    monkeypatch.setattr(automation_usage_service, "_active_provider_usage_counts", lambda: {})

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
    monkeypatch.setattr(automation_usage_service, "_probe_openai", lambda: (True, "ok"))
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


def test_provider_validation_run_supports_cursor_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automation_usage_service, "_probe_cursor", lambda: (True, "ok_cursor_cli:1.0.0"))
    monkeypatch.setattr(automation_usage_service, "_record_provider_probe_event", lambda **kwargs: None)

    report = automation_usage_service.run_provider_validation_probes(
        required_providers=["cursor"],
    )
    assert report["required_providers"] == ["cursor"]
    assert len(report["probes"]) == 1
    row = report["probes"][0]
    assert row["provider"] == "cursor"
    assert row["ok"] is True
    assert row["detail"].startswith("ok_cursor_cli:")


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


def test_provider_auto_heal_runs_cli_install_strategy_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_PROVIDER_HEAL_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(automation_usage_service, "_probe_cursor", lambda: (False, "cursor_cli_not_in_path"))
    monkeypatch.setattr(automation_usage_service, "_record_provider_heal_event", lambda **kwargs: None)
    monkeypatch.setattr(
        automation_usage_service,
        "_provider_cli_install_strategy",
        lambda provider, *, attempts, enable_cli_installs: (
            ("install_cli", lambda: (True, "install_cli_ok:agent:1.0.0"))
            if provider == "cursor" and enable_cli_installs and not attempts
            else None
        ),
    )

    report = automation_usage_service.run_provider_auto_heal(
        required_providers=["cursor"],
        max_rounds=1,
        enable_cli_installs=True,
    )
    assert report["all_healthy"] is True
    assert report["enable_cli_installs"] is True
    row = report["providers"][0]
    assert row["provider"] == "cursor"
    assert row["healed"] is True
    assert row["strategies_tried"] == ["direct_probe", "install_cli"]
    assert row["final_detail"].startswith("install_cli_ok:")


def test_provider_auto_heal_requires_cli_binary_when_install_mode_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_PROVIDER_HEAL_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(automation_usage_service, "_probe_cursor", lambda: (True, "ok_via_runtime_usage_no_cli"))
    monkeypatch.setattr(automation_usage_service, "_record_provider_heal_event", lambda **kwargs: None)
    monkeypatch.setattr(
        automation_usage_service,
        "_provider_cli_install_strategy",
        lambda provider, *, attempts, enable_cli_installs: (
            ("install_cli", lambda: (True, "install_cli_ok:agent:1.0.0"))
            if provider == "cursor" and enable_cli_installs and not attempts
            else None
        ),
    )

    report = automation_usage_service.run_provider_auto_heal(
        required_providers=["cursor"],
        max_rounds=1,
        enable_cli_installs=True,
    )
    assert report["all_healthy"] is True
    row = report["providers"][0]
    assert row["healed"] is True
    assert row["strategies_tried"] == ["direct_probe", "install_cli"]
    assert row["attempts"][0]["ok"] is False
    assert str(row["attempts"][0]["detail"]).startswith("cli_binary_required:")
    assert row["final_detail"].startswith("install_cli_ok:")


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
        enable_cli_installs: bool | None = None,
    ) -> dict:
        captured["required_providers"] = required_providers
        captured["max_rounds"] = max_rounds
        captured["runtime_window_seconds"] = runtime_window_seconds
        captured["min_execution_events"] = min_execution_events
        captured["enable_cli_installs"] = enable_cli_installs
        return {
            "required_providers": required_providers or [],
            "external_provider_count": len(required_providers or []),
            "max_rounds": max_rounds,
            "enable_cli_installs": bool(enable_cli_installs),
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
                "enable_cli_installs": True,
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
        "enable_cli_installs": True,
    }


def test_daily_summary_backfills_missing_host_failure_observability(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = True
    agent_service._store_loaded_path = str(agent_service._store_path())
    agent_service._store_loaded_test_context = os.getenv("PYTEST_CURRENT_TEST")
    now = agent_service._now()
    agent_service._store["task_gap_host_1"] = {
        "id": "task_gap_host_1",
        "direction": "legacy failed task missing telemetry",
        "task_type": TaskType.IMPL,
        "status": TaskStatus.FAILED,
        "model": "openclaw/openrouter/free",
        "command": "codex exec",
        "started_at": now,
        "output": "failed before friction contract",
        "context": {"executor": "openclaw"},
        "progress_pct": None,
        "current_step": None,
        "decision_prompt": None,
        "decision": None,
        "claimed_by": "openai-codex:railway-runner",
        "claimed_at": now,
        "created_at": now,
        "updated_at": now,
        "tier": "openrouter",
    }

    snapshot = ProviderUsageSnapshot(
        id="provider_coherence_internal_test",
        provider="coherence-internal",
        kind="custom",
        status="ok",
        data_source="runtime_events",
        metrics=[],
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_latest_provider_snapshots",
        lambda limit=800: {"coherence-internal": snapshot},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: ProviderUsageOverview(
            providers=[snapshot],
            unavailable_providers=[],
            tracked_providers=1,
            limit_coverage={},
        ),
    )

    summary = automation_usage_service.daily_system_summary(window_hours=24, top_n=3)
    backfill = summary["host_failure_observability_backfill"]
    assert backfill["host_failed_tasks"] >= 1
    assert backfill["completion_events_backfilled"] >= 1
    assert backfill["friction_events_backfilled"] >= 1
    assert summary["host_runner"]["failed_runs"] >= 1
    assert summary["friction"]["total_events"] >= 1
    assert not any("exceed friction events" in gap for gap in summary["contract_gaps"])


def test_daily_summary_includes_quality_awareness_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    quality_awareness_service._QUALITY_AWARENESS_CACHE["expires_at"] = 0.0
    quality_awareness_service._QUALITY_AWARENESS_CACHE["summary"] = None
    snapshot = ProviderUsageSnapshot(
        id="provider_coherence_internal_quality",
        provider="coherence-internal",
        kind="custom",
        status="ok",
        data_source="runtime_events",
        metrics=[],
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_latest_provider_snapshots",
        lambda limit=800: {"coherence-internal": snapshot},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: ProviderUsageOverview(
            providers=[snapshot],
            unavailable_providers=[],
            tracked_providers=1,
            limit_coverage={},
        ),
    )
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "load_baseline",
        lambda path: {},
    )
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "build_maintainability_audit",
        lambda baseline=None: {
            "generated_at": "2026-02-23T11:22:33Z",
            "summary": {
                "severity": "medium",
                "risk_score": 62,
                "regression": True,
                "regression_reasons": ["max_long_function_count: 12 > baseline 10"],
                "python_module_count": 120,
                "runtime_file_count": 210,
                "layer_violation_count": 1,
                "large_module_count": 2,
                "very_large_module_count": 1,
                "long_function_count": 12,
                "placeholder_count": 0,
            },
            "architecture": {
                "very_large_modules": [{"file": "api/app/services/automation_usage_service.py", "line_count": 2900}],
                "long_functions": [{"file": "api/app/services/runtime_service.py", "function": "heavy", "line_count": 140}],
                "layer_violations": [
                    {
                        "file": "api/app/models/runtime.py",
                        "forbidden_import": "app.services.agent_service",
                        "reason": "models should not depend on services/routers",
                    }
                ],
            },
            "placeholder_scan": {"findings": []},
            "recommended_tasks": [
                {
                    "task_id": "architecture-modularization-review",
                    "title": "Architecture modularization review",
                    "priority": "high",
                    "roi_estimate": 4.2,
                    "direction": "Split oversized files and remove cross-layer imports.",
                }
            ],
        },
    )

    summary = automation_usage_service.daily_system_summary(window_hours=24, top_n=3, force_refresh=True)
    quality = summary["quality_awareness"]
    assert quality["status"] == "ok"
    assert quality["summary"]["risk_score"] == 62
    assert quality["summary"]["regression"] is True
    assert quality["hotspots"]
    assert any("maintainability metrics regressed" in row for row in quality["guidance"])
    assert quality["recommended_tasks"][0]["task_id"] == "architecture-modularization-review"


def test_daily_summary_quality_awareness_falls_back_when_audit_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_awareness_service._QUALITY_AWARENESS_CACHE["expires_at"] = 0.0
    quality_awareness_service._QUALITY_AWARENESS_CACHE["summary"] = None
    snapshot = ProviderUsageSnapshot(
        id="provider_coherence_internal_quality_fallback",
        provider="coherence-internal",
        kind="custom",
        status="ok",
        data_source="runtime_events",
        metrics=[],
    )
    monkeypatch.setattr(
        automation_usage_service,
        "_latest_provider_snapshots",
        lambda limit=800: {"coherence-internal": snapshot},
    )
    monkeypatch.setattr(
        automation_usage_service,
        "collect_usage_overview",
        lambda force_refresh=False: ProviderUsageOverview(
            providers=[snapshot],
            unavailable_providers=[],
            tracked_providers=1,
            limit_coverage={},
        ),
    )
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "load_baseline",
        lambda path: {},
    )
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "build_maintainability_audit",
        lambda baseline=None: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    summary = automation_usage_service.daily_system_summary(window_hours=24, top_n=3, force_refresh=True)
    quality = summary["quality_awareness"]
    assert quality["status"] == "unavailable"
    assert quality["hotspots"] == []
    assert "audit unavailable" in quality["guidance"][0]


@pytest.mark.asyncio
async def test_daily_summary_endpoint_passes_query_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_daily_summary(
        *,
        window_hours: int = 24,
        top_n: int = 3,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        captured["window_hours"] = window_hours
        captured["top_n"] = top_n
        captured["force_refresh"] = force_refresh
        return {
            "generated_at": "2026-02-23T00:00:00Z",
            "window_hours": window_hours,
            "host_runner": {"total_runs": 1, "failed_runs": 0, "completed_runs": 1, "running_runs": 0, "pending_runs": 0, "by_task_type": {"impl": {"total": 1, "completed": 1}}},
            "execution": {"tracked_runs": 1, "failed_runs": 0, "success_runs": 1, "coverage": {"coverage_rate": 1.0}},
            "tool_usage": {"worker_events": 1, "worker_failed_events": 0, "top_tools": [{"tool": "tool:agent-task-completion", "events": 1, "failed": 0}]},
            "friction": {"total_events": 0, "open_events": 0, "top_block_types": [], "top_stages": [], "entry_points": []},
            "providers": [],
            "top_attention_areas": [],
            "contract_gaps": [],
            "quality_awareness": {
                "status": "ok",
                "generated_at": "2026-02-23T00:00:00Z",
                "intent_focus": ["trust", "clarity", "reuse"],
                "summary": {
                    "severity": "low",
                    "risk_score": 10,
                    "regression": False,
                    "regression_reasons": [],
                    "python_module_count": 10,
                    "runtime_file_count": 20,
                    "layer_violations": 0,
                    "large_modules": 0,
                    "very_large_modules": 0,
                    "long_functions": 0,
                    "placeholder_findings": 0,
                },
                "hotspots": [],
                "guidance": [],
                "recommended_tasks": [],
            },
        }

    monkeypatch.setattr(automation_usage_service, "daily_system_summary", _fake_daily_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/automation/usage/daily-summary",
            params={"window_hours": 12, "top_n": 5, "force_refresh": True},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 12
    assert payload["host_runner"]["total_runs"] == 1
    assert captured == {"window_hours": 12, "top_n": 5, "force_refresh": True}


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
        assert rows["openai"]["usage_events"] >= 1
        assert rows["openai"]["validated_execution"] is True
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
        assert rows["openai"]["usage_events"] >= 1
        assert rows["openai"]["validated_execution"] is True
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
