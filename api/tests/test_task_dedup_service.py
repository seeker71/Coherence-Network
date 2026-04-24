"""Tests for the task dedup service — prevents duplicate tasks per idea+phase.

Covers:
  1. Completed spec phase is detected (should_skip=True)
  2. Skip-ahead when next phase already completed
  3. Retry budget exhausted after MAX_RETRIES_PER_PHASE failures
  4. Per-phase cap prevents unbounded creation
  5. Bridge uses task history instead of stale stage
  6. Context propagation on skip-ahead
  7. Error handling — non-existent idea returns all-zero history
  8. Phase summary included in list_tasks_for_idea response
  9. Auto-retry respects dedup gate
  10. Fingerprint set on auto-advance/retry tasks
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from app.models.agent import TaskType, TaskStatus


# ── Test helpers ──────────────────────────────────────────────────────────

def _make_tasks_payload(
    idea_id: str = "test-dedup-A",
    groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a fake list_tasks_for_idea response."""
    groups = groups or []
    total = sum(g.get("count", 0) for g in groups)
    return {
        "idea_id": idea_id,
        "total": total,
        "groups": groups,
    }


def _make_group(
    task_type: str = "spec",
    completed: int = 0,
    failed: int = 0,
    pending: int = 0,
    running: int = 0,
    timed_out: int = 0,
    needs_decision: int = 0,
    tasks: list[dict] | None = None,
) -> dict[str, Any]:
    """Build a fake task group."""
    count = completed + failed + pending + running + timed_out + needs_decision
    status_counts = {
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "running": running,
        "timed_out": timed_out,
        "needs_decision": needs_decision,
    }
    if tasks is None:
        tasks = []
        for i in range(completed):
            tasks.append({
                "id": f"t-{task_type}-completed-{i}",
                "task_type": task_type,
                "status": "completed",
                "output": f"Completed output {i}",
                "context": {"idea_id": "test-idea"},
                "created_at": f"2025-01-0{i+1}T00:00:00Z",
                "updated_at": f"2025-01-0{i+1}T01:00:00Z",
            })
        for i in range(failed):
            tasks.append({
                "id": f"t-{task_type}-failed-{i}",
                "task_type": task_type,
                "status": "failed",
                "output": f"Failed output {i}",
                "context": {"idea_id": "test-idea"},
                "created_at": f"2025-01-0{i+1}T00:00:00Z",
                "updated_at": f"2025-01-0{i+1}T01:00:00Z",
            })
    return {
        "task_type": task_type,
        "count": count,
        "status_counts": status_counts,
        "tasks": tasks,
    }


_LONG_SPEC_OUTPUT = (
    "Spec written at specs/test.md. This is a comprehensive specification document "
    "covering all requirements, API endpoints, data models, and verification criteria "
    "for the feature. Created file: api/app/services/test_service.py. Modified file: "
    "api/app/routers/test_routes.py.\nDIF: trust=ok, verify=80, eventId=abc-123-def"
)


def _task(
    *,
    id: str = "t-001",
    task_type: str = "spec",
    status: str = "completed",
    output: str = _LONG_SPEC_OUTPUT,
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


# ── Scenario 1: Completed spec phase detected ────────────────────────────

class TestCheckIdeaPhaseHistory:

    def test_completed_phase_should_skip(self):
        """A phase with 1+ completed tasks should have should_skip=True."""
        from app.services.task_dedup_service import _extract_phase_history

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="spec", completed=1),
        ])
        history = _extract_phase_history(payload, "spec")

        assert history.should_skip is True
        assert history.completed_count == 1
        assert history.failed_count == 0
        assert history.active_count == 0
        assert history.retry_budget_left == 2

    def test_no_tasks_should_not_skip(self):
        """A phase with no tasks should have should_skip=False."""
        from app.services.task_dedup_service import _extract_phase_history

        payload = _make_tasks_payload(groups=[])
        history = _extract_phase_history(payload, "spec")

        assert history.should_skip is False
        assert history.completed_count == 0
        assert history.total_count == 0
        assert history.retry_budget_left == 2

    def test_only_failed_should_not_skip(self):
        """A phase with only failed tasks should not skip."""
        from app.services.task_dedup_service import _extract_phase_history

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="impl", failed=2),
        ])
        history = _extract_phase_history(payload, "impl")

        assert history.should_skip is False
        assert history.failed_count == 2
        assert history.retry_budget_left == 0


