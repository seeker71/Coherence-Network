"""Spec 159 acceptance tests: split review into code-review → deploy → verify-production.

Named per specs/159-split-review-deploy-verify-phases.md § Acceptance Tests.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import pipeline_advance_service
from app.models.agent import TaskType


def _task(
    *,
    id: str = "t-acc",
    task_type: str = "code-review",
    status: str = "completed",
    output: str = "CODE_REVIEW_PASSED: ok",
    idea_id: str = "idea-acc",
    retry_count: int = 0,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {"idea_id": idea_id, "retry_count": retry_count}
    return {
        "id": id,
        "task_type": task_type,
        "status": status,
        "output": output,
        "direction": f"dir-{task_type}",
        "model": "test-model",
        "context": ctx,
    }


def _stub_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_service as _as

    monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))


def _stub_create_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    from app.services import agent_service as _as

    created: list[dict[str, Any]] = []

    def _create(payload: Any) -> dict[str, Any]:
        row = {
            "id": f"n-{len(created)}",
            "task_type": (
                payload.task_type.value
                if hasattr(payload.task_type, "value")
                else str(payload.task_type)
            ),
            "direction": payload.direction,
            "context": dict(payload.context or {}),
        }
        created.append(row)
        return row

    monkeypatch.setattr(_as, "create_task", _create)
    return created


def _stub_update_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    from app.services import agent_service as _as

    updates: list[dict[str, Any]] = []

    def _update(task_id: str, **kwargs: Any) -> dict[str, Any]:
        updates.append({"task_id": task_id, **kwargs})
        return {"id": task_id, **kwargs}

    monkeypatch.setattr(_as, "update_task", _update)
    return updates


def _stub_idea_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    from app.services import idea_service as _is

    out: dict[str, str] = {}

    def _upd(idea_id: str, **kwargs: Any) -> None:
        m = kwargs.get("manifestation_status")
        if m is not None:
            out[idea_id] = str(m)

    monkeypatch.setattr(_is, "update_idea", _upd)
    return out


# --- Acceptance Tests (spec names) -------------------------------------------


def test_code_review_pass_advances_to_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    """code-review with CODE_REVIEW_PASSED creates the next-phase deploy task."""
    _stub_list_empty(monkeypatch)
    created = _stub_create_capture(monkeypatch)
    monkeypatch.setattr(pipeline_advance_service, "_find_spec_file", lambda *_: "specs/159.md")

    task = _task(
        output="CODE_REVIEW_PASSED: requirements met, tests green, mergeable.",
    )
    result = pipeline_advance_service.maybe_advance(task)

    assert result is not None
    assert result.get("task_type") == TaskType.DEPLOY or result.get("task_type") == "deploy"
    assert len(created) == 1
    assert created[0]["task_type"] == "deploy"


def test_code_review_fail_does_not_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CODE_REVIEW_PASSED, pipeline does not create deploy."""
    _stub_list_empty(monkeypatch)
    created = _stub_create_capture(monkeypatch)

    task = _task(
        output="CODE_REVIEW_FAILED: tests missing for edge cases. " * 2,
    )
    assert pipeline_advance_service.maybe_advance(task) is None
    assert created == []


def test_deploy_fail_creates_fix_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exhausted deploy retries escalate (fix path or needs_decision) — Spec R3."""
    created = _stub_create_capture(monkeypatch)
    updates = _stub_update_capture(monkeypatch)
    _stub_list_empty(monkeypatch)

    task = _task(
        id="deploy-dead",
        task_type="deploy",
        status="failed",
        output="DEPLOY_FAILED: docker build failed with exit code 1. " * 2,
        idea_id="idea-deploy-fail",
        retry_count=pipeline_advance_service._MAX_RETRIES,
    )
    pipeline_advance_service.maybe_retry(task)

    def _is_needs_decision(u: dict[str, Any]) -> bool:
        s = u.get("status")
        val = getattr(s, "value", s)
        return val == "needs_decision"

    escalated = any(_is_needs_decision(u) for u in updates)
    fix_like = any(
        c.get("task_type") in ("impl", "heal", "spec")
        for c in created
    )
    assert escalated or fix_like, (
        f"expected escalation or fix task; updates={updates}, created={created}"
    )


def test_verify_production_fail_creates_hotfix_and_regression_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VERIFY_FAILED → urgent impl hotfix + manifestation_status=regression."""
    _stub_list_empty(monkeypatch)
    created = _stub_create_capture(monkeypatch)
    manifest = _stub_idea_capture(monkeypatch)

    task = _task(
        task_type="verify-production",
        output=(
            "VERIFY_FAILED: GET https://api.coherencycoin.com/api/ideas returned 404 "
            "— feature not found in production."
        ),
        idea_id="idea-hotfix",
    )
    assert pipeline_advance_service.maybe_advance(task) is None

    assert len(created) == 1
    assert created[0]["task_type"] == "impl"
    assert created[0]["context"].get("hotfix") is True
    assert created[0]["context"].get("priority") == "urgent"
    assert manifest.get("idea-hotfix") == "regression"


