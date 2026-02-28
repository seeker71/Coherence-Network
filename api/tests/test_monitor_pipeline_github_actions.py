from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from scripts import monitor_pipeline


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _Client:
    def get(self, url: str, timeout: int = 10):  # noqa: ARG002
        if url.endswith("/api/agent/pipeline-status"):
            return _Resp(
                200,
                {
                    "attention": {"low_success_rate": False},
                    "running": [{"id": "task-running-1", "running_seconds": 30}],
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
                        "index": 60,
                        "total": 80,
                    }
                },
            )
        raise AssertionError(f"unexpected url: {url}")

    def post(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        if url.endswith("/api/agent/tasks"):
            return _Resp(201, {"id": "heal-ci-123"})
        raise AssertionError(f"unexpected post url: {url}")

    def patch(self, url: str, json: dict | None = None, timeout: int = 10):  # noqa: ARG002
        raise AssertionError(f"unexpected patch url: {url}")


def test_collect_github_actions_health_parses_completed_runs(monkeypatch) -> None:
    monkeypatch.setattr(monitor_pipeline, "_github_repo_slug", lambda: "seeker71/Coherence-Network")
    now = datetime.now(timezone.utc)
    created = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    started = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    updated = (now - timedelta(hours=1, minutes=55)).isoformat().replace("+00:00", "Z")
    payload = {
        "workflow_runs": [
            {
                "status": "completed",
                "conclusion": "failure",
                "created_at": created,
                "run_started_at": started,
                "updated_at": updated,
                "name": "test",
                "html_url": "https://github.com/seeker71/Coherence-Network/actions/runs/1",
            },
            {
                "status": "completed",
                "conclusion": "success",
                "created_at": created,
                "run_started_at": started,
                "updated_at": updated,
                "name": "validate",
                "html_url": "https://github.com/seeker71/Coherence-Network/actions/runs/2",
            },
        ]
    }

    class _RunResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(args, **kwargs):  # noqa: ANN001, ARG001
        if args[:3] == ["gh", "auth", "status"]:
            return _RunResult(0, "")
        if args[:3] == ["gh", "api", "repos/seeker71/Coherence-Network/actions/runs"]:
            return _RunResult(0, json.dumps(payload))
        raise AssertionError(f"unexpected subprocess args: {args}")

    monkeypatch.setattr("subprocess.run", _fake_run)
    health = monitor_pipeline._collect_github_actions_health(logging.getLogger("test"))
    assert health["available"] is True
    assert health["completed_runs"] == 2
    assert health["failed_runs"] == 1
    assert health["failure_rate"] == 0.5
    assert health["sample_failed_run_links"] == [
        "https://github.com/seeker71/Coherence-Network/actions/runs/1"
    ]
    assert any("github.com/seeker71/Coherence-Network/actions" in link for link in health["official_records"])


def test_run_check_tracks_high_github_actions_failure_rate(tmp_path, monkeypatch) -> None:
    issues_file = tmp_path / "monitor_issues.json"
    gha_file = tmp_path / "github_actions_health.json"
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(issues_file))
    monkeypatch.setattr(monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(gha_file))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": True,
            "repo": "seeker71/Coherence-Network",
            "completed_runs": 12,
            "failed_runs": 7,
            "failure_rate": 0.5833,
            "wasted_minutes_failed": 29.1,
            "sample_failed_run_links": ["https://github.com/seeker71/Coherence-Network/actions/runs/100"],
            "official_records": ["https://github.com/seeker71/Coherence-Network/actions"],
        },
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)
    monkeypatch.setenv("PIPELINE_AUTO_FIX_ENABLED", "1")

    payload = monitor_pipeline._run_check(_Client(), logging.getLogger("test"), auto_fix=True, auto_recover=False)
    conditions = {row["condition"] for row in payload["issues"]}
    assert "github_actions_high_failure_rate" in conditions
    assert gha_file.exists()
    persisted = json.loads(gha_file.read_text(encoding="utf-8"))
    assert persisted["failure_rate"] == 0.5833


