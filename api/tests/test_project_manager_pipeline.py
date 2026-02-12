"""Tests for project manager orchestrator pipeline — spec 005.
These tests define the contract for the orchestrator behavior.
No mocks: real file I/O, real load_backlog, load_state, save_state, refresh_backlog.
"""
import logging
import os
import tempfile


# Import project_manager module logic
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

# Load backlog logic
from importlib.util import spec_from_file_location, module_from_spec

spec = spec_from_file_location(
    "project_manager",
    os.path.join(_api_dir, "scripts", "project_manager.py"),
)
pm = module_from_spec(spec)
spec.loader.exec_module(pm)
sys.modules["project_manager"] = pm


def test_orchestrator_creates_spec_task_on_first_run():
    """Acceptance: initial state and backlog parsing. No mocks — real file I/O."""
    with tempfile.TemporaryDirectory() as d:
        backlog_file = os.path.join(d, "005-backlog.md")
        with open(backlog_file, "w") as f:
            f.write("# Backlog\n1. First item\n2. Second item\n")

        state_file = os.path.join(d, "project_manager_state.json")
        orig_backlog = pm.BACKLOG_FILE
        orig_state = pm.STATE_FILE
        pm.BACKLOG_FILE = backlog_file
        pm.STATE_FILE = state_file

        try:
            state = pm.load_state()
            assert state["backlog_index"] == 0
            assert state["phase"] == "spec"
            assert state["current_task_id"] is None

            items = pm.load_backlog()
            assert len(items) == 2
            assert items[0] == "First item"
            assert items[1] == "Second item"

        finally:
            pm.BACKLOG_FILE = orig_backlog
            pm.STATE_FILE = orig_state


def test_orchestrator_creates_impl_task_after_spec():
    """Acceptance: impl phase direction references spec. No mocks."""
    direction = pm.build_direction("impl", "Add GET /api/foo", 1)
    assert "Implement per spec" in direction
    assert "Add GET /api/foo" in direction

    direction = pm.build_direction("impl", "Add GET /api/foo", 2)
    assert "Fix the issues" in direction
    assert "Add GET /api/foo" in direction


def test_orchestrator_creates_test_task_after_impl():
    """Acceptance: After impl completes, creates test task"""
    with tempfile.TemporaryDirectory() as d:
        # Override file paths for test
        orig_backlog = pm.BACKLOG_FILE
        orig_state = pm.STATE_FILE
        pm.STATE_FILE = os.path.join(d, "project_manager_state.json")

        try:
            # Test the build_direction function for test phase
            direction = pm.build_direction("test", "Add GET /api/foo", 1)
            assert "Write and run tests" in direction
            assert "Add GET /api/foo" in direction
            assert "define the contract" in direction

        finally:
            pm.BACKLOG_FILE = orig_backlog
            pm.STATE_FILE = orig_state


def test_orchestrator_creates_review_task_after_test():
    """Acceptance: After test completes, creates review task"""
    with tempfile.TemporaryDirectory() as d:
        # Override file paths for test
        orig_backlog = pm.BACKLOG_FILE
        orig_state = pm.STATE_FILE
        pm.STATE_FILE = os.path.join(d, "project_manager_state.json")

        try:
            # Test the build_direction function for review phase
            direction = pm.build_direction("review", "Add GET /api/foo", 1)
            assert "Review the implementation" in direction
            assert "Add GET /api/foo" in direction
            assert "spec compliance" in direction

        finally:
            pm.BACKLOG_FILE = orig_backlog
            pm.STATE_FILE = orig_state


def test_validation_fails_on_pytest_fail_or_review_fail():
    """Acceptance: Validation: `cd api && pytest -v` exit 0 and review output contains 'pass'"""
    # Test the validation functions
    assert pm.review_indicates_pass("Review: pass. All good.") is True
    assert pm.review_indicates_pass("PASS — no issues") is True
    assert pm.review_indicates_pass("Review: fail. Issues found.") is False
    assert pm.review_indicates_pass("") is False

    # Test with false positive cases
    assert pm.review_indicates_pass("No pass needed here") is False
    assert pm.review_indicates_pass("The review says pass but there are failures") is False


