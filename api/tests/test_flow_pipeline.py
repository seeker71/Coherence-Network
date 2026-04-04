"""Flow-centric integration tests for pipeline phase advancement.

Tests that completing tasks triggers correct phase transitions:
  code-review → deploy → verify-production

Phase advancement happens inside pipeline_advance_service.maybe_advance(task),
which is called automatically when agent_service.update_task() sets status=completed.
"""

from __future__ import annotations

from typing import Any

import pytest
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.services import pipeline_advance_service as pas
from app.services import pipeline_advance_service
from app.models.agent import TaskType, TaskStatus


# ─── helpers ──────────────────────────────────────────────────────────────────

def _task(
    *,
    id: str = "t-001",
    task_type: str = "code-review",
    status: str = "completed",
    output: str = "CODE_REVIEW_PASSED: all good",
    idea_id: str = "idea-abc",
    retry_count: int = 0,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {"idea_id": idea_id, "retry_count": retry_count}
    if extra_context:
        ctx.update(extra_context)
    return {
        "id": id,
        "task_type": task_type,
        "status": status,
        "output": output,
        "direction": f"Direction for {task_type}",
        "model": "claude-test",
        "context": ctx,
    }


def _stub_no_existing_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make list_tasks return empty so duplicate-skip check passes."""
    from app.services import agent_service as _as
    monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))
    monkeypatch.setattr(pas, "_find_spec_file", lambda *_: "specs/test-flow.md")


def _stub_create_task(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture tasks created by agent_service.create_task."""
    created: list[dict] = []

    def _create(payload: Any) -> dict[str, Any]:
        d = {
            "id": f"new-{len(created)+1}",
            "task_type": payload.task_type.value if hasattr(payload.task_type, "value") else str(payload.task_type),
            "direction": payload.direction,
            "context": payload.context or {},
        }
        created.append(d)
        return d

    from app.services import agent_service as _as
    monkeypatch.setattr(_as, "create_task", _create)
    return created


def _stub_idea_service(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Capture calls to idea_service.update_idea."""
    updates: dict[str, str] = {}

    def _update(idea_id: str, **kwargs: Any) -> None:
        updates[idea_id] = kwargs.get("manifestation_status", "")

    from app.services import idea_service as _is
    monkeypatch.setattr(_is, "update_idea", _update)
    return updates


# ═══════════════════════════════════════════════════════════════════════════════
# Phase Configuration (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhaseConfiguration:
    """Verify phase sequence mapping and task type assignments."""

    def test_phase_sequence(self) -> None:
        """_NEXT_PHASE maps: code-review -> deploy -> verify-production."""
        assert pas._NEXT_PHASE["code-review"] == "deploy"
        assert pas._NEXT_PHASE["deploy"] == "verify-production"
        # verify-production advances to reflect (terminal learning phase)
        assert pas._NEXT_PHASE.get("verify-production") == "reflect"

    def test_phase_task_types(self) -> None:
        """Each phase has the correct TaskType mapping."""
        assert pas._PHASE_TASK_TYPE["code-review"] == TaskType.CODE_REVIEW
        assert pas._PHASE_TASK_TYPE["deploy"] == TaskType.DEPLOY
        assert pas._PHASE_TASK_TYPE["verify-production"] == TaskType.VERIFY

    @pytest.mark.asyncio
    async def test_pipeline_status_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/pipeline/status returns running state; GET /api/pipeline/summary always 200."""
        from app.routers import pipeline

        app = FastAPI()
        app.include_router(pipeline.router, prefix="/api")

        # When running: status returns 200
        monkeypatch.setattr(
            "app.services.pipeline_service.get_status",
            lambda: {"running": True, "uptime_seconds": 10, "cycle_count": 1},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/status")
            assert resp.status_code == 200
            assert resp.json()["running"] is True

        # Summary always returns 200, even when not running
        monkeypatch.setattr(
            "app.services.pipeline_service.get_status",
            lambda: {"running": False, "uptime_seconds": 0, "cycle_count": 0},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/pipeline/summary")
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Code Review Gate (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCodeReviewGate:
    """Code-review must contain CODE_REVIEW_PASSED to advance to deploy."""

    def test_code_review_lgtm_advances_to_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Complete code-review with CODE_REVIEW_PASSED + LGTM creates deploy task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: Code looks good. LGTM.",
        )
        result = pas.maybe_advance(task)

        assert result is not None
        assert len(created) == 1
        assert created[0]["task_type"] == "deploy"

    def test_code_review_approved_advances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CODE_REVIEW_PASSED + APPROVED also triggers advancement."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: APPROVED. All spec requirements met.",
        )
        result = pas.maybe_advance(task)

        assert result is not None
        assert len(created) == 1
        assert created[0]["task_type"] == "deploy"

    def test_code_review_without_pass_phrase_does_not_advance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output without CODE_REVIEW_PASSED does not create deploy task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="The code looks okay but has some minor issues. LGTM with reservations.",
        )
        result = pas.maybe_advance(task)

        assert result is None
        assert created == []

    def test_code_review_fail_no_advance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Failed code-review (status=failed) does not advance."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="failed",
            output="CODE_REVIEW_PASSED: but status is failed",
        )
        result = pas.maybe_advance(task)

        assert result is None
        assert created == []


# ═══════════════════════════════════════════════════════════════════════════════
# Deploy Phase (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeployPhase:
    """Deploy phase advancement and context propagation."""

    def test_deploy_complete_advances_to_verify(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Completing deploy task creates verify-production task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: SHA abc1234 live at coherencycoin.com. Health check 200 OK.",
        )
        result = pas.maybe_advance(task)

        assert result is not None
        assert len(created) == 1
        # TaskType.VERIFY has value "verify"
        assert created[0]["task_type"] == "verify"

    def test_deploy_with_idea_id_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """idea_id carries through from code-review to deploy to verify."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        # Simulate code-review completing -> creates deploy
        cr_task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: all checks green.",
            idea_id="idea-propagation-test",
        )
        pas.maybe_advance(cr_task)
        assert len(created) == 1
        assert created[0]["context"]["idea_id"] == "idea-propagation-test"

        # Simulate deploy completing -> creates verify
        deploy_task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: SHA def5678 live at coherencycoin.com. Health 200.",
            idea_id="idea-propagation-test",
        )
        pas.maybe_advance(deploy_task)
        assert len(created) == 2
        assert created[1]["context"]["idea_id"] == "idea-propagation-test"

    def test_deploy_failure_no_advance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Failed deploy does not create verify-production task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="failed",
            output="DEPLOY_FAILED: SSH timeout to 187.77.152.42",
        )
        result = pas.maybe_advance(task)

        assert result is None
        assert created == []


# ═══════════════════════════════════════════════════════════════════════════════
# Verify Production (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerifyProduction:
    """Verify-production phase outcomes: validated, hotfix, regression."""

    def test_verify_passed_validates_idea(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VERIFY_PASSED in output marks idea as validated."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        idea_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_PASSED: All scenarios passed. /api/health 200, /api/ideas 200.",
            idea_id="idea-verify-pass",
        )
        pas.maybe_advance(task)

        assert idea_updates.get("idea-verify-pass") == "validated"

    def test_verify_failed_creates_hotfix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VERIFY_FAILED creates hotfix impl task with priority=urgent."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_FAILED: /api/pipeline/status returned 500 instead of 200.",
            idea_id="idea-verify-fail",
        )
        pas.maybe_advance(task)

        # A hotfix task should be created
        hotfix_tasks = [t for t in created if t["context"].get("hotfix") is True]
        assert len(hotfix_tasks) >= 1
        hotfix = hotfix_tasks[0]
        assert hotfix["task_type"] == "impl"
        assert hotfix["context"]["priority"] == "urgent"

    def test_verify_failed_sets_regression_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify failure sets idea manifestation_status to regression."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        idea_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_FAILED: /api/ideas returned 404. Expected 200 with JSON body containing ideas array.",
            idea_id="idea-regression",
        )
        pas.maybe_advance(task)

        assert idea_updates.get("idea-regression") == "regression"

    def test_verify_without_verdict_no_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ambiguous verify output (no VERIFY_PASSED/VERIFY_FAILED) takes no special action."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        idea_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="Ran some checks against production. Results were mixed but inconclusive.",
            idea_id="idea-ambiguous",
        )
        pas.maybe_advance(task)

        # No hotfix created (no VERIFY_FAILED)
        hotfix_tasks = [t for t in created if t.get("context", {}).get("hotfix") is True]
        assert hotfix_tasks == []
        # Idea not marked validated or regression
        assert "idea-ambiguous" not in idea_updates


# ═══════════════════════════════════════════════════════════════════════════════
# Full Chain (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullChain:
    """End-to-end pipeline chain tests."""

    def test_full_pipeline_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """code-review (LGTM) -> deploy (complete) -> verify (VERIFY_PASSED) end-to-end."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        idea_updates = _stub_idea_service(monkeypatch)

        # Step 1: code-review passes
        cr_task = _task(
            id="cr-1",
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: LGTM. All tests pass.",
            idea_id="idea-full-chain",
        )
        r1 = pas.maybe_advance(cr_task)
        assert r1 is not None
        assert len(created) == 1
        assert created[0]["task_type"] == "deploy"

        # Step 2: deploy passes
        deploy_task = _task(
            id="d-1",
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: SHA abc123 live at coherencycoin.com. Health check 200.",
            idea_id="idea-full-chain",
        )
        r2 = pas.maybe_advance(deploy_task)
        assert r2 is not None
        assert len(created) == 2
        assert created[1]["task_type"] == "verify"

        # Step 3: verify passes
        verify_task = _task(
            id="v-1",
            task_type="verify-production",
            status="completed",
            output="VERIFY_PASSED: All scenarios pass. /api/health 200, /api/ideas 200.",
            idea_id="idea-full-chain",
        )
        r3 = pas.maybe_advance(verify_task)
        # verify-production advances to reflect
        assert idea_updates.get("idea-full-chain") == "validated"

    def test_multiple_ideas_independent_chains(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two ideas with separate pipeline chains do not interfere."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        # Idea A: code-review passes
        task_a = _task(
            id="cr-a",
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: Idea A looks great. LGTM.",
            idea_id="idea-a",
        )
        pas.maybe_advance(task_a)

        # Idea B: code-review passes
        task_b = _task(
            id="cr-b",
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: Idea B is solid. APPROVED.",
            idea_id="idea-b",
        )
        pas.maybe_advance(task_b)

        assert len(created) == 2
        ideas = {t["context"]["idea_id"] for t in created}
        assert ideas == {"idea-a", "idea-b"}
        # Both are deploy tasks
        assert all(t["task_type"] == "deploy" for t in created)

    def test_downstream_invalidation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When a phase fails, downstream phases are not created."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        # code-review fails (status=failed) -> no deploy created
        task = _task(
            task_type="code-review",
            status="failed",
            output="CODE_REVIEW_FAILED: Missing test coverage.",
            idea_id="idea-blocked",
        )
        result = pas.maybe_advance(task)

        assert result is None
        assert created == []

        # Even with a separate deploy attempt that fails -> no verify
        deploy_task = _task(
            task_type="deploy",
            status="failed",
            output="DEPLOY_FAILED: build error",
            idea_id="idea-blocked",
        )
        result2 = pas.maybe_advance(deploy_task)
        assert result2 is None
        assert created == []


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases: exception safety, deduplication, stats shape."""

    def test_pipeline_advance_exception_does_not_propagate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If pipeline raises an error during advancement, maybe_advance returns None gracefully."""
        _stub_no_existing_tasks(monkeypatch)

        # Make create_task raise
        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "create_task", lambda _payload: (_ for _ in ()).throw(RuntimeError("boom")))

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: LGTM.",
        )
        # Should not propagate the exception
        result = pas.maybe_advance(task)
        assert result is None

    def test_deduplication_no_duplicate_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Completing the same phase twice does not create duplicate downstream tasks."""
        # First call: no existing tasks
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: LGTM. All good.",
            idea_id="idea-dedup",
        )
        r1 = pas.maybe_advance(task)
        assert r1 is not None
        assert len(created) == 1

        # Second call: now there IS an existing deploy task (pending)
        from app.services import agent_service as _as
        existing_deploy = [{
            "id": "existing-deploy",
            "task_type": "deploy",
            "status": "pending",
            "context": {"idea_id": "idea-dedup"},
        }]
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: (existing_deploy, 1, 0))

        r2 = pas.maybe_advance(task)
        # Should skip because deploy already exists
        assert r2 is None
        assert len(created) == 1  # still just 1

    def test_stats_structure(self) -> None:
        """Pipeline phase maps have expected structure and all phases covered."""
        # _NEXT_PHASE has all expected phases
        assert "code-review" in pas._NEXT_PHASE
        assert "deploy" in pas._NEXT_PHASE
        assert "verify-production" in pas._NEXT_PHASE
        assert "spec" in pas._NEXT_PHASE
        assert "impl" in pas._NEXT_PHASE
        assert "test" in pas._NEXT_PHASE

        # _PHASE_TASK_TYPE maps every phase in _NEXT_PHASE that has a successor
        for phase, next_phase in pas._NEXT_PHASE.items():
            if next_phase is not None:
                assert phase in pas._PHASE_TASK_TYPE, (
                    f"Phase {phase!r} has successor {next_phase!r} but no TaskType mapping"
                )

        # _DOWNSTREAM cascade map covers code-review and deploy
        assert "deploy" in pas._DOWNSTREAM.get("code-review", [])
        assert "verify-production" in pas._DOWNSTREAM.get("code-review", [])
        assert "verify-production" in pas._DOWNSTREAM.get("deploy", [])

        # _MIN_OUTPUT_CHARS has entries for all pipeline phases
        for phase in ("code-review", "deploy", "verify-production"):
            assert phase in pas._MIN_OUTPUT_CHARS, (
                f"Phase {phase!r} missing from _MIN_OUTPUT_CHARS"
            )
