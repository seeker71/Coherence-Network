from __future__ import annotations

import json
import importlib

import sys
importlib.import_module("app.services.agent_execution_service")

flow = sys.modules["app.services.agent_execution_task_flow"]


def test_smart_complexity_assessment_defaults_to_complex_when_missing() -> None:
    state = flow._smart_complexity_assessment({"direction": "Build a tiny helper"})

    assert state["complexity_score"] == 1.0
    assert state["decompose_required"] is True
    assert state["complexity_reason"] == "missing context complexity_score, defaulted to 1.0"


def test_smart_router_stage_sets_complexity_for_missing_context(
    monkeypatch,
) -> None:
    task = {"id": "task-router", "direction": "Build endpoint", "context": {}}
    micro_tasks: list[dict[str, object]] = [{"goal": "build endpoint"}]

    plan_inputs: dict[str, object] = {}
    calls: list[str] = []

    def fake_plan(_task: dict[str, object], *, complexity_score: float, decompose_required: bool) -> list[dict[str, object]]:
        plan_inputs["complexity_score"] = complexity_score
        plan_inputs["decompose_required"] = decompose_required
        return micro_tasks

    def fake_run_smart_model(**kwargs: object) -> dict[str, object]:
        stage = str(kwargs["stage"])
        calls.append(stage)
        if stage == "router":
            return {
                "ok": True,
                "elapsed_ms": 1,
                "content": json.dumps(
                    {
                        "complexity_score": 0.91,
                        "complexity_reason": "defaulted from missing context",
                        "decompose_required": False,
                    }
                ),
            }
        if stage == "worker":
            return {"ok": True, "elapsed_ms": 1, "content": json.dumps({"result": "ok", "done_checks": []})}
        if stage == "reviewer":
            return {
                "ok": True,
                "elapsed_ms": 1,
                "content": json.dumps({"accepted": True, "gaps": [], "followup_tasks": []}),
            }
        raise AssertionError(f"unexpected smart stage: {stage}")

    monkeypatch.setattr(flow, "_smart_run_smart_model", fake_run_smart_model)
    monkeypatch.setattr(flow, "_smart_plan_micro_tasks", fake_plan)
    monkeypatch.setattr(flow, "_smart_update_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_smart_record_event", lambda **_: None)
    monkeypatch.setattr(
        flow,
        "_complete_failure",
        lambda **kwargs: {
            "ok": False,
            "status": "failed",
            "msg": kwargs.get("msg"),
        },
    )
    monkeypatch.setattr(
        flow,
        "_complete_success",
        lambda **kwargs: {
            "ok": True,
            "status": "completed",
            "msg": "smart-success",
        },
    )

    result = flow._smart_execute_task_workflow(
        "task-router",
        task=task,
        route_is_paid=False,
        worker_id="openclaw-worker:server",
        force_paid_providers=False,
        max_cost_usd=None,
        estimated_cost_usd=None,
        cost_slack_ratio=None,
    )

    assert calls[:1] == ["router"]
    assert result["status"] == "completed"
    assert plan_inputs["complexity_score"] == 0.91
    assert plan_inputs["decompose_required"] is False


def test_smart_workflow_escalates_on_repeated_smart_reviewer_parse_failure(
    monkeypatch,
) -> None:
    task = {
        "id": "task-reviewer-repeat",
        "direction": "One microtask",
        "context": {"complexity_score": 0.2, "decompose_required": False},
    }
    calls: list[str] = []
    failures: list[dict[str, object]] = []

    def fake_plan(_task: dict[str, object], *, complexity_score: float, decompose_required: bool) -> list[dict[str, object]]:
        return [{"goal": "one microtask"}]

    def fake_run_smart_model(**kwargs: object) -> dict[str, object]:
        stage = str(kwargs["stage"])
        calls.append(stage)
        if stage == "worker":
            return {"ok": True, "elapsed_ms": 1, "content": json.dumps({"result": "partial output", "done_checks": []})}
        if stage == "reviewer":
            return {"ok": True, "elapsed_ms": 1, "content": "not-json-review"}
        raise AssertionError(f"unexpected smart stage: {stage}")

    def fake_complete_failure(**kwargs: object) -> dict[str, object]:
        failures.append({"msg": kwargs.get("msg")})
        return {
            "ok": False,
            "status": "failed",
            "msg": kwargs.get("msg"),
        }

    monkeypatch.setattr(flow, "_smart_plan_micro_tasks", fake_plan)
    monkeypatch.setattr(flow, "_smart_run_smart_model", fake_run_smart_model)
    monkeypatch.setattr(flow, "_smart_update_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_smart_record_event", lambda **_: None)
    monkeypatch.setattr(flow, "_complete_failure", fake_complete_failure)
    monkeypatch.setattr(
        flow,
        "_complete_success",
        lambda **_: {"ok": True, "status": "completed", "msg": "smart-success"},
    )

    result = flow._smart_execute_task_workflow(
        "task-reviewer-repeat",
        task=task,
        route_is_paid=False,
        worker_id="openclaw-worker:server",
        force_paid_providers=False,
        max_cost_usd=None,
        estimated_cost_usd=None,
        cost_slack_ratio=None,
    )

    assert result["status"] == "failed"
    assert calls.count("worker") == 2
    assert calls.count("reviewer") == 2
    assert failures and isinstance(failures[0]["msg"], str)
    assert str(failures[0]["msg"]).startswith("Smart workflow blocked")


