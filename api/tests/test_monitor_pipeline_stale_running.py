from __future__ import annotations

import logging

from scripts import monitor_pipeline


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _StaleClient:
    def __init__(self, running: list[dict], *, heal_task_id: str = "heal-orphan-1") -> None:
        self.running = running
        self.heal_task_id = heal_task_id
        self.post_calls: list[dict] = []
        self.patch_calls: list[dict] = []

    def get(self, url: str, timeout: int = 10):  # noqa: ARG002
        if url.endswith("/api/agent/pipeline-status"):
            return _Resp(
                200,
                {
                    "attention": {"low_success_rate": False},
                    "running": self.running,
                    "pending": [],
                    "project_manager": {"blocked": False},
                },
            )
        if url.endswith("/api/agent/metrics"):
            return _Resp(200, {})
        if url.endswith("/api/agent/effectiveness"):
            return _Resp(
                200,
                {
                    "plan_progress": {
                        "backlog_alignment": {"phase_6_7_not_worked": False},
                        "index": 1,
                        "total": 80,
                    }
                },
            )
        if url.endswith("/api/gates/public-deploy-contract"):
            return _Resp(200, {"result": "public_contract_passed"})
        raise AssertionError(f"unexpected url: {url}")

    def post(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        self.post_calls.append({"url": url, "json": json})
        if url.endswith("/api/agent/tasks"):
            return _Resp(201, {"id": self.heal_task_id})
        raise AssertionError(f"unexpected post url: {url}")

    def patch(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        self.patch_calls.append({"url": url, "json": json})
        return _Resp(200, {})


class _PaidSignalsClient:
    def get(self, url: str, timeout: int = 10):  # noqa: ARG002
        if url.endswith("/api/agent/pipeline-status"):
            return _Resp(
                200,
                {
                    "attention": {"low_success_rate": False},
                    "running": [],
                    "pending": [],
                    "project_manager": {"blocked": False},
                },
            )
        if url.endswith("/api/agent/metrics"):
            return _Resp(200, {})
        if url.endswith("/api/agent/effectiveness"):
            return _Resp(
                200,
                {
                    "plan_progress": {
                        "backlog_alignment": {"phase_6_7_not_worked": False},
                        "index": 1,
                        "total": 80,
                    }
                },
            )
        if url.endswith("/api/gates/public-deploy-contract"):
            return _Resp(200, {"result": "public_contract_passed"})
        if url.endswith("/api/automation/usage/alerts"):
            return _Resp(
                200,
                {
                    "alerts": [
                        {
                            "id": "a1",
                            "provider": "supabase",
                            "metric_id": "egress_quota",
                            "severity": "critical",
                            "message": "low remaining egress",
                        }
                    ]
                },
            )
        if "/api/automation/usage/readiness" in url:
            return _Resp(
                200,
                {
                    "all_required_ready": False,
                    "blocking_issues": ["supabase: status=degraded, configured=True"],
                },
            )
        if "/api/automation/usage/provider-validation" in url:
            return _Resp(
                200,
                {
                    "all_required_validated": False,
                    "blocking_issues": ["supabase: configured=True, readiness_status=degraded, successful_events=0/1"],
                },
            )
        if "/api/friction/events" in url:
            return _Resp(
                200,
                [
                    {
                        "event_id": "f1",
                        "block_type": "paid_provider_blocked",
                        "metadata": {"provider": "openrouter"},
                    }
                ],
            )
        raise AssertionError(f"unexpected url: {url}")

    def post(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        return _Resp(201, {"id": "noop-heal"})

    def patch(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        return _Resp(200, {})


def _set_common_monkeypatches(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(tmp_path / "monitor_issues.json"))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(
        monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(tmp_path / "github_actions_health.json")
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": False,
            "note": "disabled in test",
            "completed_runs": 0,
            "failed_runs": 0,
            "failure_rate": 0.0,
            "wasted_minutes_failed": 0.0,
            "sample_failed_run_links": [],
            "official_records": [],
        },
    )


def test_run_check_flags_running_task_stale_after_30m(monkeypatch, tmp_path) -> None:
    _set_common_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr(monitor_pipeline, "ORPHAN_RUNNING_SEC", 1800)
    client = _StaleClient([{"id": "task-running-1", "running_seconds": 1900}])

    payload = monitor_pipeline._run_check(
        client,
        logging.getLogger("test"),
        auto_fix=False,
        auto_recover=False,
    )

    orphan_issue = next((row for row in payload["issues"] if row["condition"] == "orphan_running"), None)
    assert orphan_issue is not None
    assert orphan_issue["severity"] == "high"
    assert "1800s" in orphan_issue["message"]
    assert "task-running-1" in orphan_issue["message"]
    assert client.patch_calls == []
    assert client.post_calls == []


def test_run_check_reaps_stale_running_tasks_and_triggers_heal_and_restart(monkeypatch, tmp_path) -> None:
    _set_common_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr(monitor_pipeline, "ORPHAN_RUNNING_SEC", 1800)
    monkeypatch.setenv("PIPELINE_AUTO_FIX_ENABLED", "1")

    restart_reasons: list[str] = []
    monkeypatch.setattr(monitor_pipeline, "_request_restart", lambda reason, _log: restart_reasons.append(reason))

    client = _StaleClient(
        [
            {"id": "task-running-a", "running_seconds": 4000},
            {"id": "task-running-b", "running_seconds": 2200},
        ]
    )

    payload = monitor_pipeline._run_check(
        client,
        logging.getLogger("test"),
        auto_fix=True,
        auto_recover=True,
    )

    orphan_issue = next((row for row in payload["issues"] if row["condition"] == "orphan_running"), None)
    assert orphan_issue is not None
    assert orphan_issue.get("heal_task_id") == "heal-orphan-1"
    assert "Restart requested" in orphan_issue["suggested_action"]
    assert restart_reasons == ["stale_running_orphan"]

    assert len(client.patch_calls) == 2
    patched_urls = {row["url"] for row in client.patch_calls}
    assert any(url.endswith("/api/agent/tasks/task-running-a") for url in patched_urls)
    assert any(url.endswith("/api/agent/tasks/task-running-b") for url in patched_urls)
    assert all((row["json"] or {}).get("status") == "failed" for row in client.patch_calls)

    heal_posts = [row for row in client.post_calls if row["url"].endswith("/api/agent/tasks")]
    assert len(heal_posts) == 1
    heal_context = (heal_posts[0]["json"] or {}).get("context") or {}
    assert heal_context.get("monitor_condition") == "orphan_running"


def test_run_check_flags_paid_service_awareness_issues(monkeypatch, tmp_path) -> None:
    _set_common_monkeypatches(monkeypatch, tmp_path)
    client = _PaidSignalsClient()

    payload = monitor_pipeline._run_check(
        client,
        logging.getLogger("test"),
        auto_fix=False,
        auto_recover=False,
    )

    conditions = {row["condition"] for row in payload["issues"]}
    assert "paid_service_usage_alerts" in conditions
    assert "paid_service_readiness_blocked" in conditions
    assert "paid_service_validation_blocked" in conditions
    assert "paid_provider_blocked_friction" in conditions
