from __future__ import annotations

from scripts import run_self_improve_cycle


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []
        self._task_counter = 0
        self._task_order: list[str] = []
        self._task_outputs: dict[str, str] = {}
        self.alerts_payload: dict = {"threshold_ratio": 0.15, "alerts": []}

    def post(self, url: str, json: dict | None = None, headers: dict | None = None) -> _FakeResponse:  # noqa: ARG002
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

    def get(self, url: str) -> _FakeResponse:
        if "/api/automation/usage/alerts" in url:
            return _FakeResponse(200, self.alerts_payload)
        for task_id in self._task_order:
            if url.endswith(f"/api/agent/tasks/{task_id}"):
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
    client = _FakeClient()

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
    )

    assert report["status"] == "completed"
    assert [row["stage"] for row in report["stages"]] == ["plan", "execute", "review"]

    plan_payload, execute_payload, review_payload = client.created_payloads
    assert plan_payload["task_type"] == "spec"
    assert execute_payload["task_type"] == "impl"
    assert review_payload["task_type"] == "review"

    assert "stage-1-output" in execute_payload["direction"]
    assert "stage-2-output" in review_payload["direction"]
    for stage in report["stages"]:
        assert stage["executor"] == "codex"
        assert stage["model"] in {"gpt-5.3-codex", "gpt-5.3-codex-spark"}


def test_run_cycle_skips_when_usage_too_close_to_limit() -> None:
    client = _FakeClient()
    client.alerts_payload = {
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

    report = run_self_improve_cycle.run_cycle(
        client=client,
        base_url="https://example.test",
        poll_interval_seconds=0,
        timeout_seconds=5,
        execute_pending=False,
        execute_token="",
        usage_threshold_ratio=0.15,
    )

    assert report["status"] == "skipped"
    assert "Usage limit precheck blocked self-improve cycle" in report["skip_reason"]
    assert report["stages"] == []
    assert client.created_payloads == []
