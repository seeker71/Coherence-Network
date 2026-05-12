"""Stale-running pipeline monitoring tests.

The pipeline-observability-and-auto-review spec lists 23 requirements,
but its test path narrows to a specific concern: how the body
recognizes a *stale-running* task — one that has been claimed by a
runner and is still in `running` state past a threshold (default
1800s / 30 minutes). The detection runs in two places:

  · `telegram_report_formatter._stale_running_rows` — pure filter
    that turns `pipeline_status["running"]` rows into a list of
    those past the threshold. Used for the operator status reply
    so a glance at Telegram shows which runs are hung.

  · `runner_orphan_recovery_service.maybe_recover_on_idle_heartbeat`
    — the auto-failure path that runs when a runner heartbeat
    reports idle while still claiming tasks. Tested at the
    integration layer in other files; this file pins the pure
    detection contract.

Source under test:
    api/app/services/telegram_report_formatter.py::_stale_running_rows
    api/app/services/config_service.py::pipeline_stale_running_seconds default

Spec: specs/pipeline-observability-and-auto-review.md (slice: stale-
running detection)
"""

from __future__ import annotations

import pytest

from app.services import telegram_report_formatter as fmt


# ── _stale_running_rows — the pure filter contract ────────────────


def test_stale_running_filters_by_strict_greater_than_threshold():
    """Strict > threshold: a task running exactly at the threshold is
    *not* yet stale. Otherwise the auto-recovery path would flap on
    the boundary every poll."""
    rows = [
        {"id": "task-fresh", "running_seconds": 60},
        {"id": "task-at-threshold", "running_seconds": 1800},
        {"id": "task-past-threshold", "running_seconds": 1801},
        {"id": "task-way-past", "running_seconds": 7200},
    ]
    stale = fmt._stale_running_rows(rows, threshold_seconds=1800)
    ids = [r["id"] for r in stale]
    assert "task-fresh" not in ids
    assert "task-at-threshold" not in ids
    assert "task-past-threshold" in ids
    assert "task-way-past" in ids
    assert len(stale) == 2


def test_stale_running_silently_drops_invalid_rows():
    """Operator status reply must not crash on a malformed row. The
    pipeline_status payload can contain mix of dicts, strings, or
    rows missing the running_seconds field. The filter is tolerant."""
    rows = [
        {"id": "good", "running_seconds": 3000},
        None,                              # not a dict
        "not-a-dict-string",               # not a dict
        {"id": "missing-seconds"},         # no running_seconds key
        {"id": "null-seconds", "running_seconds": None},
        {"id": "string-seconds", "running_seconds": "twelve"},
        {"id": "good-2", "running_seconds": 5000},
    ]
    stale = fmt._stale_running_rows(rows, threshold_seconds=1800)
    ids = [r["id"] for r in stale]
    assert "good" in ids
    assert "good-2" in ids
    assert len(stale) == 2, (
        f"invalid rows must be silently filtered out; got {len(stale)}: {ids}"
    )


def test_stale_running_threshold_zero_includes_all_positive_durations():
    """When threshold is 0, every task with positive running_seconds is
    "past" the threshold by definition (>0 > 0). Useful for force-flush
    cleanup."""
    rows = [
        {"id": "zero", "running_seconds": 0},
        {"id": "one", "running_seconds": 1},
        {"id": "many", "running_seconds": 9999},
    ]
    stale = fmt._stale_running_rows(rows, threshold_seconds=0)
    ids = [r["id"] for r in stale]
    # 0 is not strictly > 0, so it's excluded; 1 and 9999 are.
    assert "zero" not in ids
    assert "one" in ids
    assert "many" in ids


def test_stale_running_empty_list_returns_empty():
    """No running tasks → no stale running. Baseline."""
    assert fmt._stale_running_rows([], threshold_seconds=1800) == []


def test_stale_running_preserves_row_dicts_intact():
    """Filtered rows must come back as the same dicts callers passed
    in — the operator status reply formats Task ID, claimed_by, and
    other fields from these rows. Mutating or stripping fields would
    break that downstream render."""
    original = {
        "id": "task-keep-intact",
        "running_seconds": 3600,
        "claimed_by": "runner-a",
        "worker_id": "agent-7",
        "task_type": "compose-spec",
    }
    stale = fmt._stale_running_rows([original], threshold_seconds=1800)
    assert len(stale) == 1
    kept = stale[0]
    # Same fields, same values, no surprise mutation.
    for key, value in original.items():
        assert kept[key] == value


def test_stale_running_threshold_default_is_thirty_minutes():
    """The pipeline_stale_running_seconds default in config_service is
    1800s (30 minutes). Pin the default so a refactor doesn't silently
    change the operator's mental model of "stale = >30min"."""
    from app.services import config_service

    cfg = config_service.get_config()
    threshold = cfg.get("pipeline_stale_running_seconds")
    assert threshold == 1800, (
        f"stale-running threshold default must stay at 1800s (30 min) "
        f"per the operator-status contract; got {threshold!r}"
    )
