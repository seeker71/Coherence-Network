"""Tests for auto-heal from diagnostics service (spec 114)."""

from __future__ import annotations

from pathlib import Path


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


def test_heal_strategies_cover_all_categories() -> None:
    from app.services.auto_heal_service import HEAL_STRATEGIES

    expected = {"timeout", "executor_crash", "provider_error", "validation_failure", "unknown"}
    assert set(HEAL_STRATEGIES.keys()) == expected
    for cat, strategy in HEAL_STRATEGIES.items():
        assert "direction_template" in strategy
        assert "max_retries" in strategy
        assert "cooldown_seconds" in strategy
        assert 1 <= strategy["max_retries"] <= 3


def test_maybe_create_heal_task_eligible(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    created_tasks: list[dict] = []

    def fake_creator(data) -> dict:
        task = {"id": f"heal-{len(created_tasks)}", "task_type": "heal", "direction": data.direction, "context": data.context}
        created_tasks.append(task)
        return task

    failed = _make_failed_task(output="Process exited with code 137 (SIGKILL)")
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=fake_creator)

    assert result is not None
    assert result["task_type"] == "heal"
    assert len(created_tasks) == 1


def test_maybe_create_heal_task_cooldown_suppressed(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    created_tasks: list[dict] = []

    def fake_creator(data) -> dict:
        task = {"id": f"heal-{len(created_tasks)}", "task_type": "heal", "direction": data.direction, "context": data.context}
        created_tasks.append(task)
        return task

    sp = _store(tmp_path)

    # First call — should create
    failed1 = _make_failed_task(task_id="task-001", output="rate limit exceeded")
    result1 = maybe_create_heal_task(failed1, store_path=sp, task_creator=fake_creator)
    assert result1 is not None

    # Second call for SAME category within cooldown — should be suppressed
    failed2 = _make_failed_task(task_id="task-002", output="HTTP 429 Too Many Requests")
    result2 = maybe_create_heal_task(failed2, store_path=sp, task_creator=fake_creator)
    assert result2 is None
    assert len(created_tasks) == 1  # only first was created


def test_maybe_create_heal_task_retry_limit(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    created_tasks: list[dict] = []

    def fake_creator(data) -> dict:
        task = {"id": f"heal-{len(created_tasks)}", "task_type": "heal", "direction": data.direction, "context": data.context}
        created_tasks.append(task)
        return task

    # Task already retried 3 times
    failed = _make_failed_task(
        output="timeout after 300s",
        context={"retry_count": 3},
    )
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=fake_creator)
    assert result is None
    assert len(created_tasks) == 0


def test_maybe_create_heal_task_already_healed(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    created_tasks: list[dict] = []

    def fake_creator(data) -> dict:
        task = {"id": f"heal-{len(created_tasks)}", "task_type": "heal", "direction": data.direction, "context": data.context}
        created_tasks.append(task)
        return task

    # Task already has a heal task
    failed = _make_failed_task(
        output="crash",
        context={"heal_task_id": "heal-existing-123"},
    )
    result = maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=fake_creator)
    assert result is None
    assert len(created_tasks) == 0


def test_heal_task_context_fields(tmp_path) -> None:
    from app.services.auto_heal_service import maybe_create_heal_task

    captured_data = []

    def fake_creator(data) -> dict:
        captured_data.append(data)
        return {"id": "heal-0", "task_type": "heal", "direction": data.direction, "context": data.context}

    failed = _make_failed_task(task_id="task-xyz", output="AssertionError: expected 200")
    maybe_create_heal_task(failed, store_path=_store(tmp_path), task_creator=fake_creator)

    assert len(captured_data) == 1
    ctx = captured_data[0].context
    assert ctx["source_task_id"] == "task-xyz"
    assert ctx["error_category"] == "validation_failure"
    assert "error_summary" in ctx
    assert "retry_count" in ctx
    assert "strategy_name" in ctx


def test_auto_heal_stats_shape(tmp_path) -> None:
    from app.services.auto_heal_service import compute_auto_heal_stats, maybe_create_heal_task

    created_tasks: list[dict] = []

    def fake_creator(data) -> dict:
        task = {"id": f"heal-{len(created_tasks)}", "task_type": "heal", "direction": data.direction, "context": data.context}
        created_tasks.append(task)
        return task

    sp = _store(tmp_path)

    # Create some heals
    maybe_create_heal_task(_make_failed_task("t1", "timeout hit"), store_path=sp, task_creator=fake_creator)
    maybe_create_heal_task(_make_failed_task("t2", "Traceback crash"), store_path=sp, task_creator=fake_creator)

    # Compute stats from records + a list of all failed tasks
    all_failed = [
        _make_failed_task("t1", "timeout hit"),
        _make_failed_task("t2", "Traceback crash"),
        _make_failed_task("t3", "some unknown error"),
    ]
    stats = compute_auto_heal_stats(all_failed, store_path=sp)

    assert "total_failed" in stats
    assert stats["total_failed"] == 3
    assert "heals_created" in stats
    assert stats["heals_created"] == 2
    assert "heal_rate" in stats
    assert "by_category" in stats