# ── Scenario 3: Retry budget exhausted ───────────────────────────────────

class TestRetryBudget:

    def test_retry_budget_exhausted_after_max_failures(self):
        """After MAX_RETRIES_PER_PHASE failures, retry_budget_left should be 0."""
        from app.services.task_dedup_service import _extract_phase_history, MAX_RETRIES_PER_PHASE

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="impl", failed=MAX_RETRIES_PER_PHASE),
        ])
        history = _extract_phase_history(payload, "impl")

        assert history.retry_budget_left == 0
        assert history.should_skip is False

    def test_timed_out_counts_toward_budget(self):
        """timed_out status counts toward retry budget equally with failed."""
        from app.services.task_dedup_service import _extract_phase_history

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="impl", timed_out=2),
        ])
        history = _extract_phase_history(payload, "impl")

        assert history.failed_count == 2  # timed_out counted as failed
        assert history.retry_budget_left == 0

    def test_mixed_failed_and_timed_out(self):
        """Both failed + timed_out eat into the retry budget."""
        from app.services.task_dedup_service import _extract_phase_history

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="impl", failed=1, timed_out=1),
        ])
        history = _extract_phase_history(payload, "impl")

        assert history.failed_count == 2
        assert history.retry_budget_left == 0


# ── Scenario 6: Context propagation on skip-ahead ────────────────────────

class TestBuildSkipContext:

    def test_propagates_impl_branch(self):
        """Skip context should propagate impl_branch from completed impl task."""
        from app.services.task_dedup_service import build_skip_context

        payload = _make_tasks_payload(
            idea_id="test-dedup-F",
            groups=[
                {
                    "task_type": "impl",
                    "count": 1,
                    "status_counts": {"completed": 1},
                    "tasks": [{
                        "id": "t-impl-1",
                        "task_type": "impl",
                        "status": "completed",
                        "context": {
                            "idea_id": "test-dedup-F",
                            "impl_branch": "feat/test-dedup-F",
                        },
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T01:00:00Z",
                    }],
                },
            ],
        )

        ctx = build_skip_context("test-dedup-F", ["impl"], payload)
        assert ctx["impl_branch"] == "feat/test-dedup-F"
        assert ctx["idea_id"] == "test-dedup-F"

    def test_propagates_spec_file_and_pr(self):
        """Skip context should propagate spec_file and pr_url."""
        from app.services.task_dedup_service import build_skip_context

        payload = _make_tasks_payload(
            idea_id="test-dedup-G",
            groups=[
                {
                    "task_type": "spec",
                    "count": 1,
                    "status_counts": {"completed": 1},
                    "tasks": [{
                        "id": "t-spec-1",
                        "task_type": "spec",
                        "status": "completed",
                        "context": {
                            "idea_id": "test-dedup-G",
                            "spec_file": "specs/test-dedup-G.md",
                        },
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T01:00:00Z",
                    }],
                },
                {
                    "task_type": "impl",
                    "count": 1,
                    "status_counts": {"completed": 1},
                    "tasks": [{
                        "id": "t-impl-1",
                        "task_type": "impl",
                        "status": "completed",
                        "context": {
                            "idea_id": "test-dedup-G",
                            "impl_branch": "feat/test-dedup-G",
                            "pr_url": "https://github.com/example/pr/123",
                        },
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T01:00:00Z",
                    }],
                },
            ],
        )

        ctx = build_skip_context("test-dedup-G", ["spec", "impl"], payload)
        assert ctx["spec_file"] == "specs/test-dedup-G.md"
        assert ctx["impl_branch"] == "feat/test-dedup-G"
        assert ctx["pr_url"] == "https://github.com/example/pr/123"

    def test_empty_skipped_phases(self):
        """No skipped phases returns minimal context."""
        from app.services.task_dedup_service import build_skip_context

        payload = _make_tasks_payload(groups=[])
        ctx = build_skip_context("test-idea", [], payload)
        assert ctx == {"idea_id": "test-idea"}


# ── Scenario 7: Error handling — non-existent idea ───────────────────────

