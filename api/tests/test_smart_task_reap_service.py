"""Unit tests for smart task reaping helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.smart_task_reap_service import (
    classify_log_error_class,
    partial_output_ratio,
    runners_matching_claim,
    task_stale_age_minutes,
)


def test_task_stale_age_minutes_prefers_updated_at() -> None:
    now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    task = {
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "updated_at": (now - timedelta(minutes=10)).isoformat(),
    }
    age = task_stale_age_minutes(task, now=now)
    assert age is not None
    assert 9.0 <= age <= 11.0


def test_runners_matching_claim_exact() -> None:
    r = runners_matching_claim(
        "host:1234",
        [{"runner_id": "host:1234", "online": True}],
    )
    assert r is not None
    assert r["runner_id"] == "host:1234"


def test_classify_log_error_class_crash() -> None:
    assert classify_log_error_class("Process killed with SIGKILL") == "process_crash_or_oom"


def test_partial_output_ratio() -> None:
    assert partial_output_ratio("x" * 500, 2000) == 0.25
