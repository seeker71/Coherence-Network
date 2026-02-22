from __future__ import annotations

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
        tasks_payload: list[dict] | None = None,
        needs_decision_payload: list[dict] | None = None,
        friction_payload: list[dict] | None = None,
        runtime_payload: dict | None = None,
        usage_error: Exception | None = None,
        post_error_plan: list[Exception] | None = None,
    ) -> None:
        self.created_payloads: list[dict] = []
        self._task_counter = 0
        self._task_order: list[str] = []
        self._task_outputs: dict[str, str] = {}
        self._post_error_plan = list(post_error_plan or [])
        self.usage_payload = usage_payload
        self.tasks_payload = tasks_payload or []
        self.needs_decision_payload = needs_decision_payload or []
        self.friction_payload = friction_payload or []
        self.runtime_payload = runtime_payload or {}
        self.usage_error = usage_error

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
            self._task_counter += 1
            task_id = f"task-{self._task_counter}"
            payload = dict(json or {})
            payload["_task_id"] = task_id
            self.created_payloads.append(payload)
            self._task_order.append(task_id)
            return _FakeResponse(201, {"id": task_id})

        if "/execute" in url:
            return _FakeResponse(200, {"ok": True})

        raise AssertionError(f"unexpected post url: {url}")

    def get(self, url: str, timeout: float | None = None) -> _FakeResponse:  # noqa: ARG002
        if "/api/automation/usage/alerts" in url:
            if self.usage_error:
                raise self.usage_error
            return _FakeResponse(200, self.usage_payload)

        if "/api/agent/tasks?status=needs_decision" in url:
            return _FakeResponse(200, self.needs_decision_payload)

        if "/api/agent/tasks?" in url and "/api/agent/tasks/" not in url:
            return _FakeResponse(200, self.tasks_payload)

        if "/api/friction/events" in url:
            return _FakeResponse(200, self.friction_payload)

        if "/api/runtime/endpoints/summary" in url:
            return _FakeResponse(200, self.runtime_payload)

        if "/api/agent/tasks/" in url:
            task_id = url.rsplit("/", 1)[-1]
            if task_id in self._task_order:
                idx = int(task_id.split("-")[-1])
                output = f"stage-{idx}-output"
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


def test_run_cycle_fails_plan_submit_stage_on_repeated_post_errors() -> None:
    client = _FakeClient(
        usage_payload=_default_usage_payload(),
        post_error_plan=[RuntimeError("timeout"), RuntimeError("timeout"), RuntimeError("timeout")],
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

    assert report["status"] == "failed"
    assert report["failed_stage"] == "plan_submit_or_wait"
    assert "task submit failed" in str(report["failure_error"])


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
