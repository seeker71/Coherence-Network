from __future__ import annotations

from datetime import datetime, timezone

from app.routers import agent_monitor_helpers


def test_stale_pending_backlog_emits_dormant_tending_issue(set_config) -> None:
    set_config("pipeline", "pending_actionable_window_seconds", 86400)
    status = {
        "running": [],
        "pending": [
            {"id": "task_old", "wait_seconds": 1_984_714},
        ],
        "attention": {},
    }

    issues = agent_monitor_helpers.derive_monitor_issues_from_pipeline_status(
        status,
        now=datetime.now(timezone.utc),
    )

    assert [issue["condition"] for issue in issues] == ["dormant_pending_backlog"]
    assert issues[0]["severity"] == "medium"


def test_recent_pending_without_runner_still_emits_runner_down_issue(set_config) -> None:
    set_config("pipeline", "pending_actionable_window_seconds", 86400)
    status = {
        "running": [],
        "pending": [
            {"id": "task_recent", "wait_seconds": 700},
        ],
        "attention": {},
    }

    issues = agent_monitor_helpers.derive_monitor_issues_from_pipeline_status(
        status,
        now=datetime.now(timezone.utc),
    )

    assert [issue["condition"] for issue in issues] == ["no_task_running"]
    assert "1 actionable pending" in issues[0]["message"]


def test_fallback_status_marks_dormant_pending_as_attention(set_config, monkeypatch) -> None:
    set_config("pipeline", "pending_actionable_window_seconds", 86400)
    status = {
        "running": [],
        "pending": [
            {"id": "task_old", "wait_seconds": 1_984_714},
        ],
        "recent_completed": [],
        "attention": {},
        "project_manager": {},
    }
    monkeypatch.setattr(agent_monitor_helpers.agent_service, "get_pipeline_status", lambda: status)

    payload = agent_monitor_helpers.build_fallback_status_report(
        now=datetime.now(timezone.utc),
        fallback_reason="missing_status_report_file",
        monitor_payload={
            "issues": agent_monitor_helpers.derive_monitor_issues_from_pipeline_status(
                status,
                now=datetime.now(timezone.utc),
            )
        },
        effectiveness=None,
    )

    assert payload["layer_1_orchestration"]["status"] == "ok"
    assert payload["layer_2_execution"]["dormant_pending_count"] == 1
    assert payload["layer_2_execution"]["actionable_pending_count"] == 0
    assert payload["overall"]["needs_attention"] == ["dormant_pending_backlog"]


def test_low_success_rate_issue_digests_metrics(monkeypatch) -> None:
    def fake_aggregates() -> dict:
        return {
            "success_rate": {"completed": 22, "failed": 12, "total": 34, "rate": 0.65},
            "by_task_type": {
                "impl": {"completed": 8, "failed": 11, "success_rate": 0.42},
                "test": {"completed": 0, "failed": 1, "success_rate": 0.0},
                "spec": {"completed": 14, "failed": 0, "success_rate": 1.0},
            },
        }

    import app.services.metrics_service as metrics_service

    monkeypatch.setattr(metrics_service, "get_aggregates", fake_aggregates)
    status = {
        "running": [{"id": "task_running", "running_seconds": 1}],
        "pending": [],
        "attention": {"low_success_rate": True},
        "diagnostics": {
            "recent_failed_reasons": [
                {"reason": "spec_gate", "count": 6},
                {"reason": "no_code", "count": 2},
            ],
            "recent_failed_signatures": [
                {"signature": "impl_without_active_spec", "count": 6},
            ],
        },
    }

    issues = agent_monitor_helpers.derive_monitor_issues_from_pipeline_status(
        status,
        now=datetime.now(timezone.utc),
    )

    assert [issue["condition"] for issue in issues] == ["low_success_rate"]
    assert "65%" in issues[0]["message"]
    assert "22 completed / 12 failed / 34 resolved" in issues[0]["message"]
    assert "impl 42% (8/11)" in issues[0]["message"]
    assert "Recent failure buckets: spec_gate x6, no_code x2" in issues[0]["message"]
    assert "Top signatures: impl_without_active_spec x6" in issues[0]["message"]
    assert "Digest recent impl failures first" in issues[0]["suggested_action"]