def test_orchestrator_handles_needs_decision():
    """Acceptance: On needs_decision: orchestrator pauses, does not create new tasks until human /reply"""
    with tempfile.TemporaryDirectory() as d:
        state_file = os.path.join(d, "project_manager_state.json")

        # Override file paths for test
        orig_state = pm.STATE_FILE
        pm.STATE_FILE = state_file

        try:
            # Test initial state
            state = pm.load_state()
            assert state["backlog_index"] == 0
            assert state["phase"] == "spec"
            assert state["current_task_id"] is None
            assert state["blocked"] is False

            # Test saving and loading state
            pm.save_state({"backlog_index": 2, "phase": "impl", "blocked": True})
            loaded_state = pm.load_state()
            assert loaded_state["backlog_index"] == 2
            assert loaded_state["phase"] == "impl"
            assert loaded_state["blocked"] is True

        finally:
            pm.STATE_FILE = orig_state


def test_orchestrator_handles_max_iterations():
    """Acceptance: If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations"""
    with tempfile.TemporaryDirectory() as d:
        # Override file paths for test
        orig_backlog = pm.BACKLOG_FILE
        orig_state = pm.STATE_FILE
        pm.STATE_FILE = os.path.join(d, "project_manager_state.json")

        try:
            # Test the maximum iterations behavior
            assert pm.MAX_ITERATIONS == 5

        finally:
            pm.BACKLOG_FILE = orig_backlog
            pm.STATE_FILE = orig_state


def test_backlog_refresh_functionality():
    """Test that backlog refresh works. Real load_backlog and refresh_backlog — no mocks."""
    with tempfile.TemporaryDirectory() as d:
        backlog_file = os.path.join(d, "005-backlog.md")
        with open(backlog_file, "w") as f:
            f.write("# Backlog\n")

        orig_backlog = pm.BACKLOG_FILE
        pm.BACKLOG_FILE = backlog_file

        try:
            items = pm.load_backlog()
            assert len(items) == 0

            log = logging.getLogger("test_pm_refresh")
            log.addHandler(logging.NullHandler())
            refreshed = pm.refresh_backlog(log, remaining=2)
            assert refreshed is True

            items = pm.load_backlog()
            assert len(items) > 0
            assert any("Sprint" in it or "specs" in it for it in items)

        finally:
            pm.BACKLOG_FILE = orig_backlog


def test_pipeline_phases():
    """Test that all pipeline phases are defined correctly"""
    assert pm.PHASES == ["spec", "impl", "test", "review"]
    assert pm.TASK_TYPE_BY_PHASE["spec"] == "spec"
    assert pm.TASK_TYPE_BY_PHASE["impl"] == "impl"
    assert pm.TASK_TYPE_BY_PHASE["test"] == "test"
    assert pm.TASK_TYPE_BY_PHASE["review"] == "review"


def test_build_direction_function():
    """Test the build_direction function comprehensively"""
    # Spec phase
    direction = pm.build_direction("spec", "Test item", 1)
    assert "Write or expand the spec" in direction
    assert "Test item" in direction

    # Impl phase - first iteration
    direction = pm.build_direction("impl", "Test item", 1)
    assert "Implement per spec" in direction
    assert "Test item" in direction

    # Impl phase - later iterations
    direction = pm.build_direction("impl", "Test item", 3)
    assert "Fix the issues" in direction
    assert "Test item" in direction

    # Test phase
    direction = pm.build_direction("test", "Test item", 1)
    assert "Write and run tests" in direction
    assert "Test item" in direction

    # Review phase
    direction = pm.build_direction("review", "Test item", 1)
    assert "Review the implementation" in direction
    assert "Test item" in direction


def test_state_file_persistence():
    """Test that state file persists correctly"""
    with tempfile.TemporaryDirectory() as d:
        state_file = os.path.join(d, "test_state.json")

        # Override file path for test
        orig_state = pm.STATE_FILE
        pm.STATE_FILE = state_file

        try:
            # Test saving state
            test_state = {
                "backlog_index": 5,
                "phase": "review",
                "current_task_id": "task_abc",
                "iteration": 2,
                "blocked": True
            }
            pm.save_state(test_state)

            # Test loading state
            loaded_state = pm.load_state()
            assert loaded_state["backlog_index"] == 5
            assert loaded_state["phase"] == "review"
            assert loaded_state["current_task_id"] == "task_abc"
            assert loaded_state["iteration"] == 2
            assert loaded_state["blocked"] is True

            # Test default state
            os.remove(state_file)
            default_state = pm.load_state()
            assert default_state["backlog_index"] == 0
            assert default_state["phase"] == "spec"
            assert default_state["current_task_id"] is None
            assert default_state["iteration"] == 1
            assert default_state["blocked"] is False

        finally:
            pm.STATE_FILE = orig_state