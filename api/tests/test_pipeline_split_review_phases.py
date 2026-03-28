"""Tests for split review pipeline: code-review → deploy → verify-production.

Spec 159: Replace single 'review' phase with three distinct phases:
  1. code-review  — does code meet spec, pass tests, is it mergeable?
  2. deploy       — merge to main, build, deploy to VPS, health check
  3. verify-production — run curl scenarios against live production

These tests verify:
  - Phase sequence: test → code-review → deploy → verify-production
  - Pass-gate: code-review must output CODE_REVIEW_PASSED to advance
  - Deploy: DEPLOY_FAILED stops pipeline; DEPLOY_PASSED advances to verify
  - Verify: VERIFY_PASSED sets idea validated; VERIFY_FAILED creates hotfix task
  - Public failures handled gracefully (hotfix created, regression set)
  - Each phase has independent retry logic
  - Legacy 'review' phase still dead-ends (backward compat)
  - Phase directions contain the right instructions
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.models.agent import TaskStatus, TaskType
from app.services import pipeline_advance_service


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_task(
    task_type: str,
    status: str = "completed",
    idea_id: str = "test-idea",
    output: str = "Output with enough characters to pass validation checks.",
    extra_context: dict | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {"idea_id": idea_id}
    if extra_context:
        ctx.update(extra_context)
    return {
        "id": "task-abc123",
        "task_type": task_type,
        "status": status,
        "output": output,
        "direction": "some direction",
        "context": ctx,
        "model": "claude-sonnet-4-6",
    }


def _no_existing_tasks(limit: int = 200, offset: int = 0) -> tuple[list, int, int]:
    return [], 0, 0


def _stub_create_task(task_create: Any) -> dict[str, Any]:
    return {
        "id": "new-task-999",
        "direction": task_create.direction,
        "task_type": task_create.task_type,
        "status": "pending",
        "context": task_create.context or {},
    }


# ─── Phase Sequence Tests ─────────────────────────────────────────────────────


class TestPhaseSequence:
    """Verify that the pipeline advances through correct phases."""

    def test_test_phase_advances_to_code_review(self) -> None:
        """After test completes, next phase is code-review (not legacy review)."""
        assert pipeline_advance_service._NEXT_PHASE["test"] == "code-review"

    def test_code_review_advances_to_deploy(self) -> None:
        """After code-review, next phase is deploy."""
        assert pipeline_advance_service._NEXT_PHASE["code-review"] == "deploy"

    def test_deploy_advances_to_verify_production(self) -> None:
        """After deploy, next phase is verify-production."""
        assert pipeline_advance_service._NEXT_PHASE["deploy"] == "verify-production"

    def test_verify_production_is_terminal(self) -> None:
        """verify-production has no next phase — it is the terminal step."""
        assert pipeline_advance_service._NEXT_PHASE["verify-production"] is None

    def test_legacy_review_is_dead_end(self) -> None:
        """Legacy 'review' phase still has no next phase (backward compat)."""
        assert pipeline_advance_service._NEXT_PHASE["review"] is None

    def test_legacy_verify_is_dead_end(self) -> None:
        """Legacy 'verify' phase still has no next phase (backward compat)."""
        assert pipeline_advance_service._NEXT_PHASE.get("verify") is None

    def test_full_pipeline_sequence(self) -> None:
        """Full spec→impl→test→code-review→deploy→verify-production path."""
        sequence = []
        current = "spec"
        while current is not None:
            sequence.append(current)
            current = pipeline_advance_service._NEXT_PHASE.get(current)
        assert sequence == ["spec", "impl", "test", "code-review", "deploy", "verify-production"]


class TestPhaseTaskTypes:
    """Verify task types are mapped correctly for new phases."""

    def test_code_review_maps_to_code_review_task_type(self) -> None:
        assert pipeline_advance_service._PHASE_TASK_TYPE["code-review"] == TaskType.CODE_REVIEW

    def test_deploy_maps_to_deploy_task_type(self) -> None:
        assert pipeline_advance_service._PHASE_TASK_TYPE["deploy"] == TaskType.DEPLOY

    def test_verify_production_maps_to_verify_task_type(self) -> None:
        assert pipeline_advance_service._PHASE_TASK_TYPE["verify-production"] == TaskType.VERIFY


# ─── Pass-Gate Tests ──────────────────────────────────────────────────────────


class TestCodeReviewPassGate:
    """code-review must output CODE_REVIEW_PASSED to advance."""

    def test_code_review_without_pass_token_does_not_advance(self) -> None:
        """If output lacks CODE_REVIEW_PASSED, no next task is created."""
        task = _make_task(
            "code-review",
            output="The code looks pretty good but has some issues. " * 3,
        )
        with patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()):
            result = pipeline_advance_service.maybe_advance(task)
        assert result is None

    def test_code_review_with_pass_token_advances_to_deploy(self) -> None:
        """If output contains CODE_REVIEW_PASSED, deploy task is created."""
        task = _make_task(
            "code-review",
            output="CODE_REVIEW_PASSED: all files correct, tests pass, DIF: trust=positive, verify=75, eventId=abc",
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            result = pipeline_advance_service.maybe_advance(task)

        assert result is not None
        assert result["task_type"] == TaskType.DEPLOY

    def test_code_review_failed_token_does_not_advance(self) -> None:
        """CODE_REVIEW_FAILED output does not advance the pipeline."""
        task = _make_task(
            "code-review",
            output="CODE_REVIEW_FAILED: missing test coverage, DIF: trust=concern, verify=15, eventId=xyz",
        )
        with patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()):
            result = pipeline_advance_service.maybe_advance(task)
        assert result is None

    def test_pass_gate_token_defined_for_code_review(self) -> None:
        """The pass-gate token is explicitly configured for code-review."""
        assert "code-review" in pipeline_advance_service._PASS_GATE_TOKEN
        assert pipeline_advance_service._PASS_GATE_TOKEN["code-review"] == "CODE_REVIEW_PASSED"

    def test_deploy_has_no_pass_gate_token(self) -> None:
        """deploy phase does not require a special pass-gate token."""
        assert "deploy" not in pipeline_advance_service._PASS_GATE_TOKEN

    def test_verify_production_has_no_pass_gate_token(self) -> None:
        """verify-production checks VERIFY_PASSED/FAILED separately — not via _PASS_GATE_TOKEN."""
        assert "verify-production" not in pipeline_advance_service._PASS_GATE_TOKEN


# ─── Deploy Phase Tests ───────────────────────────────────────────────────────


class TestDeployPhase:
    """Deploy phase: merge, build, health check, advance on DEPLOY_PASSED."""

    def test_deploy_passed_advances_to_verify_production(self) -> None:
        """DEPLOY_PASSED output advances pipeline to verify-production."""
        task = _make_task(
            "deploy",
            output="DEPLOY_PASSED: SHA abc123 live at coherencycoin.com. Health check HTTP 200.",
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            result = pipeline_advance_service.maybe_advance(task)

        assert result is not None
        assert result["task_type"] == TaskType.VERIFY

    def test_deploy_without_passed_token_still_advances(self) -> None:
        """Deploy has no pass-gate token check — any complete output advances."""
        task = _make_task(
            "deploy",
            output="Health check passed. Build successful. Containers restarted.",
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            result = pipeline_advance_service.maybe_advance(task)

        assert result is not None
        assert result["task_type"] == TaskType.VERIFY

    def test_deploy_hollow_output_blocked(self) -> None:
        """Deploy with too-short output is treated as hollow and not advanced."""
        task = _make_task("deploy", output="ok")
        # Patch update_task so the hollow rejection doesn't fail on missing DB
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.update_task", return_value=None),
        ):
            result = pipeline_advance_service.maybe_advance(task)
        assert result is None

    def test_deploy_direction_contains_merge_instructions(self) -> None:
        """The auto-generated deploy direction includes merge + SSH deploy commands."""
        code_review_task = _make_task(
            "code-review",
            output="CODE_REVIEW_PASSED: everything looks good " * 3,
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            pipeline_advance_service.maybe_advance(code_review_task)

        assert len(created_tasks) == 1
        direction = created_tasks[0]["direction"]
        assert "deploy" in direction.lower() or "Deploy" in direction
        assert "ssh" in direction.lower() or "docker compose" in direction.lower()
        assert "health" in direction.lower() or "DEPLOY_PASSED" in direction

    def test_deploy_direction_contains_pass_fail_tokens(self) -> None:
        """Deploy direction explicitly mentions DEPLOY_PASSED and DEPLOY_FAILED output tokens."""
        code_review_task = _make_task(
            "code-review",
            output="CODE_REVIEW_PASSED: spec verified " * 3,
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            pipeline_advance_service.maybe_advance(code_review_task)

        direction = created_tasks[0]["direction"]
        assert "DEPLOY_PASSED" in direction
        assert "DEPLOY_FAILED" in direction


# ─── Verify-Production Phase Tests ───────────────────────────────────────────


class TestVerifyProductionPhase:
    """verify-production: run curl scenarios, handle public failures gracefully."""

    def test_verify_passed_sets_idea_validated(self) -> None:
        """VERIFY_PASSED output triggers manifestation_status=validated on the idea."""
        task = _make_task(
            "verify-production",
            output="VERIFY_PASSED: all 4 curl scenarios returned expected results.",
        )
        validated_ids: list[str] = []

        def capture_update(idea_id: str, **kwargs: Any) -> None:
            if kwargs.get("manifestation_status") == "validated":
                validated_ids.append(idea_id)

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.idea_service.update_idea", side_effect=capture_update),
        ):
            result = pipeline_advance_service.maybe_advance(task)

        # Terminal phase — no next task created
        assert result is None
        # But idea was validated
        assert "test-idea" in validated_ids

    def test_verify_failed_creates_hotfix_task(self) -> None:
        """VERIFY_FAILED output triggers urgent hotfix task creation."""
        task = _make_task(
            "verify-production",
            output="VERIFY_FAILED: GET /api/ideas returned 500 instead of 200. Feature is broken.",
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch("app.services.idea_service.update_idea", return_value=None),
        ):
            result = pipeline_advance_service.maybe_advance(task)

        # No next phase advancement
        assert result is None

        # Hotfix task was created
        assert len(created_tasks) == 1
        hotfix = created_tasks[0]
        assert hotfix["context"].get("hotfix") is True
        assert hotfix["context"].get("priority") == "urgent"
        assert hotfix["task_type"] == TaskType.IMPL

    def test_verify_failed_sets_idea_regression(self) -> None:
        """VERIFY_FAILED marks the idea as regression, not validated."""
        task = _make_task(
            "verify-production",
            output="VERIFY_FAILED: /api/health returned 503. Deployment broken.",
        )
        update_calls: list[dict] = []

        def capture_update(idea_id: str, **kwargs: Any) -> None:
            update_calls.append({"idea_id": idea_id, **kwargs})

        with (
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch("app.services.idea_service.update_idea", side_effect=capture_update),
        ):
            pipeline_advance_service.maybe_advance(task)

        regression_calls = [c for c in update_calls if c.get("manifestation_status") == "regression"]
        assert len(regression_calls) >= 1
        assert regression_calls[0]["idea_id"] == "test-idea"

    def test_verify_failed_hotfix_contains_failing_output(self) -> None:
        """Hotfix task direction includes the failing verify-production output."""
        failing_output = "VERIFY_FAILED: /api/ideas/test-idea returned 404. Data missing from prod DB."
        task = _make_task("verify-production", output=failing_output)
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch("app.services.idea_service.update_idea", return_value=None),
        ):
            pipeline_advance_service.maybe_advance(task)

        assert len(created_tasks) == 1
        direction = created_tasks[0]["direction"]
        assert "VERIFY_FAILED" in direction or "404" in direction or "publicly broken" in direction.lower()

    def test_verify_passed_without_idea_id_does_not_crash(self) -> None:
        """VERIFY_PASSED with no idea_id in context exits cleanly without crashing."""
        task = {
            "id": "task-noidea",
            "task_type": "verify-production",
            "status": "completed",
            "output": "VERIFY_PASSED: all scenarios pass.",
            "direction": "verify",
            "context": {},  # no idea_id
            "model": "claude-haiku-4-5",
        }
        with patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()):
            result = pipeline_advance_service.maybe_advance(task)
        assert result is None  # no crash, no task created

    def test_verify_failed_without_idea_id_does_not_crash(self) -> None:
        """VERIFY_FAILED with no idea_id handles gracefully — no hotfix, no crash."""
        task = {
            "id": "task-noidea",
            "task_type": "verify-production",
            "status": "completed",
            "output": "VERIFY_FAILED: something broke.",
            "direction": "verify",
            "context": {},  # no idea_id
            "model": "claude-haiku-4-5",
        }
        # Should not raise, even though _handle_verify_failure won't be called
        result = pipeline_advance_service.maybe_advance(task)
        assert result is None


# ─── Downstream Cascade Tests ─────────────────────────────────────────────────


class TestDownstreamCascade:
    """Failing upstream phases should cascade-invalidate downstream ones."""

    def test_code_review_downstream_includes_deploy_and_verify(self) -> None:
        """If code-review is invalidated, deploy and verify-production are also invalidated."""
        downstream = pipeline_advance_service._DOWNSTREAM.get("code-review", [])
        assert "deploy" in downstream
        assert "verify-production" in downstream

    def test_deploy_downstream_includes_verify(self) -> None:
        """If deploy is invalidated, verify-production is also invalidated."""
        downstream = pipeline_advance_service._DOWNSTREAM.get("deploy", [])
        assert "verify-production" in downstream

    def test_impl_failure_invalidates_code_review_and_deploy(self) -> None:
        """impl failure cascades to code-review, deploy, and verify-production."""
        downstream = pipeline_advance_service._DOWNSTREAM.get("impl", [])
        assert "code-review" in downstream
        assert "deploy" in downstream
        assert "verify-production" in downstream


# ─── Idempotency / Dedup Tests ────────────────────────────────────────────────


class TestDeduplication:
    """Already-pending tasks should not be double-created."""

    def test_code_review_not_created_if_already_pending(self) -> None:
        """If a code-review task for this idea already exists, don't create another."""
        existing_code_review = {
            "id": "task-existing-cr",
            "task_type": "code-review",
            "status": "pending",
            "context": {"idea_id": "test-idea"},
        }
        task = _make_task(
            "test",
            output="All 12 tests passed. pytest exit code 0. Coverage 87%.",
        )

        def mock_list(limit: int = 200, offset: int = 0) -> tuple:
            return [existing_code_review], 1, 0

        with patch("app.services.agent_service.list_tasks", side_effect=mock_list):
            result = pipeline_advance_service.maybe_advance(task)

        assert result is None

    def test_deploy_not_created_if_already_running(self) -> None:
        """If a deploy task for this idea is running, don't create another."""
        existing_deploy = {
            "id": "task-existing-deploy",
            "task_type": "deploy",
            "status": "running",
            "context": {"idea_id": "test-idea"},
        }
        task = _make_task(
            "code-review",
            output="CODE_REVIEW_PASSED: everything correct " * 3,
        )

        def mock_list(limit: int = 200, offset: int = 0) -> tuple:
            return [existing_deploy], 1, 0

        with patch("app.services.agent_service.list_tasks", side_effect=mock_list):
            result = pipeline_advance_service.maybe_advance(task)

        assert result is None


