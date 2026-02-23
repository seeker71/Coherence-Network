from __future__ import annotations

import json
from pathlib import Path

from scripts import run_self_improve_cycle


class _FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(
        self,
        *,
        usage_payload: dict,
        tasks_payload: object | None = None,
        needs_decision_payload: object | None = None,
        friction_payload: object | None = None,
        runtime_payload: object | None = None,
        daily_summary_payload: dict | None = None,
        usage_error: Exception | None = None,
        tasks_error: Exception | None = None,
        runtime_error: Exception | None = None,
        health_error: Exception | None = None,
        gates_error: Exception | None = None,
        deploy_active: bool = False,
        execute_status_code: int = 200,
        pending_polls_before_complete: int = 0,
        post_error_plan: list[Exception] | None = None,
        task_post_status_plan: list[int] | None = None,
        stage_output_overrides: dict[int, str] | None = None,
    ) -> None:
        self.created_payloads: list[dict] = []
        self.submitted_payloads: list[dict] = []
        self._task_counter = 0
        self._task_order: list[str] = []
        self._task_outputs: dict[str, str] = {}
        self._post_error_plan = list(post_error_plan or [])
        self._task_post_status_plan = list(task_post_status_plan or [])
        self._stage_output_overrides = dict(stage_output_overrides or {})
        self.usage_payload = usage_payload
        self.tasks_payload = tasks_payload if tasks_payload is not None else []
        self.needs_decision_payload = needs_decision_payload if needs_decision_payload is not None else []
        self.friction_payload = friction_payload if friction_payload is not None else []
        self.runtime_payload = runtime_payload if runtime_payload is not None else {}
        self.daily_summary_payload = daily_summary_payload or {
            "quality_awareness": {
                "status": "ok",
                "summary": {"severity": "low", "risk_score": 12},
                "hotspots": [{"kind": "long_function", "path": "api/app/services/example.py", "detail": "split helper"}],
                "guidance": ["Use extraction-by-intent for long functions to reduce drift."],
                "recommended_tasks": [
                    {"task_id": "architecture-modularization-review", "title": "Architecture modularization review"}
                ],
            }
        }
        self.usage_error = usage_error
        self.tasks_error = tasks_error
        self.runtime_error = runtime_error
        self.health_error = health_error
        self.gates_error = gates_error
        self.deploy_active = deploy_active
        self.execute_status_code = execute_status_code
        self.pending_polls_before_complete = max(0, pending_polls_before_complete)
        self._task_poll_counts: dict[str, int] = {}

    def post(
        self,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> _FakeResponse:  # noqa: ARG002
        if self._post_error_plan:
            raise self._post_error_plan.pop(0)

        if url.endswith("/api/agent/tasks"):
            payload = dict(json or {})
            self.submitted_payloads.append(payload)
            status_code = self._task_post_status_plan.pop(0) if self._task_post_status_plan else 201
            if status_code >= 400:
                return _FakeResponse(status_code, {"error": f"forced status {status_code}"})
            self._task_counter += 1
            task_id = f"task-{self._task_counter}"
            payload["_task_id"] = task_id
            self.created_payloads.append(payload)
            self._task_order.append(task_id)
            return _FakeResponse(201, {"id": task_id})

        if "/execute" in url:
            return _FakeResponse(self.execute_status_code, {"ok": self.execute_status_code < 400})

        raise AssertionError(f"unexpected post url: {url}")

    def get(  # noqa: ARG002
        self,
        url: str,
        timeout: float | None = None,
        headers: dict | None = None,
    ) -> _FakeResponse:
        if "/api/automation/usage/alerts" in url:
            if self.usage_error:
                raise self.usage_error
            return _FakeResponse(200, self.usage_payload)

        if url.endswith("/api/health"):
            if self.health_error:
                raise self.health_error
            return _FakeResponse(200, {"status": "ok"})

        if url.endswith("/api/gates/main-head"):
            if self.gates_error:
                raise self.gates_error
            return _FakeResponse(200, {"sha": "abc123"})

        if "api.github.com/repos/" in url and "/actions/workflows/public-deploy-contract.yml/runs" in url:
            workflow_runs = (
                [{"status": "in_progress", "html_url": "https://github.com/example/redeploy"}]
                if self.deploy_active
                else []
            )
            return _FakeResponse(200, {"workflow_runs": workflow_runs})

        if "/api/agent/tasks?status=needs_decision" in url:
            return _FakeResponse(200, self.needs_decision_payload)

        if "/api/agent/tasks?" in url and "/api/agent/tasks/" not in url:
            if self.tasks_error:
                raise self.tasks_error
            return _FakeResponse(200, self.tasks_payload)

        if "/api/friction/events" in url:
            return _FakeResponse(200, self.friction_payload)

        if "/api/runtime/endpoints/summary" in url:
            if self.runtime_error:
                raise self.runtime_error
            return _FakeResponse(200, self.runtime_payload)

        if "/api/automation/usage/daily-summary" in url:
            return _FakeResponse(200, self.daily_summary_payload)

        if "/api/agent/tasks/" in url:
            task_id = url.rsplit("/", 1)[-1]
            if task_id in self._task_order:
                poll_count = self._task_poll_counts.get(task_id, 0) + 1
                self._task_poll_counts[task_id] = poll_count
                if poll_count <= self.pending_polls_before_complete:
                    return _FakeResponse(
                        200,
                        {
                            "id": task_id,
                            "status": "pending",
                            "output": "",
                            "context": {"executor": "codex"},
                            "model": "",
                        },
                    )
                idx = int(task_id.split("-")[-1])
                output = self._stage_output_overrides.get(idx, f"stage-{idx}-output")
                self._task_outputs[task_id] = output
                payload = self.created_payloads[idx - 1]
                context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
                return _FakeResponse(
                    200,
                    {
                        "id": task_id,
                        "status": "completed",
                        "output": output,
                        "context": {"executor": context.get("executor", "")},
                        "model": context.get("model_override", ""),
                    },
                )

        raise AssertionError(f"unexpected get url: {url}")


def _default_usage_payload() -> dict:
    return {"threshold_ratio": 0.15, "alerts": []}


def test_plan_prompt_requires_proof_retry_and_unblock() -> None:
    prompt = run_self_improve_cycle.build_plan_direction()

    lowered = prompt.lower()
    assert "cheap" in lowered
    assert "fast" in lowered
    assert "proof" in lowered
    assert "retry" in lowered
    assert "unblock" in lowered
    assert "common blocker" in lowered
    assert "intent first" in lowered
    assert "system-level lens" in lowered
    assert "option thinking" in lowered
    assert "failure anticipation" in lowered
    assert "proof of meaning" in lowered
    assert "maintainability guidance" in lowered
    assert "quality-awareness" in lowered


def test_stage_payloads_pin_expected_models() -> None:
    plan_payload = run_self_improve_cycle.build_task_payload(
        direction="plan",
        task_type="spec",
        model_override="gpt-5.3-codex",
    )
    execute_payload = run_self_improve_cycle.build_task_payload(
        direction="execute",
        task_type="impl",
        model_override="gpt-5.3-codex-spark",
    )
    review_payload = run_self_improve_cycle.build_task_payload(
        direction="review",
        task_type="review",
        model_override="gpt-5.3-codex",
    )

    assert plan_payload["context"]["model_override"] == "gpt-5.3-codex"
    assert execute_payload["context"]["model_override"] == "gpt-5.3-codex-spark"
    assert review_payload["context"]["model_override"] == "gpt-5.3-codex"
    assert plan_payload["context"]["executor"] == "codex"
    assert execute_payload["context"]["executor"] == "codex"
    assert review_payload["context"]["executor"] == "codex"
    assert plan_payload["context"]["runner_codex_auth_mode"] == "api_key"
    assert execute_payload["context"]["runner_codex_auth_mode"] == "api_key"
    assert review_payload["context"]["runner_codex_auth_mode"] == "api_key"


def test_run_cycle_submits_plan_execute_review_in_order() -> None:
    client = _FakeClient(usage_payload=_default_usage_payload())

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_order.json",
    )

    assert report["status"] == "completed"
    assert [row["stage"] for row in report["stages"]] == ["plan", "execute", "review"]
    assert report["data_quality_mode"] in {"full", "degraded_partial", "degraded_usage"}
    assert report["input_bundle"]["blocking_usage_alert_count"] == 0
    assert report["input_bundle"]["usage_source"] == "live"
    assert report["input_bundle"]["quality_hotspot_count"] == 1
    assert report["input_bundle"]["quality_guidance_count"] == 1

    plan_payload, execute_payload, review_payload = client.created_payloads
    assert plan_payload["task_type"] == "spec"
    assert execute_payload["task_type"] == "impl"
    assert review_payload["task_type"] == "review"

    assert "stage-1-output" in execute_payload["direction"]
    assert "stage-2-output" in review_payload["direction"]
    for stage in report["stages"]:
        assert stage["executor"] == "codex"
        assert stage["model"] in {"gpt-5.3-codex", "gpt-5.3-codex-spark"}

    summary = report["delta_summary"]["problem"]
    assert "usage_blocking" in summary