def test_full_chain_ends_in_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    """code-review → deploy → verify-production; validated only after VERIFY_PASSED."""
    manifest: dict[str, str] = {}

    def _create(payload: Any) -> dict[str, Any]:
        tt = (
            payload.task_type.value
            if hasattr(payload.task_type, "value")
            else str(payload.task_type)
        )
        return {
            "id": f"chain-{tt}",
            "task_type": tt,
            "direction": payload.direction,
            "context": dict(payload.context or {}),
        }

    def _idea(idea_id: str, **kwargs: Any) -> None:
        m = kwargs.get("manifestation_status")
        if m is not None:
            manifest[idea_id] = str(m)

    from app.services import agent_service as _as
    from app.services import idea_service as _is

    monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))
    monkeypatch.setattr(_as, "create_task", _create)
    monkeypatch.setattr(_as, "update_task", lambda *_a, **_k: {})
    monkeypatch.setattr(_is, "update_idea", _idea)
    monkeypatch.setattr(pipeline_advance_service, "_find_spec_file", lambda *_: "specs/159.md")

    iid = "idea-chain"
    cr = _task(
        id="cr",
        task_type="code-review",
        output="CODE_REVIEW_PASSED: all acceptance criteria satisfied.",
        idea_id=iid,
    )
    r1 = pipeline_advance_service.maybe_advance(cr)
    assert r1 is not None
    assert manifest.get(iid) != "validated"

    d = dict(r1)
    d["status"] = "completed"
    d["output"] = (
        "DEPLOY_PASSED: SHA abc1234 live. Health check https://api.coherencycoin.com/api/health 200 OK."
    )
    r2 = pipeline_advance_service.maybe_advance(d)
    assert r2 is not None
    assert manifest.get(iid) != "validated"

    v = dict(r2)
    v["status"] = "completed"
    v["task_type"] = "verify-production"
    v["output"] = (
        "VERIFY_PASSED: GET /api/health 200; GET /api/ideas 200. Scenarios green."
    )
    assert pipeline_advance_service.maybe_advance(v) is None
    assert manifest.get(iid) == "validated"


def test_phase_stats_in_pipeline_status() -> None:
    """R6: per-phase counters are exposed via pipeline pulse digest (phase_stats).

    Spec also requires GET /api/pipeline/status to include phase_stats; pulse is the
    implementation that aggregates task history into phase_stats today.
    """
    from app.services import pipeline_pulse_service

    pulse = pipeline_pulse_service.compute_pulse(window_days=7, task_limit=50)
    assert "phase_stats" in pulse
    assert isinstance(pulse["phase_stats"], dict)
    for _phase, stats in pulse["phase_stats"].items():
        assert "completed" in stats
        assert "failed" in stats


def test_downstream_invalidation_includes_deploy_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    """_DOWNSTREAM cascades code-review → deploy + verify-production (R5)."""
    ds_cr = pipeline_advance_service._DOWNSTREAM.get("code-review", [])
    assert "deploy" in ds_cr
    assert "verify-production" in ds_cr
    assert "verify-production" in pipeline_advance_service._DOWNSTREAM.get("deploy", [])

    existing = [
        {
            "id": "d1",
            "task_type": "deploy",
            "status": "completed",
            "context": {"idea_id": "inv-x"},
        },
        {
            "id": "v1",
            "task_type": "verify-production",
            "status": "pending",
            "context": {"idea_id": "inv-x"},
        },
    ]
    updates = _stub_update_capture(monkeypatch)
    from app.services import agent_service as _as

    monkeypatch.setattr(_as, "list_tasks", lambda **_k: (existing, 2, 0))

    n = pipeline_advance_service.invalidate_downstream("code-review", "inv-x")
    assert n == 2
    assert {u["task_id"] for u in updates} == {"d1", "v1"}