# ─── Retry Logic Tests ────────────────────────────────────────────────────────


class TestRetryLogic:
    """Each phase has its own retry logic with max 2 retries."""

    def test_code_review_retries_on_failure(self) -> None:
        """Failed code-review creates a retry task."""
        task = _make_task(
            "code-review",
            status="failed",
            output="Provider timed out after 300s.",
            extra_context={"retry_count": 0},
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
        ):
            result = pipeline_advance_service.maybe_retry(task)

        assert result is not None
        assert result["context"]["retry_count"] == 1

    def test_deploy_retries_on_timeout(self) -> None:
        """Timed-out deploy creates a retry task."""
        task = _make_task(
            "deploy",
            status="timed_out",
            output="SSH connection timed out.",
            extra_context={"retry_count": 1},
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
        ):
            result = pipeline_advance_service.maybe_retry(task)

        assert result is not None
        assert result["context"]["retry_count"] == 2

    def test_verify_production_retries_on_failure(self) -> None:
        """Failed verify-production (not VERIFY_FAILED — but failed status) retries."""
        task = _make_task(
            "verify-production",
            status="failed",
            output="Agent crashed mid-verify.",
            extra_context={"retry_count": 0},
        )
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
        ):
            result = pipeline_advance_service.maybe_retry(task)

        assert result is not None
        assert result["context"]["retry_count"] == 1

    def test_code_review_max_retries_escalates(self) -> None:
        """After 2 retries, code-review escalates to needs_decision."""
        task = _make_task(
            "code-review",
            status="failed",
            output="Provider auth failed.",
            extra_context={"retry_count": 2},
        )
        escalated_to: list[str] = []

        def capture_update(task_id: str, **kwargs: Any) -> None:
            if kwargs.get("status") == TaskStatus.NEEDS_DECISION:
                escalated_to.append(task_id)

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.update_task", side_effect=capture_update),
        ):
            result = pipeline_advance_service.maybe_retry(task)

        assert result is None  # no new retry task
        assert "task-abc123" in escalated_to

    def test_deploy_retry_carries_partial_work(self) -> None:
        """Retry of a deploy task preserves partial output in the direction."""
        partial_output = "Merged to main successfully. Build started but SSH dropped."
        task = _make_task(
            "deploy",
            status="failed",
            output=partial_output,
            extra_context={"retry_count": 0},
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=capture_create),
        ):
            pipeline_advance_service.maybe_retry(task)

        assert len(created_tasks) == 1
        assert partial_output in created_tasks[0]["direction"]