def test_run_cycle_retries_plan_submit_when_transient_error_happens() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        post_error_plan=[RuntimeError("intermittent read timeout"),],
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_retry.json",
    )

    assert report["status"] == "completed"
    assert len(client.created_payloads) == 3


def test_run_cycle_retries_plan_submit_across_multiple_post_outages() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        post_error_plan=[
            RuntimeError("timeout"),
            RuntimeError("timeout"),
            RuntimeError("timeout"),
            RuntimeError("timeout"),
            RuntimeError("timeout"),
        ],
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_retry_fail.json",
    )

    assert report["status"] == "completed"
    assert len(client.created_payloads) == 3


def test_run_cycle_retries_plan_submit_on_http_502_then_completes() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        # First plan submit fails with 502, then plan/execute/review submits succeed.
        task_post_status_plan=[502, 201, 201, 201],
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_retry_502.json",
    )

    assert report["status"] == "completed"
    assert len(client.submitted_payloads) == 4
    assert len(client.created_payloads) == 3


def test_run_cycle_returns_infra_blocked_on_plan_submit_timeouts() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        post_error_plan=[
            RuntimeError("read operation timed out")
            for _ in range(20)
        ],
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_timeout_infra.json",
    )

    assert report["status"] == "infra_blocked"
    assert report["failed_stage"] == "plan_submit_or_wait"
    assert report["stages"] == []


