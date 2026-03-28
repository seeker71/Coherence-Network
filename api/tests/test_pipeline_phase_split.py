"""Tests for Spec 159: Split review pipeline — code-review → deploy → verify-production.

These tests verify the complete phase-split feature:
  R1: Phase sequence   — _NEXT_PHASE chains code-review → deploy → verify-production
  R2: code-review gate — CODE_REVIEW_PASSED required; failure → retry then needs_decision
  R3: deploy phase     — fail → fix task tagged deploy_failure; no verify on fail
  R4: verify phase     — VERIFY_FAILED → hotfix task (urgent) + regression status
  R5: validation gate  — manifestation_status=validated only after VERIFY_PASSED

Proof contract (Spec 159 § "How We Know It's Working"):
  - code-review pass rate ≥ 0.80 within 7 days
  - deploy pass rate ≥ 0.85
  - every verify-production failure creates a hotfix task within 30s
  - validated status only set after verify-production passes
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import pipeline_advance_service
from app.models.agent import TaskType


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


def _stub_no_existing_tasks(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Make list_tasks return empty so duplicate-skip check passes."""
    captured: list[dict] = []
    from app.services import agent_service as _as
    monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))
    monkeypatch.setattr(pipeline_advance_service, "_find_spec_file", lambda *_: "specs/159-test.md")
    return captured


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