def test_smart_workflow_escalates_when_attempt_limit_reached(
    monkeypatch,
) -> None:
    task = {
        "id": "task-attempt-limit",
        "direction": "Keep trying",
        "context": {"complexity_score": 0.2, "decompose_required": False},
    }
    calls: list[str] = []
    failures: list[str] = []

    def fake_plan(_task: dict[str, object], *, complexity_score: float, decompose_required: bool) -> list[dict[str, object]]:
        return [{"goal": "keep trying", "max_attempts": 2}]

    def fake_run_smart_model(**kwargs: object) -> dict[str, object]:
        calls.append(str(kwargs["stage"]))
        if kwargs["stage"] == "worker":
            return {
                "ok": False,
                "elapsed_ms": 1,
                "content": "",
                "error": f"worker failure {len(calls)}",
            }
        raise AssertionError(f"unexpected smart stage: {kwargs['stage']}")

    def fake_complete_failure(**kwargs: object) -> dict[str, object]:
        failures.append(str(kwargs.get("msg")))
        return {"ok": False, "status": "failed", "msg": kwargs.get("msg")}

    monkeypatch.setattr(flow, "_smart_plan_micro_tasks", fake_plan)
    monkeypatch.setattr(flow, "_smart_run_smart_model", fake_run_smart_model)
    monkeypatch.setattr(flow, "_smart_update_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_smart_record_event", lambda **_: None)
    monkeypatch.setattr(flow, "_complete_failure", fake_complete_failure)
    monkeypatch.setattr(flow, "_complete_success", lambda **_: {"ok": True, "status": "completed", "msg": "smart-success"})

    result = flow._smart_execute_task_workflow(
        "task-attempt-limit",
        task=task,
        route_is_paid=False,
        worker_id="openclaw-worker:server",
        force_paid_providers=False,
        max_cost_usd=None,
        estimated_cost_usd=None,
        cost_slack_ratio=None,
    )

    assert result["status"] == "failed"
    assert calls == ["worker", "worker"]
    assert any(
        "exceeded attempts (2)" in msg or "repeated worker failure" in msg
        for msg in failures
    )


def test_smart_workflow_accepts_followup_after_reviewer_reject(
    monkeypatch,
) -> None:
    task = {
        "id": "task-followup",
        "direction": "Build docs and then tests",
        "context": {"complexity_score": 0.4, "decompose_required": True},
    }
    micro_tasks = [{"goal": "Build docs", "max_attempts": 2}]

    calls: list[str] = []

    def fake_plan(_task: dict[str, object], *, complexity_score: float, decompose_required: bool) -> list[dict[str, object]]:
        return micro_tasks

    def fake_run_smart_model(**kwargs: object) -> dict[str, object]:
        calls.append(str(kwargs["stage"]))
        if kwargs["stage"] == "worker":
            if len([c for c in calls if c == "worker"]) == 1:
                return {"ok": True, "elapsed_ms": 1, "content": json.dumps({"result": "docs draft", "done_checks": []})}
            return {"ok": True, "elapsed_ms": 1, "content": json.dumps({"result": "full docs", "done_checks": []})}
        if kwargs["stage"] == "reviewer":
            if len([c for c in calls if c == "reviewer"]) == 1:
                return {
                    "ok": True,
                    "elapsed_ms": 1,
                    "content": json.dumps(
                        {
                            "accepted": False,
                            "gaps": ["missing examples"],
                            "followup_tasks": [{"goal": "Add examples", "complexity": 0.7}],
                        }
                    ),
                }
            return {"ok": True, "elapsed_ms": 1, "content": json.dumps({"accepted": True, "gaps": [], "followup_tasks": []})}
        raise AssertionError(f"unexpected smart stage: {kwargs['stage']}")

    monkeypatch.setattr(flow, "_smart_plan_micro_tasks", fake_plan)
    monkeypatch.setattr(flow, "_smart_run_smart_model", fake_run_smart_model)
    monkeypatch.setattr(flow, "_smart_update_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_smart_record_event", lambda **_: None)
    monkeypatch.setattr(
        flow,
        "_complete_success",
        lambda **kwargs: {"ok": True, "status": "completed", "msg": kwargs.get("model")},
    )
    monkeypatch.setattr(
        flow,
        "_complete_failure",
        lambda **kwargs: {"ok": False, "status": "failed", "msg": kwargs.get("msg")},
    )

    result = flow._smart_execute_task_workflow(
        "task-followup",
        task=task,
        route_is_paid=False,
        worker_id="openclaw-worker:server",
        force_paid_providers=False,
        max_cost_usd=None,
        estimated_cost_usd=None,
        cost_slack_ratio=None,
    )

    assert result["status"] == "completed"
    assert calls == ["worker", "reviewer", "worker", "reviewer"]
    assert micro_tasks and micro_tasks[0]["goal"] == "Add examples"
    assert float(micro_tasks[0]["complexity"]) <= 0.25
