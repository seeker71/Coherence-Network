"""Tests for auto-heal from diagnostics service (spec 114).

Tests exercise real service logic. The task_creator parameter captures the real
AgentTaskCreate object (which passes full Pydantic validation) instead of mocking
the creation call. This validates the complete data flow from error classification
through to a valid task creation request.
"""

from __future__ import annotations

from pathlib import Path

from app.models.agent import AgentTaskCreate, TaskType


def _store(tmp_path: Path) -> Path:
    return tmp_path / "heal_records.json"


def _make_failed_task(
    task_id: str = "task-001",
    output: str | None = "Traceback: KeyError",
    error_category: str | None = None,
    error_summary: str | None = None,
    context: dict | None = None,
) -> dict:
    return {
        "id": task_id,
        "status": "failed",
        "output": output,
        "error_category": error_category,
        "error_summary": error_summary,
        "context": context or {},
    }


class TaskCreationCapture:
    """Captures AgentTaskCreate objects and validates them through real Pydantic validation.

    This is NOT a mock — it validates the full AgentTaskCreate model (direction length,
    task_type enum, context structure) and only replaces the side-effecting DB write.
    """

    def __init__(self) -> None:
        self.calls: list[AgentTaskCreate] = []
        self.created: list[dict] = []

    def __call__(self, data: AgentTaskCreate) -> dict:
        # Verify the input is a REAL validated AgentTaskCreate, not a raw dict
        assert isinstance(data, AgentTaskCreate), f"Expected AgentTaskCreate, got {type(data)}"
        assert data.task_type == TaskType.HEAL, f"Expected HEAL, got {data.task_type}"
        assert len(data.direction) >= 1, "Direction must be non-empty"
        assert len(data.direction) <= 5000, "Direction exceeds max length"
        assert isinstance(data.context, dict), "Context must be a dict"

        self.calls.append(data)
        task = {
            "id": f"heal-{len(self.created)}",
            "task_type": data.task_type.value,
            "direction": data.direction,
            "status": "pending",
            "context": data.context,
        }
        self.created.append(task)
        return task


def test_heal_strategies_cover_all_categories() -> None:
    from app.services.auto_heal_service import HEAL_STRATEGIES

    expected = {"timeout", "executor_crash", "provider_error", "validation_failure", "unknown"}
    assert set(HEAL_STRATEGIES.keys()) == expected
    for cat, strategy in HEAL_STRATEGIES.items():
        assert "direction_template" in strategy
        assert "max_retries" in strategy
        assert "cooldown_seconds" in strategy
        assert 1 <= strategy["max_retries"] <= 3
        assert strategy["cooldown_seconds"] > 0
        # Verify direction template is formattable with expected placeholders
        formatted = strategy["direction_template"].format(
            source_task_id="test-123",
            error_summary="test error",
        )
        assert "test-123" in formatted
        assert "test error" in formatted


def test_maybe_create_heal_task_eligible(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    capture = TaskCreationCapture()
    failed = _make_failed_task(output="Process exited with code 137 (SIGKILL)")
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=capture)

    assert result is not None
    assert result["task_type"] == "heal"
    assert result["status"] == "pending"
    assert len(capture.calls) == 1

    # Verify the AgentTaskCreate was built correctly
    create_data = capture.calls[0]
    assert create_data.task_type == TaskType.HEAL
    assert "SIGKILL" in create_data.direction or "crashed" in create_data.direction
    assert create_data.context["error_category"] == "executor_crash"
    assert create_data.context["source_task_id"] == "task-001"