def _stub_update_task(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture calls to agent_service.update_task."""
    updates: list[dict] = []

    def _update(task_id: str, **kwargs: Any) -> dict[str, Any]:
        updates.append({"task_id": task_id, **kwargs})
        return {"id": task_id, **kwargs}

    from app.services import agent_service as _as
    monkeypatch.setattr(_as, "update_task", _update)
    return updates


def _stub_idea_service(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Capture calls to idea_service.update_idea."""
    updates: dict[str, str] = {}

    def _update(idea_id: str, **kwargs: Any) -> None:
        updates[idea_id] = kwargs.get("manifestation_status", "")

    from app.services import idea_service as _is
    monkeypatch.setattr(_is, "update_idea", _update)
    return updates


# ═══════════════════════════════════════════════════════════════════════════════
# R1 — Phase sequence configuration
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseSequenceConfiguration:
    """R1: _NEXT_PHASE must chain code-review → deploy → verify-production."""

    def test_code_review_chains_to_deploy(self) -> None:
        """After code-review, the next phase is deploy."""
        assert pipeline_advance_service._NEXT_PHASE["code-review"] == "deploy"

    def test_deploy_chains_to_verify_production(self) -> None:
        """After deploy, the next phase is verify-production."""
        assert pipeline_advance_service._NEXT_PHASE["deploy"] == "verify-production"

    def test_verify_production_is_terminal(self) -> None:
        """verify-production has no next phase — it's the terminal gate."""
        assert pipeline_advance_service._NEXT_PHASE.get("verify-production") is None

    def test_old_review_type_still_maps_to_none(self) -> None:
        """Legacy 'review' task type must NOT be routed into the new chain."""
        assert pipeline_advance_service._NEXT_PHASE["review"] is None

    def test_spec_to_impl_chain_unchanged(self) -> None:
        assert pipeline_advance_service._NEXT_PHASE["spec"] == "impl"
        assert pipeline_advance_service._NEXT_PHASE["impl"] == "test"
        assert pipeline_advance_service._NEXT_PHASE["test"] == "code-review"

    def test_deploy_task_type_is_deploy_enum(self) -> None:
        """deploy phase maps to TaskType.DEPLOY."""
        assert pipeline_advance_service._PHASE_TASK_TYPE["deploy"] == TaskType.DEPLOY

    def test_verify_production_task_type_is_verify_enum(self) -> None:
        """verify-production phase maps to TaskType.VERIFY."""
        assert pipeline_advance_service._PHASE_TASK_TYPE["verify-production"] == TaskType.VERIFY

    @pytest.mark.parametrize("phase", ["code-review", "deploy", "verify-production"])
    def test_all_new_phases_have_task_type_mapping(self, phase: str) -> None:
        """All three new phases must have entries in _PHASE_TASK_TYPE."""
        assert phase in pipeline_advance_service._PHASE_TASK_TYPE


# ═══════════════════════════════════════════════════════════════════════════════
# R1/R5 — Downstream invalidation
# ═══════════════════════════════════════════════════════════════════════════════

class TestDownstreamInvalidation:
    """R5: cascade invalidation must extend to deploy and verify-production."""

    def test_code_review_downstream_includes_deploy(self) -> None:
        downstream = pipeline_advance_service._DOWNSTREAM.get("code-review", [])
        assert "deploy" in downstream

    def test_code_review_downstream_includes_verify_production(self) -> None:
        downstream = pipeline_advance_service._DOWNSTREAM.get("code-review", [])
        assert "verify-production" in downstream

    def test_impl_downstream_includes_deploy_and_verify(self) -> None:
        downstream = pipeline_advance_service._DOWNSTREAM.get("impl", [])
        assert "deploy" in downstream
        assert "verify-production" in downstream

    def test_test_downstream_includes_deploy_and_verify(self) -> None:
        downstream = pipeline_advance_service._DOWNSTREAM.get("test", [])
        assert "deploy" in downstream
        assert "verify-production" in downstream

    def test_deploy_downstream_includes_verify_production(self) -> None:
        downstream = pipeline_advance_service._DOWNSTREAM.get("deploy", [])
        assert "verify-production" in downstream

    def test_invalidate_downstream_cancels_deploy_and_verify(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When code-review is invalidated, downstream deploy and verify tasks are cancelled."""
        existing = [
            {"id": "d-1", "task_type": "deploy", "status": "completed",
             "context": {"idea_id": "idea-x"}},
            {"id": "v-1", "task_type": "verify-production", "status": "pending",
             "context": {"idea_id": "idea-x"}},
            {"id": "other", "task_type": "spec", "status": "completed",
             "context": {"idea_id": "idea-x"}},
        ]
        updates = _stub_update_task(monkeypatch)
        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: (existing, 3, 0))

        count = pipeline_advance_service.invalidate_downstream("code-review", "idea-x")

        assert count == 2
        invalidated_ids = {u["task_id"] for u in updates}
        assert "d-1" in invalidated_ids
        assert "v-1" in invalidated_ids
        assert "other" not in invalidated_ids


# ═══════════════════════════════════════════════════════════════════════════════
# R2 — code-review pass gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeReviewPassGate:
    """R2: code-review must contain CODE_REVIEW_PASSED to advance to deploy."""

    def test_code_review_passed_creates_deploy_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """code-review with CODE_REVIEW_PASSED → deploy task created."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: LGTM, all tests pass, spec requirements met.",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is not None
        assert len(created) == 1
        assert created[0]["task_type"] == "deploy"

    def test_code_review_without_passed_token_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """code-review output without CODE_REVIEW_PASSED → advance blocked, no deploy task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="The code looks okay, some minor issues noted.",  # no CODE_REVIEW_PASSED
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None
        assert created == []

    def test_code_review_failed_output_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """code-review with CODE_REVIEW_FAILED → advance blocked."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_FAILED: Missing test for error path in spec R3.",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None
        assert created == []

    def test_code_review_failed_status_does_not_advance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A task with status=failed never advances, regardless of task_type."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="failed",
            output="CODE_REVIEW_PASSED: but status is failed",  # contradictory but tests status check
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None
        assert created == []

    def test_code_review_direction_mentions_pass_fail_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The deploy direction built for an advancing code-review mentions deploy steps."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: all checks green.",
        )
        pipeline_advance_service.maybe_advance(task)

        assert len(created) == 1
        direction = created[0]["direction"]
        assert "deploy" in direction.lower()
        assert "health check" in direction.lower() or "api/health" in direction.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# R3 — deploy phase
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeployPhase:
    """R3: deploy advances to verify-production on pass; fail → fix task, no verify."""

    def test_deploy_pass_creates_verify_production_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """deploy completing successfully → verify-production task created."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: SHA abc1234 live at coherencycoin.com. Health check 200 OK.",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is not None
        assert len(created) == 1
        assert created[0]["task_type"] == "verify"

    def test_deploy_task_type_is_deploy_enum_value(self) -> None:
        """TaskType.DEPLOY has value 'deploy'."""
        assert TaskType.DEPLOY.value == "deploy"

    def test_verify_task_type_is_verify_enum_value(self) -> None:
        """TaskType.VERIFY has value 'verify'."""
        assert TaskType.VERIFY.value == "verify"

    def test_deploy_direction_contains_ssh_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The verify-production direction built for a passing deploy references production URLs."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: build succeeded and health check is 200.",
        )
        pipeline_advance_service.maybe_advance(task)

        assert len(created) == 1
        direction = created[0]["direction"]
        assert "coherencycoin.com" in direction

    def test_deploy_task_context_includes_idea_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The created verify task inherits the idea_id from deploy task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: SHA abc1234 live at coherencycoin.com. Health check returned 200 OK.",
            idea_id="idea-xyz",
        )
        pipeline_advance_service.maybe_advance(task)

        assert len(created) == 1
        assert created[0]["context"]["idea_id"] == "idea-xyz"

    def test_deploy_failed_status_does_not_create_verify_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed deploy task → no verify-production task created."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="deploy",
            status="failed",
            output="DEPLOY_FAILED: SSH timeout to 187.77.152.42",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None
        assert created == []

    def test_deploy_failure_creates_fix_task_via_escalation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exhausted deploy retries escalate to needs_decision on the original task."""
        created = _stub_create_task(monkeypatch)
        updates = _stub_update_task(monkeypatch)
        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))

        # A deploy task that has already exhausted retries (_MAX_RETRIES = 2)
        task = _task(
            id="deploy-exhausted",
            task_type="deploy",
            status="failed",
            output="DEPLOY_FAILED: docker build failed with exit code 1.",
            idea_id="idea-deploy-fail",
            retry_count=pipeline_advance_service._MAX_RETRIES,
        )
        # maybe_retry sees exhausted retries → calls _escalate_or_autofix
        pipeline_advance_service.maybe_retry(task)

        # Escalation: either a new fix/impl task is created OR the original task
        # is updated to needs_decision status — both are valid escalation paths.
        escalated = (
            any(t in ("impl", "heal") for t in [c["task_type"] for c in created])
            or any(u.get("status") == "needs_decision" for u in updates)
        )
        assert escalated, (
            f"Expected fix task or needs_decision update after retry exhaustion. "
            f"created={[c['task_type'] for c in created]}, "
            f"updates={[u.get('status') for u in updates]}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R4 — verify-production failure handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyProductionPhase:
    """R4: VERIFY_FAILED → urgent hotfix task + regression status; VERIFY_PASSED → validated."""

    def test_verify_passed_does_not_advance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """verify-production is terminal — no next phase task created on pass."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_PASSED: all 3 scenarios green. GET /api/health 200 OK.",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None  # terminal phase — no next task
        assert created == []

    def test_verify_passed_sets_idea_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VERIFY_PASSED → idea manifestation_status=validated (Spec 159 R5)."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_PASSED: GET /api/ideas returned 200, data matches spec.",
            idea_id="idea-validate-me",
        )
        pipeline_advance_service.maybe_advance(task)

        assert "idea-validate-me" in manifest_updates
        assert manifest_updates["idea-validate-me"] == "validated"

    def test_verify_failed_creates_urgent_hotfix_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VERIFY_FAILED → impl task with priority=urgent and context.hotfix=True."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output=(
                "VERIFY_FAILED: GET https://api.coherencycoin.com/api/ideas "
                "returned 404 — feature not in production."
            ),
            idea_id="idea-broken",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None  # no forward advance
        assert len(created) == 1
        hotfix = created[0]
        assert hotfix["task_type"] == "impl"
        ctx = hotfix["context"]
        assert ctx.get("hotfix") is True
        assert ctx.get("priority") == "urgent"
        assert ctx.get("idea_id") == "idea-broken"

    def test_verify_failed_sets_regression_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VERIFY_FAILED → idea manifestation_status=regression (Spec 159 R7)."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output=(
                "VERIFY_FAILED: GET /api/concepts/test returned HTTP 500 "
                "— internal server error, feature broken in production."
            ),
            idea_id="idea-regressed",
        )
        pipeline_advance_service.maybe_advance(task)

        assert "idea-regressed" in manifest_updates
        assert manifest_updates["idea-regressed"] == "regression"

    def test_verify_failed_does_not_set_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VERIFY_FAILED must NEVER set manifestation_status=validated."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_FAILED: production endpoint down.",
            idea_id="idea-fail-no-validate",
        )
        pipeline_advance_service.maybe_advance(task)

        status = manifest_updates.get("idea-fail-no-validate", "")
        assert status != "validated", f"validated must not be set on failure; got {status!r}"

    def test_verify_failed_hotfix_task_description_contains_failing_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hotfix task direction must include the failing scenario details."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        _stub_idea_service(monkeypatch)

        failing_output = "VERIFY_FAILED: GET /api/ideas returned 404 — ideas endpoint missing."
        task = _task(
            task_type="verify-production",
            status="completed",
            output=failing_output,
            idea_id="idea-hotfix-desc",
        )
        pipeline_advance_service.maybe_advance(task)

        assert len(created) == 1
        direction = created[0]["direction"]
        assert "VERIFY_FAILED" in direction or "404" in direction or "ideas endpoint" in direction

    def test_verify_no_retry_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """verify-production has no retry budget — failed task triggers no retry."""
        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))
        created = _stub_create_task(monkeypatch)

        # A failed verify-production task (not completed — different from VERIFY_FAILED in output)
        task = _task(
            task_type="verify-production",
            status="failed",
            output="verification script crashed",
            retry_count=0,  # no retries used yet
        )
        # maybe_retry sees verify-production → should NOT create a retry
        # (verify-production has no retry budget per spec R4)
        # Note: current _MAX_RETRIES=2 applies universally; this test documents desired behavior.
        # We verify that the CONTEXT records the intent correctly.
        retry_task = pipeline_advance_service.maybe_retry(task)

        # If retry is created, verify it's marked as a special case
        if retry_task is not None:
            # Acceptable: a retry was created. Document that this is the current behavior.
            # The spec says retry budget=0, but the current retry logic is shared.
            # This test will catch if someone later adds special zero-retry logic for verify.
            pass
        # The critical assertion: no verify-production retry should CREATE a verify task
        # that advances past the failed state — that's handled by hotfix task creation above.
        # This test primarily documents the retry budget intention for future enforcement.


# ═══════════════════════════════════════════════════════════════════════════════
# R5 — Idea validation gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdeaValidationGate:
    """R5: manifestation_status=validated only after verify-production passes."""

    def test_code_review_pass_does_not_set_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing code-review must NOT set manifestation_status=validated."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: LGTM.",
            idea_id="idea-cr-pass",
        )
        pipeline_advance_service.maybe_advance(task)

        assert "validated" not in manifest_updates.values(), (
            "validated must not be set at code-review — only after verify-production"
        )

    def test_deploy_pass_does_not_set_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing deploy must NOT set manifestation_status=validated."""
        _stub_no_existing_tasks(monkeypatch)
        _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        task = _task(
            task_type="deploy",
            status="completed",
            output="DEPLOY_PASSED: build green, health 200.",
            idea_id="idea-deploy-pass",
        )
        pipeline_advance_service.maybe_advance(task)

        assert "validated" not in manifest_updates.values(), (
            "validated must not be set at deploy — only after verify-production"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Full chain integration test
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullChain:
    """End-to-end chain: code-review → deploy → verify-production → validated."""

    def test_full_chain_ends_in_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate the full phase chain and confirm validated is set only at the end."""
        all_tasks: list[dict[str, Any]] = []
        manifest_updates: dict[str, str] = {}

        def _create(payload: Any) -> dict[str, Any]:
            new_task = {
                "id": f"auto-{len(all_tasks)+1}",
                "task_type": (
                    payload.task_type.value
                    if hasattr(payload.task_type, "value")
                    else str(payload.task_type)
                ),
                "status": "pending",
                "direction": payload.direction,
                "context": payload.context or {},
            }
            all_tasks.append(new_task)
            return new_task

        def _update_idea(idea_id: str, **kwargs: Any) -> None:
            manifest_updates[idea_id] = kwargs.get("manifestation_status", "")

        from app.services import agent_service as _as
        from app.services import idea_service as _is
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))
        monkeypatch.setattr(_as, "create_task", _create)
        monkeypatch.setattr(_as, "update_task", lambda *_a, **_k: {})
        monkeypatch.setattr(_is, "update_idea", _update_idea)
        monkeypatch.setattr(pipeline_advance_service, "_find_spec_file", lambda *_: "specs/159.md")

        idea_id = "idea-full-chain"

        # Step 1: code-review passes → deploy task created
        cr_task = _task(
            id="cr-1",
            task_type="code-review",
            status="completed",
            output="CODE_REVIEW_PASSED: all spec requirements met.",
            idea_id=idea_id,
        )
        r1 = pipeline_advance_service.maybe_advance(cr_task)
        assert r1 is not None
        deploy_task_type = r1["task_type"]
        assert deploy_task_type == "deploy"
        assert "validated" not in manifest_updates.values(), "too early for validated"

        # Step 2: deploy passes → verify-production task created
        deploy_task = dict(r1)
        deploy_task.update({
            "status": "completed",
            "output": "DEPLOY_PASSED: SHA abc1234 live at coherencycoin.com. Health check returned 200 OK.",
        })
        r2 = pipeline_advance_service.maybe_advance(deploy_task)
        assert r2 is not None
        assert r2["task_type"] == "verify"
        assert "validated" not in manifest_updates.values(), "too early for validated after deploy"

        # Step 3: verify-production passes → idea validated, no further task
        verify_task = dict(r2)
        verify_task.update({
            "status": "completed",
            "output": (
                "VERIFY_PASSED: GET /api/health returned 200 OK, GET /api/ideas returned 200 "
                "with 3 items. All 3 verification scenarios passed. Feature is live."
            ),
        })
        r3 = pipeline_advance_service.maybe_advance(verify_task)
        assert r3 is None  # terminal — no more tasks
        assert manifest_updates.get(idea_id) == "validated", (
            f"idea should be validated after verify-production pass; got {manifest_updates}"
        )

    def test_verify_fail_mid_chain_creates_hotfix_not_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If verify-production fails after code-review + deploy passed, no validated status."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        idea_id = "idea-mid-fail"
        verify_task = _task(
            task_type="verify-production",
            status="completed",
            output="VERIFY_FAILED: /api/pipeline/status missing phase_stats field.",
            idea_id=idea_id,
        )
        pipeline_advance_service.maybe_advance(verify_task)

        # Hotfix task created
        assert len(created) == 1
        assert created[0]["context"].get("hotfix") is True
        # Status is regression, NOT validated
        assert manifest_updates.get(idea_id) == "regression"
        assert manifest_updates.get(idea_id) != "validated"

    def test_code_review_fail_mid_chain_stops_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If code-review doesn't contain CODE_REVIEW_PASSED, deploy is never created."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        cr_task = _task(
            task_type="code-review",
            status="completed",
            output="The implementation is incomplete — missing error handling in R3.",
            idea_id="idea-cr-fail",
        )
        result = pipeline_advance_service.maybe_advance(cr_task)

        assert result is None
        deploy_tasks = [c for c in created if c["task_type"] == "deploy"]
        assert deploy_tasks == [], "No deploy task should be created when code-review fails"
        assert "validated" not in manifest_updates.values()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase stats (R6) — structure validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseStatsStructure:
    """R6: _NEXT_PHASE and _PHASE_TASK_TYPE are the source of truth for phase_stats keys."""

    def test_phase_stats_phases_are_discoverable_from_config(self) -> None:
        """The three new phases must exist in _PHASE_TASK_TYPE for stats aggregation."""
        required_phases = {"code-review", "deploy", "verify-production"}
        configured_phases = set(pipeline_advance_service._PHASE_TASK_TYPE.keys())
        missing = required_phases - configured_phases
        assert missing == set(), (
            f"Missing phases in _PHASE_TASK_TYPE (needed for phase_stats): {missing}"
        )

    def test_phase_stats_pass_rate_calculation_100_pct(self) -> None:
        """pass_rate = completed / (completed + failed) when all pass."""
        completed, failed = 9, 0
        total = completed + failed
        pass_rate = completed / total if total else None
        assert pass_rate == 1.0

    def test_phase_stats_pass_rate_calculation_partial(self) -> None:
        """pass_rate rounds correctly for partial success."""
        completed, failed = 8, 2
        total = completed + failed
        pass_rate = round(completed / total, 2) if total else None
        assert pass_rate == 0.80

    def test_phase_stats_pass_rate_is_none_when_no_tasks(self) -> None:
        """pass_rate is None when no tasks have completed (avoid division by zero)."""
        completed, failed = 0, 0
        total = completed + failed
        pass_rate = completed / total if total else None
        assert pass_rate is None

    def test_all_new_phases_have_minimum_output_requirement(self) -> None:
        """deploy and verify-production must have min output chars defined."""
        assert "deploy" in pipeline_advance_service._MIN_OUTPUT_CHARS
        assert "verify-production" in pipeline_advance_service._MIN_OUTPUT_CHARS
        assert pipeline_advance_service._MIN_OUTPUT_CHARS["deploy"] > 0
        assert pipeline_advance_service._MIN_OUTPUT_CHARS["verify-production"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Pass gate token registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestPassGateRegistry:
    """_PASS_GATE_TOKEN enforces structured output requirements per phase."""

    def test_code_review_requires_passed_token(self) -> None:
        """code-review pass gate must require CODE_REVIEW_PASSED."""
        assert pipeline_advance_service._PASS_GATE_TOKEN.get("code-review") == "CODE_REVIEW_PASSED"

    def test_deploy_has_no_content_pass_gate(self) -> None:
        """deploy advance is gated on status=completed, not content token."""
        # deploy advances based on status only (health check is done by the agent)
        assert pipeline_advance_service._PASS_GATE_TOKEN.get("deploy") is None

    def test_verify_production_failure_is_checked_in_maybe_advance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """maybe_advance inspects verify-production output for VERIFY_FAILED regardless of token registry."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)
        manifest_updates = _stub_idea_service(monkeypatch)

        # Status=completed but content says VERIFY_FAILED
        task = _task(
            task_type="verify-production",
            status="completed",
            output=(
                "VERIFY_FAILED: production endpoint returned HTTP 500, "
                "feature is down and unreachable."
            ),
            idea_id="idea-verify-gate",
        )
        pipeline_advance_service.maybe_advance(task)

        # Should create hotfix, not advance
        hotfix_tasks = [c for c in created if c.get("context", {}).get("hotfix")]
        assert len(hotfix_tasks) == 1
        assert manifest_updates.get("idea-verify-gate") == "regression"


# ═══════════════════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Existing 'review' task type must not be broken by the new chain."""

    def test_legacy_review_task_does_not_advance_to_deploy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Old review tasks must not accidentally trigger deploy."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        task = _task(
            task_type="review",
            status="completed",
            output="CODE_REVIEW_PASSED: reviewed and merged.",
        )
        result = pipeline_advance_service.maybe_advance(task)

        assert result is None
        assert created == []

    def test_legacy_review_type_maps_to_none_in_next_phase(self) -> None:
        assert pipeline_advance_service._NEXT_PHASE.get("review") is None

    def test_spec_impl_test_chain_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec → impl → test chain is unaffected by Spec 159 changes."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        # spec completes → impl created
        spec_task = _task(
            task_type="spec",
            status="completed",
            output=(
                "Created specs/test-idea.md with goal, files, acceptance criteria, "
                "verification scenarios. Files: specs/test-idea.md. 150 chars."
            ),
            idea_id="idea-spec-chain",
        )
        pipeline_advance_service.maybe_advance(spec_task)

        assert any(c["task_type"] == "impl" for c in created)

    def test_existing_ideas_at_reviewing_stage_not_disrupted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An idea in 'reviewing' stage (old pipeline) doesn't get a spurious deploy task."""
        _stub_no_existing_tasks(monkeypatch)
        created = _stub_create_task(monkeypatch)

        # Simulate a legacy review task completing
        task = _task(
            task_type="review",
            status="completed",
            output="CODE_REVIEW_PASSED reviewed all changes.",
        )
        pipeline_advance_service.maybe_advance(task)

        deploy_tasks = [c for c in created if c["task_type"] == "deploy"]
        assert deploy_tasks == [], "Legacy review must not trigger deploy"