def test_run_cycle_skips_when_usage_too_close_to_limit() -> None:
    client = _FakeClient(
        usage_payload={
            "threshold_ratio": 0.15,
            "alerts": [
                {
                    "provider": "openai",
                    "metric_id": "tokens_quota",
                    "severity": "warning",
                    "remaining_ratio": 0.1,
                    "message": "openai tokens low remaining",
                }
            ],
        }
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_skip.json",
    )

    assert report["status"] == "skipped"
    assert "Usage limit precheck blocked self-improve cycle" in report["skip_reason"]
    assert report["stages"] == []
    assert report["input_bundle"]["usage_source"] == "live"
    assert client.created_payloads == []


def test_run_cycle_continues_when_usage_precheck_fails_without_cache() -> None:
    client = _FakeClient(usage_payload=_default_usage_payload(), usage_error=RuntimeError("precheck timeout"))

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_missing_cache.json",
    )

    assert report["status"] == "completed"
    assert report["data_quality_mode"] == "degraded_usage"
    assert report["input_bundle"]["usage_source"] == "missing"
    assert report["usage_limit_precheck"]["allowed"] is True


def test_run_cycle_uses_cached_usage_when_usage_endpoint_fails() -> None:
    cache_file = "/tmp/self_improve_cache_with_data.json"
    run_self_improve_cycle._save_cached_usage_payload(
        Path(cache_file),
        {
            "threshold_ratio": 0.15,
            "alerts": [
                {
                    "provider": "openai",
                    "metric_id": "tokens_quota",
                    "severity": "critical",
                    "remaining_ratio": 0.05,
                    "message": "cached low quota",
                }
            ],
        },
    )

    client = _FakeClient(usage_payload=_default_usage_payload(), usage_error=RuntimeError("precheck timeout"))
    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path=cache_file,
    )

    assert report["status"] == "skipped"
    assert report["data_quality_mode"] == "degraded_usage"
    assert report["input_bundle"]["usage_source"] == "cached"
    assert "blocked" in report["skip_reason"]
    assert report["input_bundle_before"]["usage"]["blocking_alerts"][0]["provider"] == "openai"


def test_delta_summary_includes_before_after_metrics() -> None:
    client = _FakeClient(
        usage_payload={
            "threshold_ratio": 0.15,
            "alerts": [
                {
                    "provider": "openrouter",
                    "metric_id": "requests_5m",
                    "severity": "warning",
                    "remaining_ratio": 0.3,
                    "message": "stable",
                }
            ],
        },
        tasks_payload=[
            {"id": "existing", "status": "pending"},
            {"id": "blocked", "status": "needs_decision"},
        ],
        needs_decision_payload=[{"id": "blocked", "status": "needs_decision"}],
        friction_payload=[{"id": "f1", "block_type": "paid_provider_blocked"}],
        runtime_payload={"summary": []},
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_delta.json",
    )

    delta = report["delta_summary"]
    assert delta["before_metrics"]["task_count"] == 2
    assert delta["after_metrics"]["friction_open_count"] == 1
    assert delta["proof"]["before_counts"]["needs_decision_count"] == 1
    assert delta["proof"]["after_counts"]["needs_decision_count"] == 1