def test_maybe_create_heal_task_cooldown_suppressed(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    capture = TaskCreationCapture()
    sp = _store(tmp_path)

    # First call — should create
    failed1 = _make_failed_task(task_id="task-001", output="rate limit exceeded")
    result1 = maybe_create_heal_task(failed1, store_path=sp, task_creator=capture)
    assert result1 is not None
    assert result1["context"]["error_category"] == "provider_error"

    # Second call for SAME category within cooldown — must be suppressed
    failed2 = _make_failed_task(task_id="task-002", output="HTTP 429 Too Many Requests")
    result2 = maybe_create_heal_task(failed2, store_path=sp, task_creator=capture)
    assert result2 is None
    assert len(capture.created) == 1  # only first was created

    # Verify cooldown record was persisted to the store
    import json
    records = json.loads(sp.read_text())
    assert len(records) == 1
    assert records[0]["error_category"] == "provider_error"
    assert records[0]["source_task_id"] == "task-001"


def test_maybe_create_heal_task_retry_limit(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    capture = TaskCreationCapture()

    # Task already retried 3 times — timeout max_retries is 2
    failed = _make_failed_task(
        output="timeout after 300s",
        context={"retry_count": 3},
    )
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=capture)
    assert result is None
    assert len(capture.created) == 0

    # Also test at exactly the limit: retry_count == max_retries (2 for timeout)
    failed_at_limit = _make_failed_task(
        output="timeout after 300s",
        context={"retry_count": 2},
    )
    result_at_limit = maybe_create_heal_task(failed_at_limit, store_path=_store(tmp_path), task_creator=capture)
    assert result_at_limit is None


def test_maybe_create_heal_task_already_healed(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    capture = TaskCreationCapture()

    # Task already has a heal task — must not create another
    failed = _make_failed_task(
        output="crash",
        context={"heal_task_id": "heal-existing-123"},
    )
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=capture)
    assert result is None
    assert len(capture.created) == 0


def test_heal_task_context_fields(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    capture = TaskCreationCapture()
    failed = _make_failed_task(task_id="task-xyz", output="AssertionError: expected 200")
    maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=capture)

    assert len(capture.calls) == 1
    data = capture.calls[0]

    # Verify all required context fields (R4)
    ctx = data.context
    assert ctx["source_task_id"] == "task-xyz"
    assert ctx["error_category"] == "validation_failure"
    assert ctx["error_summary"] == "AssertionError: expected 200"
    assert ctx["retry_count"] == 1  # first retry
    assert ctx["strategy_name"] == "validation_failure"

    # Verify the direction contains the error info
    assert "task-xyz" in data.direction
    assert "AssertionError" in data.direction


def test_auto_heal_stats_exact_values(tmp_path) -> None:
    from app.services.auto_heal_service import compute_auto_heal_stats, maybe_create_heal_task

    capture = TaskCreationCapture()
    sp = _store(tmp_path)

    # Create heals for 2 tasks
    maybe_create_heal_task(_make_failed_task("t1", "timeout hit"), store_path=sp, task_creator=capture)
    maybe_create_heal_task(_make_failed_task("t2", "Traceback crash"), store_path=sp, task_creator=capture)

    # Verify exact context of created tasks
    assert len(capture.created) == 2
    assert capture.calls[0].context["error_category"] == "timeout"
    assert capture.calls[1].context["error_category"] == "executor_crash"

    # Compute stats with all failed tasks (including one that wasn't healed)
    all_failed = [
        _make_failed_task("t1", "timeout hit"),
        _make_failed_task("t2", "Traceback crash"),
        _make_failed_task("t3", "some unknown error"),
    ]
    stats = compute_auto_heal_stats(all_failed, store_path=sp)

    # Exact values, not just key presence
    assert stats["total_failed"] == 3
    assert stats["heals_created"] == 2
    assert stats["heal_rate"] == 0.67  # round(2/3, 2)

    by_cat = stats["by_category"]
    assert by_cat["timeout"] == {"failed": 1, "healed": 1, "suppressed": 0}
    assert by_cat["executor_crash"] == {"failed": 1, "healed": 1, "suppressed": 0}
    assert by_cat["unknown"] == {"failed": 1, "healed": 0, "suppressed": 1}
