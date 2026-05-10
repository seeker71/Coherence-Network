"""Tests for the agent-execution-lifecycle-hooks spec
(specs/agent-execution-lifecycle-hooks.md).

Lifecycle hooks fire at task transitions (begin / heartbeat / outcome /
hook_error). Custom hooks can register; failures in one hook don't
bring down dispatch (per the spec's resilience requirement).

Spec test selector: -k "lifecycle or hook_error or lifecycle_summary".
Test names below match those filters.
"""
from __future__ import annotations

import pytest

from app.services import agent_execution_hooks as hooks


@pytest.fixture(autouse=True)
def reset_hooks():
    hooks.clear_lifecycle_hooks()
    yield
    hooks.clear_lifecycle_hooks()


def test_lifecycle_hook_registration_adds_to_list():
    captured = []

    def my_hook(payload):
        captured.append(payload)

    hooks.register_lifecycle_hook(my_hook)
    assert my_hook in hooks.list_lifecycle_hooks()


def test_lifecycle_clear_removes_all_registered():
    hooks.register_lifecycle_hook(lambda payload: None)
    hooks.register_lifecycle_hook(lambda payload: None)
    assert len(hooks.list_lifecycle_hooks()) == 2
    hooks.clear_lifecycle_hooks()
    assert hooks.list_lifecycle_hooks() == []


def test_lifecycle_dispatch_fires_each_registered_hook():
    captured = []
    hooks.register_lifecycle_hook(lambda p: captured.append(("a", p["event"])))
    hooks.register_lifecycle_hook(lambda p: captured.append(("b", p["event"])))

    hooks.dispatch_lifecycle_event(
        "begin",
        task_id="task-xyz",
        task={"task_type": "spec", "status": "running"},
    )
    assert ("a", "begin") in captured
    assert ("b", "begin") in captured


def test_lifecycle_hook_error_does_not_block_other_hooks():
    """A throwing hook must not bring down dispatch — surviving hooks
    still fire. Resilience is a stated requirement."""
    captured = []

    def crashing_hook(payload):
        raise RuntimeError("simulated hook crash")

    def good_hook(payload):
        captured.append(payload["event"])

    hooks.register_lifecycle_hook(crashing_hook)
    hooks.register_lifecycle_hook(good_hook)

    # Should not raise — the crashing hook is caught, good_hook still fires
    hooks.dispatch_lifecycle_event(
        "outcome",
        task_id="task-1",
        task={"task_type": "test", "status": "completed"},
    )
    assert "outcome" in captured


def test_lifecycle_summary_returns_dict():
    """summarize_lifecycle_events returns a dict shape (counts, recent
    events, etc.). Implementation reads the JSONL log; we just verify
    the contract returns a dict without raising."""
    result = hooks.summarize_lifecycle_events(seconds=60, limit=10)
    assert isinstance(result, dict)


def test_lifecycle_payload_carries_required_fields():
    captured = []
    hooks.register_lifecycle_hook(lambda p: captured.append(p))
    hooks.dispatch_lifecycle_event(
        "heartbeat",
        task_id="task-42",
        task={"task_type": "impl", "status": "running", "model": "claude-sonnet"},
    )
    assert captured
    p = captured[0]
    assert p["event"] == "heartbeat"
    assert p["task_id"] == "task-42"
    assert p["task_type"] == "impl"
    assert p["task_status"] == "running"
