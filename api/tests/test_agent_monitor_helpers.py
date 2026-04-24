from __future__ import annotations

from datetime import datetime, timezone

from app.routers import agent_monitor_helpers


def test_stale_pending_backlog_does_not_emit_runner_down_issue(set_config) -> None:
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

    assert [issue["condition"] for issue in issues] == []


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


def test_fallback_status_marks_dormant_pending_without_attention(set_config, monkeypatch) -> None:
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
        monitor_payload={"issues": []},
        effectiveness=None,
    )

    assert payload["layer_1_orchestration"]["status"] == "ok"
    assert payload["layer_2_execution"]["dormant_pending_count"] == 1
    assert payload["layer_2_execution"]["actionable_pending_count"] == 0