class TestErrorHandling:

    def test_unknown_idea_returns_all_zeros(self):
        """check_idea_phase_history for unknown idea returns all-zero history."""
        from app.services.task_dedup_service import check_idea_phase_history

        # Patch list_tasks_for_idea to return empty
        with patch("app.services.agent_service_list.list_tasks_for_idea") as mock_ltfi:
            mock_ltfi.return_value = {"idea_id": "nonexistent", "total": 0, "groups": []}
            history = check_idea_phase_history("nonexistent", "spec")

        assert history.completed_count == 0
        assert history.failed_count == 0
        assert history.active_count == 0
        assert history.should_skip is False
        assert history.retry_budget_left == 2

    def test_exception_returns_all_zeros(self):
        """On exception, check_idea_phase_history returns all-zero (fail-open)."""
        from app.services.task_dedup_service import check_idea_phase_history

        with patch("app.services.agent_service_list.list_tasks_for_idea") as mock_ltfi:
            mock_ltfi.side_effect = Exception("DB down")
            history = check_idea_phase_history("broken-idea", "spec")

        assert history.completed_count == 0
        assert history.should_skip is False


# ── Scenario 8: Phase summary in response ────────────────────────────────

class TestPhaseSummary:

    def test_compute_phase_summary(self):
        """compute_phase_summary returns per-phase dedup stats."""
        from app.services.task_dedup_service import compute_phase_summary

        payload = _make_tasks_payload(groups=[
            _make_group(task_type="spec", completed=1),
            _make_group(task_type="impl", failed=2),
            _make_group(task_type="test", pending=1),
        ])
        summary = compute_phase_summary(payload)

        assert "spec" in summary
        assert summary["spec"]["completed"] == 1
        assert summary["spec"]["should_skip"] is True
        assert summary["spec"]["retry_budget_left"] == 2

        assert "impl" in summary
        assert summary["impl"]["failed"] == 2
        assert summary["impl"]["should_skip"] is False
        assert summary["impl"]["retry_budget_left"] == 0

        assert "test" in summary
        assert summary["test"]["active"] == 1
        assert summary["test"]["should_skip"] is False

    def test_empty_payload(self):
        """Empty payload returns empty summary."""
        from app.services.task_dedup_service import compute_phase_summary

        summary = compute_phase_summary({"groups": []})
        assert summary == {}


# ── Scenario 9: Auto-retry dedup gate ────────────────────────────────────

class TestAutoRetryDedupGate:

    def test_retry_skipped_when_phase_completed(self, monkeypatch):
        """maybe_retry returns None when phase already completed (R4)."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(task_type="impl", status="failed", idea_id="idea-retry")

        # Patch dedup gate to say phase is completed
        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(completed_count=1),
        )

        result = pas.maybe_retry(task)
        assert result is None

    def test_retry_skipped_when_budget_exhausted(self, monkeypatch):
        """maybe_retry returns None when retry budget is 0 (R4)."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(task_type="impl", status="failed", idea_id="idea-retry-2")

        escalated = []
        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(failed_count=2),
        )
        monkeypatch.setattr(
            pas, "_escalate_or_autofix",
            lambda t, tt, iid, rc: escalated.append((tt, iid)),
        )

        result = pas.maybe_retry(task)
        assert result is None
        assert len(escalated) == 1
        assert escalated[0] == ("impl", "idea-retry-2")


# ── Scenario 10: Fingerprint on auto-advance tasks (R8) ──────────────────