# ─── Output Minimum Length Tests ─────────────────────────────────────────────


class TestOutputMinimumLength:
    """Phase-specific minimum output lengths prevent hollow completions."""

    def test_code_review_min_output_is_30_chars(self) -> None:
        assert pipeline_advance_service._MIN_OUTPUT_CHARS.get("code-review", 0) >= 30

    def test_deploy_min_output_is_50_chars(self) -> None:
        assert pipeline_advance_service._MIN_OUTPUT_CHARS.get("deploy", 0) >= 50

    def test_verify_production_min_output_is_50_chars(self) -> None:
        assert pipeline_advance_service._MIN_OUTPUT_CHARS.get("verify-production", 0) >= 50

    def test_hollow_code_review_does_not_advance(self) -> None:
        """code-review with too-short output is rejected as hollow."""
        task = _make_task("code-review", output="ok")
        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.update_task", return_value=None),
        ):
            result = pipeline_advance_service.maybe_advance(task)
        assert result is None


# ─── Direction Content Tests ──────────────────────────────────────────────────


class TestVerifyProductionDirection:
    """verify-production direction must instruct the agent to run real curl scenarios."""

    def test_verify_direction_mentions_verify_passed_token(self) -> None:
        """Deploy → verify advance creates a task mentioning VERIFY_PASSED."""
        deploy_task = _make_task(
            "deploy",
            output="DEPLOY_PASSED: SHA abc123. All containers healthy.",
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            pipeline_advance_service.maybe_advance(deploy_task)

        assert len(created_tasks) == 1
        direction = created_tasks[0]["direction"]
        assert "VERIFY_PASSED" in direction
        assert "VERIFY_FAILED" in direction

    def test_verify_direction_mentions_curl_or_scenarios(self) -> None:
        """verify-production direction tells agent to run verification scenarios."""
        deploy_task = _make_task(
            "deploy",
            output="Deploy completed. Health check returned HTTP 200.",
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            pipeline_advance_service.maybe_advance(deploy_task)

        direction = created_tasks[0]["direction"]
        # Must instruct agent to verify production with concrete scenarios
        assert any(kw in direction.lower() for kw in ("curl", "scenario", "verify", "production"))


# ─── Public Failure Graceful Handling ────────────────────────────────────────


class TestPublicFailureGracefulHandling:
    """verify-production failures are publicly visible — must be handled gracefully."""

    def test_verify_failure_does_not_propagate_exception(self) -> None:
        """Even if idea_service update fails, the call does not raise."""
        task = _make_task(
            "verify-production",
            output="VERIFY_FAILED: /api/ideas returned 500.",
        )

        def failing_update(idea_id: str, **kwargs: Any) -> None:
            raise RuntimeError("DB connection failed")

        with (
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch("app.services.idea_service.update_idea", side_effect=failing_update),
        ):
            # Should not raise even when underlying services fail
            result = pipeline_advance_service.maybe_advance(task)

        assert result is None

    def test_verify_failure_hotfix_creation_exception_does_not_propagate(self) -> None:
        """If hotfix task creation fails, the verify failure handler does not raise."""
        task = _make_task(
            "verify-production",
            output="VERIFY_FAILED: production endpoint returning 404.",
        )

        def failing_create(task_create: Any) -> dict:
            raise RuntimeError("Task queue unavailable")

        with (
            patch("app.services.agent_service.create_task", side_effect=failing_create),
            patch("app.services.idea_service.update_idea", return_value=None),
        ):
            # Should not raise even when hotfix creation fails
            result = pipeline_advance_service.maybe_advance(task)

        assert result is None

    def test_verify_failed_includes_idea_id_in_hotfix_context(self) -> None:
        """Hotfix task context includes the idea_id so it can be tracked."""
        task = _make_task(
            "verify-production",
            idea_id="split-review-pipeline",
            output="VERIFY_FAILED: health endpoint returned 503.",
        )
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch("app.services.idea_service.update_idea", return_value=None),
        ):
            pipeline_advance_service.maybe_advance(task)

        assert len(created_tasks) == 1
        assert created_tasks[0]["context"]["idea_id"] == "split-review-pipeline"

    def test_multiple_verify_failures_each_create_hotfix(self) -> None:
        """Each VERIFY_FAILED event independently creates its own hotfix task."""
        task1 = _make_task("verify-production", idea_id="idea-alpha",
                           output="VERIFY_FAILED: idea-alpha is broken.")
        task2 = _make_task("verify-production", idea_id="idea-beta",
                           output="VERIFY_FAILED: idea-beta is broken.")
        created_tasks: list[dict] = []

        def capture_create(task_create: Any) -> dict:
            t = _stub_create_task(task_create)
            created_tasks.append(t)
            return t

        with (
            patch("app.services.agent_service.create_task", side_effect=capture_create),
            patch("app.services.idea_service.update_idea", return_value=None),
        ):
            pipeline_advance_service.maybe_advance(task1)
            pipeline_advance_service.maybe_advance(task2)

        assert len(created_tasks) == 2
        idea_ids = {t["context"]["idea_id"] for t in created_tasks}
        assert idea_ids == {"idea-alpha", "idea-beta"}


# ─── Validated Status Tests ───────────────────────────────────────────────────


class TestIdeaValidatedOnSuccess:
    """Ideas become 'validated' only after verify-production passes."""

    def test_idea_only_validated_after_verify_production(self) -> None:
        """Code-review PASSED and deploy PASSED do not validate the idea."""
        validated_ideas: list[str] = []

        def capture_update(idea_id: str, **kwargs: Any) -> None:
            if kwargs.get("manifestation_status") == "validated":
                validated_ideas.append(idea_id)

        cr_task = _make_task(
            "code-review",
            output="CODE_REVIEW_PASSED: all criteria met " * 3,
        )
        deploy_task = _make_task(
            "deploy",
            output="DEPLOY_PASSED: containers healthy, SHA abc123 live.",
        )

        with (
            patch("app.services.agent_service.list_tasks", return_value=_no_existing_tasks()),
            patch("app.services.agent_service.create_task", side_effect=_stub_create_task),
            patch("app.services.idea_service.update_idea", side_effect=capture_update),
            patch.object(pipeline_advance_service, "_find_spec_file", return_value=""),
        ):
            pipeline_advance_service.maybe_advance(cr_task)
            pipeline_advance_service.maybe_advance(deploy_task)

        assert validated_ideas == []  # not validated yet

    def test_idea_validated_exactly_when_verify_production_passes(self) -> None:
        """Only VERIFY_PASSED triggers manifestation_status=validated."""
        validated_ideas: list[str] = []

        def capture_update(idea_id: str, **kwargs: Any) -> None:
            if kwargs.get("manifestation_status") == "validated":
                validated_ideas.append(idea_id)

        verify_task = _make_task(
            "verify-production",
            idea_id="my-validated-feature",
            output="VERIFY_PASSED: all 5 scenarios returned correct responses.",
        )

        with patch("app.services.idea_service.update_idea", side_effect=capture_update):
            pipeline_advance_service.maybe_advance(verify_task)

        assert "my-validated-feature" in validated_ideas