def test_collect_input_bundle_parses_dict_task_payloads() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        tasks_payload={"tasks": [{"id": "t1", "status": "pending"}]},
        needs_decision_payload={"tasks": [{"id": "t2", "status": "needs_decision"}]},
        friction_payload={"events": [{"id": "f1", "block_type": "paid_provider_blocked"}]},
        runtime_payload={"summary": [{"route": "/api/health"}]},
    )

    bundle = run_self_improve_cycle._collect_input_bundle(
        client,
        base_url="https://example.test",
        threshold_ratio=0.15,
        usage_cache_path=Path("/tmp/self_improve_cache_dict_payload.json"),
    )

    assert bundle["summary"]["task_count"] == 1
    assert bundle["summary"]["needs_decision_count"] == 1
    assert bundle["summary"]["friction_open_count"] == 1
    assert bundle["summary"]["runtime_endpoint_count"] == 1


def test_run_cycle_resumes_from_checkpoint_plan_stage(tmp_path: Path) -> None:
    checkpoint = tmp_path / "self_improve_checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "updated_at": "2099-01-01T00:00:00+00:00",
                "status": "running",
                "stages": [
                    {
                        "stage": "plan",
                        "task_id": "task-plan-existing",
                        "status": "completed",
                        "executor": "codex",
                        "model": "gpt-5.3-codex",
                        "output": "existing plan output",
                        "task": {
                            "id": "task-plan-existing",
                            "status": "completed",
                            "output": "existing plan output",
                            "context": {"executor": "codex", "source": "self_improve_cycle"},
                            "model": "gpt-5.3-codex",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = _FakeClient(usage_payload=_default_usage_payload())
    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_checkpoint_resume.json",
        checkpoint_path=str(checkpoint),
    )

    assert report["status"] == "completed"
    assert report["stages"][0]["stage"] == "plan"
    assert report["stages"][0]["resumed"] is True
    assert report["stages"][0]["resume_source"] == "checkpoint"
    assert len(client.created_payloads) == 2


def test_run_cycle_tolerates_execute_forbidden_when_pending() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        execute_status_code=403,
        pending_polls_before_complete=1,
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=True,
        execute_token="invalid",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_execute_forbidden.json",
    )

    assert report["status"] == "completed"
    assert [row["stage"] for row in report["stages"]] == ["plan", "execute", "review"]


def test_infra_preflight_allows_degraded_observability_when_core_is_healthy() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        tasks_error=RuntimeError("The read operation timed out"),
        runtime_error=RuntimeError("The read operation timed out"),
    )

    preflight = run_self_improve_cycle._infra_preflight(
        client=client,
        base_url="https://example.test",
        usage_threshold_ratio=0.15,
        usage_cache_path=Path("/tmp/self_improve_preflight_usage_cache.json"),
        attempts=1,
        consecutive_successes=1,
    )

    assert preflight["allowed"] is True
    assert preflight["history"][0]["tasks_ok"] is False
    assert preflight["history"][0]["runtime_ok"] is False
    assert preflight["history"][0]["health_ok"] is True
    assert preflight["history"][0]["gates_ok"] is True


def test_run_cycle_caps_review_direction_below_agent_task_limit() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        stage_output_overrides={
            1: "PLAN-" + ("A" * 4000),
            2: "EXEC-" + ("B" * 4000),
        },
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_direction_cap.json",
    )

    assert report["status"] == "completed"
    assert len(client.created_payloads) == 3
    review_payload = client.created_payloads[2]
    assert review_payload["task_type"] == "review"
    assert len(review_payload["direction"]) <= run_self_improve_cycle.AGENT_TASK_DIRECTION_SAFE_CHARS
    assert "Original plan:" in review_payload["direction"]
    assert "Execution output:" in review_payload["direction"]


def test_run_cycle_recovers_from_422_with_compacted_direction_retry() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        stage_output_overrides={
            1: "PLAN-" + ("A" * 4000),
            2: "EXEC-" + ("B" * 4000),
        },
        # plan success, execute success, review submit 422, review submit retry success
        task_post_status_plan=[201, 201, 422, 201],
    )

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
        usage_cache_path="/tmp/self_improve_cache_review_422_retry.json",
    )

    assert report["status"] == "completed"
    assert len(client.created_payloads) == 3
    # Four submit attempts total with one failed review submit.
    assert len(client.submitted_payloads) == 4
    failed_review_submit = client.submitted_payloads[2]
    retried_review_submit = client.submitted_payloads[3]
    assert failed_review_submit["task_type"] == "review"
    assert retried_review_submit["task_type"] == "review"
    assert len(retried_review_submit["direction"]) <= len(failed_review_submit["direction"])