class TestAutoAdvanceFingerprint:

    def test_advance_sets_fingerprint(self, monkeypatch):
        """maybe_advance creates task with deterministic fingerprint (R8)."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(
            task_type="spec",
            status="completed",
            idea_id="idea-fp",
            output="Spec written at specs/test.md. This is a comprehensive specification document covering all requirements, API endpoints, data models, and verification criteria for the feature.\nDIF: trust=ok, verify=80, eventId=abc\n.py modified",
        )

        # Dedup gate: impl phase is clear
        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(),
        )
        monkeypatch.setattr(pas, "_find_spec_file", lambda *_: "specs/test.md")
        monkeypatch.setattr(pas, "_build_failure_memory", lambda *_a, **_k: "")

        created_tasks: list[dict] = []

        def fake_create(data):
            t = {
                "id": "t-new",
                "task_type": data.task_type.value if hasattr(data.task_type, "value") else data.task_type,
                "status": "pending",
                "context": data.context,
            }
            created_tasks.append(t)
            return t

        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "create_task", fake_create)

        # Patch list_tasks_for_idea for skip context
        monkeypatch.setattr(
            "app.services.agent_service_list.list_tasks_for_idea",
            lambda idea_id: {"idea_id": idea_id, "total": 0, "groups": []},
        )

        result = pas.maybe_advance(task)
        assert result is not None
        assert len(created_tasks) == 1
        ctx = created_tasks[0]["context"]
        assert ctx["task_fingerprint"] == "idea-fp:impl:auto"

    def test_retry_caps_oversized_direction(self, monkeypatch):
        """maybe_retry truncates direction+partial_work so the new task stays
        under the 3000-char OVERSIZED_DIRECTION gate (DG-002).

        Regression: before this cap, a 2900-char original direction + 5000-char
        git-diff partial + 800-char failure memory produced ~8700-char retry
        directions that the API rejected to needs_decision, piling up sediment.
        """
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        # Original direction at the seed-time cap (2900 chars)
        original = "x" * 2900
        # Partial work from huge git diff (up to 5000 chars)
        huge_diff = "diff --git a/f\n" + ("+line\n" * 1000)
        task = _task(
            task_type="impl",
            status="timed_out",
            idea_id="idea-oversized",
            extra_context={"diff_content": huge_diff},
        )
        task["direction"] = original

        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(failed_count=1),
        )
        # Max-size failure memory to stress the budget
        monkeypatch.setattr(pas, "_build_failure_memory", lambda *_a, **_k: "f" * 800)

        captured: list[dict] = []

        def fake_create(data):
            captured.append({"direction": data.direction, "context": data.context})
            return {"id": "t-capped", "task_type": "impl", "status": "pending",
                    "context": data.context}

        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "create_task", fake_create)
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))

        result = pas.maybe_retry(task)
        assert result is not None
        assert len(captured) == 1
        retry_direction = captured[0]["direction"]
        # Must stay under the API gate
        assert len(retry_direction) <= 3000, (
            f"retry direction is {len(retry_direction)} chars — "
            f"OVERSIZED_DIRECTION gate would reject it"
        )
        # Partial-work framing must survive the truncation
        assert "PARTIAL WORK FROM PREVIOUS ATTEMPT" in retry_direction
        # Failure memory must survive (it's smallest, highest-signal)
        assert "f" * 100 in retry_direction

    def test_retry_sets_fingerprint(self, monkeypatch):
        """maybe_retry creates task with deterministic fingerprint (R8)."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(
            task_type="impl",
            status="failed",
            idea_id="idea-fp-retry",
            output="Build error\n.py file modified",
        )

        # Dedup gate: impl phase has room
        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(failed_count=1),
        )
        monkeypatch.setattr(pas, "_build_failure_memory", lambda *_a, **_k: "")

        created_tasks: list[dict] = []

        def fake_create(data):
            t = {
                "id": "t-retry-new",
                "task_type": data.task_type.value if hasattr(data.task_type, "value") else data.task_type,
                "status": "pending",
                "context": data.context,
            }
            created_tasks.append(t)
            return t

        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "create_task", fake_create)
        monkeypatch.setattr(_as, "list_tasks", lambda **_k: ([], 0, 0))

        result = pas.maybe_retry(task)
        assert result is not None
        assert len(created_tasks) == 1
        ctx = created_tasks[0]["context"]
        assert ctx["task_fingerprint"] == "idea-fp-retry:impl:auto"


# ── Scenario 2: Skip-ahead in auto-advance ───────────────────────────────