def test_run_check_marks_github_actions_issue_resolved_when_rate_drops(tmp_path, monkeypatch) -> None:
    issues_file = tmp_path / "monitor_issues.json"
    issues_file.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "prev1",
                        "condition": "github_actions_high_failure_rate",
                        "severity": "high",
                        "priority": 1,
                        "message": "old",
                        "suggested_action": "old",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "resolved_at": None,
                    }
                ],
                "last_check": None,
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(issues_file))
    monkeypatch.setattr(monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(tmp_path / "gha.json"))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": True,
            "repo": "seeker71/Coherence-Network",
            "completed_runs": 12,
            "failed_runs": 1,
            "failure_rate": 0.08,
            "wasted_minutes_failed": 1.2,
            "sample_failed_run_links": [],
            "official_records": ["https://github.com/seeker71/Coherence-Network/actions"],
        },
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)

    payload = monitor_pipeline._run_check(_Client(), logging.getLogger("test"), auto_fix=False, auto_recover=False)
    assert "github_actions_high_failure_rate" not in {row["condition"] for row in payload["issues"]}
    assert "github_actions_high_failure_rate" in payload["resolved_since_last"]


def test_collect_github_actions_health_enriches_owner_and_waiver_data(tmp_path, monkeypatch) -> None:
    owners_path = tmp_path / "owners.json"
    waivers_path = tmp_path / "waivers.json"
    owners_path.write_text(
        json.dumps({"workflow_owners": {"test": "@owner"}}),
        encoding="utf-8",
    )
    waivers_path.write_text(
        json.dumps(
            {
                "waivers": [
                    {
                        "workflow": "test",
                        "owner": "@owner",
                        "reason": "temporary",
                        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_pipeline, "START_GATE_WORKFLOW_OWNERS_FILE", str(owners_path))
    monkeypatch.setattr(monitor_pipeline, "START_GATE_MAIN_WAIVERS_FILE", str(waivers_path))
    monkeypatch.setattr(monitor_pipeline, "_github_repo_slug", lambda: "seeker71/Coherence-Network")
    now = datetime.now(timezone.utc)
    created = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    payload = {
        "workflow_runs": [
            {
                "status": "completed",
                "conclusion": "failure",
                "created_at": created,
                "run_started_at": created,
                "updated_at": created,
                "name": "test",
                "html_url": "https://github.com/seeker71/Coherence-Network/actions/runs/1",
            }
        ]
    }

    class _RunResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(args, **kwargs):  # noqa: ANN001, ARG001
        if args[:3] == ["gh", "auth", "status"]:
            return _RunResult(0, "")
        if args[:3] == ["gh", "api", "repos/seeker71/Coherence-Network/actions/runs"]:
            return _RunResult(0, json.dumps(payload))
        raise AssertionError(f"unexpected subprocess args: {args}")

    monkeypatch.setattr("subprocess.run", _fake_run)
    health = monitor_pipeline._collect_github_actions_health(logging.getLogger("test"))
    top = health["top_failed_workflows"][0]
    assert top["workflow"] == "test"
    assert top["owner"] == "@owner"
    assert top["active_waiver_count"] == 1
    assert health["active_waivers"]
    assert health["unowned_failed_workflows"] == []


def test_run_check_adds_issue_for_unowned_failed_workflows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(tmp_path / "monitor_issues.json"))
    monkeypatch.setattr(monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(tmp_path / "github_actions_health.json"))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": True,
            "repo": "seeker71/Coherence-Network",
            "completed_runs": 10,
            "failed_runs": 1,
            "failure_rate": 0.1,
            "wasted_minutes_failed": 0.2,
            "top_failed_workflows": [{"workflow": "unknown", "failed_runs": 1, "owner": "", "active_waiver_count": 0}],
            "unowned_failed_workflows": ["unknown"],
            "active_waivers": [],
            "sample_failed_run_links": [],
            "official_records": ["https://github.com/seeker71/Coherence-Network/actions"],
        },
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)

    payload = monitor_pipeline._run_check(_Client(), logging.getLogger("test"), auto_fix=False, auto_recover=False)
    assert "github_actions_unowned_workflow_failures" in {row["condition"] for row in payload["issues"]}


def test_run_check_flags_stale_ai_agent_intelligence_digest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(tmp_path / "monitor_issues.json"))
    monkeypatch.setattr(monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(tmp_path / "github_actions_health.json"))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": True,
            "repo": "seeker71/Coherence-Network",
            "completed_runs": 12,
            "failed_runs": 0,
            "failure_rate": 0.0,
            "wasted_minutes_failed": 0.0,
            "sample_failed_run_links": [],
            "official_records": [],
            "unowned_failed_workflows": [],
            "active_waivers": [],
        },
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)
    monkeypatch.setenv("AI_AGENT_INTELLIGENCE_MAX_AGE_DAYS", "14")

    stale_generated = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    digest_path = tmp_path / "ai_agent_biweekly_sources.json"
    digest_path.write_text(
        json.dumps({"generated_at": stale_generated, "sources": [{"url": "https://example.com"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "AI_AGENT_INTELLIGENCE_DIGEST_FILE",
        str(digest_path),
        raising=False,
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "AI_AGENT_SECURITY_WATCH_FILE",
        str(tmp_path / "ai_agent_security_watch.json"),
        raising=False,
    )

    payload = monitor_pipeline._run_check(_Client(), logging.getLogger("test"), auto_fix=False, auto_recover=False)
    assert "ai_agent_intelligence_stale" in {row["condition"] for row in payload["issues"]}


def test_run_check_flags_open_high_ai_agent_security_advisory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(monitor_pipeline, "ISSUES_FILE", str(tmp_path / "monitor_issues.json"))
    monkeypatch.setattr(monitor_pipeline, "GITHUB_ACTIONS_HEALTH_FILE", str(tmp_path / "github_actions_health.json"))
    monkeypatch.setattr(monitor_pipeline, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        monitor_pipeline,
        "PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE",
        str(tmp_path / "public_deploy_contract_block_state.json"),
    )
    monkeypatch.setattr(monitor_pipeline, "_get_current_git_sha", lambda: "")
    monkeypatch.setattr(
        monitor_pipeline,
        "_collect_github_actions_health",
        lambda _log: {
            "available": True,
            "repo": "seeker71/Coherence-Network",
            "completed_runs": 12,
            "failed_runs": 0,
            "failure_rate": 0.0,
            "wasted_minutes_failed": 0.0,
            "sample_failed_run_links": [],
            "official_records": [],
            "unowned_failed_workflows": [],
            "active_waivers": [],
        },
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "_get_pipeline_process_args",
        lambda: {"runner_workers": 5, "pm_parallel": True, "runner_seen": True, "pm_seen": True},
    )
    monkeypatch.setattr(monitor_pipeline, "_runner_log_has_recent_errors", lambda: (False, ""))
    monkeypatch.setattr(monitor_pipeline, "_load_recent_failed_task_durations", lambda _now: [])
    monkeypatch.setattr(monitor_pipeline, "_run_maintainability_audit_if_due", lambda _log: None)
    monkeypatch.setattr(monitor_pipeline, "_run_meta_questions_if_due", lambda _log: None)

    digest_path = tmp_path / "ai_agent_biweekly_sources.json"
    digest_path.write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "sources": [{"url": "https://example.com"}]}),
        encoding="utf-8",
    )
    security_path = tmp_path / "ai_agent_security_watch.json"
    security_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "open_high_severity": [{"id": "CVE-2026-27794", "source": "NVD"}],
                "open_critical_severity": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "AI_AGENT_INTELLIGENCE_DIGEST_FILE",
        str(digest_path),
        raising=False,
    )
    monkeypatch.setattr(
        monitor_pipeline,
        "AI_AGENT_SECURITY_WATCH_FILE",
        str(security_path),
        raising=False,
    )

    payload = monitor_pipeline._run_check(_Client(), logging.getLogger("test"), auto_fix=False, auto_recover=False)
    assert "ai_agent_security_advisory_open" in {row["condition"] for row in payload["issues"]}