class TestSkipAhead:

    def test_advance_skips_completed_phase(self, monkeypatch):
        """maybe_advance skips impl (already completed) and creates test task."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(
            task_type="spec",
            status="completed",
            idea_id="idea-skip",
            output="Spec written at specs/test.md. This is a comprehensive specification document covering all requirements, API endpoints, data models, and verification criteria for the feature.\nDIF: trust=ok, verify=80, eventId=abc\n.py modified",
        )

        call_count = {"impl": 0, "test": 0}

        def fake_history(idea_id, phase):
            call_count[phase] = call_count.get(phase, 0) + 1
            if phase == "impl":
                return IdeaPhaseHistory(completed_count=1)
            return IdeaPhaseHistory()

        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            fake_history,
        )
        monkeypatch.setattr(pas, "_find_spec_file", lambda *_: "specs/test.md")
        monkeypatch.setattr(pas, "_build_failure_memory", lambda *_a, **_k: "")

        # Provide skip context
        monkeypatch.setattr(
            "app.services.agent_service_list.list_tasks_for_idea",
            lambda idea_id: {
                "idea_id": idea_id,
                "total": 1,
                "groups": [{
                    "task_type": "impl",
                    "count": 1,
                    "status_counts": {"completed": 1},
                    "tasks": [{
                        "id": "t-impl-done",
                        "task_type": "impl",
                        "status": "completed",
                        "context": {"idea_id": idea_id, "impl_branch": "feat/idea-skip"},
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T01:00:00Z",
                    }],
                }],
            },
        )

        created_tasks: list[dict] = []

        def fake_create(data):
            t = {
                "id": "t-test-new",
                "task_type": data.task_type.value if hasattr(data.task_type, "value") else data.task_type,
                "status": "pending",
                "context": data.context,
            }
            created_tasks.append(t)
            return t

        from app.services import agent_service as _as
        monkeypatch.setattr(_as, "create_task", fake_create)

        result = pas.maybe_advance(task)
        assert result is not None
        assert created_tasks[0]["task_type"] == "test"
        # R7: impl_branch propagated from skip context
        assert created_tasks[0]["context"].get("impl_branch") == "feat/idea-skip"

    def test_advance_all_phases_completed(self, monkeypatch):
        """maybe_advance returns None when all downstream phases completed."""
        from app.services import pipeline_advance_service as pas
        from app.services.task_dedup_service import IdeaPhaseHistory

        task = _task(
            task_type="spec",
            status="completed",
            idea_id="idea-all-done",
            output="Spec written at specs/test.md. This is a comprehensive specification document covering all requirements, API endpoints, data models, and verification criteria for the feature.\nDIF: trust=ok, verify=80, eventId=abc\n.py modified",
        )

        monkeypatch.setattr(
            "app.services.task_dedup_service.check_idea_phase_history",
            lambda idea_id, phase: IdeaPhaseHistory(completed_count=1),
        )

        result = pas.maybe_advance(task)
        assert result is None


# ── Bridge integration test (R5) ─────────────────────────────────────────

class TestBridgeDetermineTaskType:

    def test_bridge_uses_task_history(self):
        """Bridge determine_task_type uses live task history, not stale stage."""
        import sys
        from pathlib import Path

        # Resolve scripts/ relative to this test file (api/tests/test_*.py -> repo/scripts)
        bridge_path = str(Path(__file__).resolve().parents[2] / "scripts")
        if bridge_path not in sys.path:
            sys.path.insert(0, bridge_path)

        import idea_to_task_bridge as bridge

        # Patch _get to return task data showing spec completed
        original_get = bridge._get

        def fake_get(path, params=None):
            if "/tasks" in path:
                return {
                    "idea_id": "test-bridge",
                    "total": 1,
                    "groups": [{
                        "task_type": "spec",
                        "count": 1,
                        "status_counts": {"completed": 1},
                        "tasks": [],
                    }],
                    "phase_summary": {
                        "spec": {
                            "completed": 1,
                            "failed": 0,
                            "active": 0,
                            "should_skip": True,
                            "retry_budget_left": 2,
                        },
                    },
                }
            return original_get(path, params)

        bridge._get = fake_get
        try:
            # Stage is stale (none) but task history shows spec completed
            idea = {"id": "test-bridge", "stage": "none"}
            task_type = bridge.determine_task_type(idea)
            assert task_type == "impl"  # Should advance past spec
        finally:
            bridge._get = original_get

    def test_bridge_all_phases_complete(self):
        """Bridge returns None when all phases complete."""
        import sys
        from pathlib import Path

        bridge_path = str(Path(__file__).resolve().parents[2] / "scripts")
        if bridge_path not in sys.path:
            sys.path.insert(0, bridge_path)

        import idea_to_task_bridge as bridge

        original_get = bridge._get

        def fake_get(path, params=None):
            if "/tasks" in path:
                return {
                    "idea_id": "test-bridge-done",
                    "total": 6,
                    "groups": [],
                    "phase_summary": {
                        phase: {
                            "completed": 1,
                            "failed": 0,
                            "active": 0,
                            "should_skip": True,
                            "retry_budget_left": 2,
                        }
                        for phase in ["spec", "impl", "test", "code-review", "deploy", "verify-production"]
                    },
                }
            return original_get(path, params)

        bridge._get = fake_get
        try:
            idea = {"id": "test-bridge-done", "stage": "none"}
            task_type = bridge.determine_task_type(idea)
            assert task_type is None
        finally:
            bridge._get = original_get
