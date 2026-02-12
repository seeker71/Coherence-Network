"""Tests for project manager orchestrator — spec 005."""

import os
import tempfile


# Import project_manager module logic (extract testable helpers)
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


def test_load_backlog_parses_numbered_lines(tmp_path):
    """Backlog file parses numbered items."""
    backlog_file = tmp_path / "005-backlog.md"
    backlog_file.write_text(
        "# Backlog\n"
        "1. First item\n"
        "2. Second item\n"
        "3. specs/foo.md — do thing\n"
    )
    # Override BACKLOG_FILE for test
    orig = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = str(backlog_file)
    try:
        items = pm.load_backlog()
        assert len(items) == 3
        assert items[0] == "First item"
        assert items[1] == "Second item"
        assert "specs/foo.md" in items[2]
    finally:
        pm.BACKLOG_FILE = orig


def test_load_backlog_alternate_file(tmp_path):
    """--backlog flag: load_backlog uses BACKLOG_FILE (alternate path)."""
    alt_backlog = tmp_path / "custom-backlog.md"
    alt_backlog.write_text("# Custom\n1. Item A\n2. Item B\n")
    orig = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = str(alt_backlog)
    try:
        items = pm.load_backlog()
        assert items == ["Item A", "Item B"]
    finally:
        pm.BACKLOG_FILE = orig


def test_load_backlog_empty_and_malformed(tmp_path):
    """Backlog with no numbered lines returns empty list."""
    backlog_file = tmp_path / "empty.md"
    backlog_file.write_text("# Backlog\n\nNo numbered lines here.\n")
    orig = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = str(backlog_file)
    try:
        items = pm.load_backlog()
        assert items == []
    finally:
        pm.BACKLOG_FILE = orig


def test_build_direction_spec():
    """Spec direction references backlog item."""
    d = pm.build_direction("spec", "Add GET /api/foo", 1)
    assert "Add GET /api/foo" in d
    assert "spec" in d.lower() or "template" in d.lower()


def test_build_direction_impl():
    """Impl direction references spec."""
    d = pm.build_direction("impl", "specs/005.md", 1)
    assert "Implement" in d or "impl" in d.lower()
    assert "specs/005" in d or "005" in d


def test_review_indicates_pass():
    """Review pass detection."""
    assert pm.review_indicates_pass("Review: pass. All good.") is True
    assert pm.review_indicates_pass("PASS — no issues") is True
    assert pm.review_indicates_pass("Review: fail. Issues found.") is False
    assert pm.review_indicates_pass("") is False


def test_load_state_default():
    """State defaults when file missing."""
    with tempfile.TemporaryDirectory() as d:
        orig = pm.STATE_FILE
        pm.STATE_FILE = os.path.join(d, "nonexistent.json")
        try:
            s = pm.load_state()
            assert s["backlog_index"] == 0
            assert s["phase"] == "spec"
            assert s["current_task_id"] is None
            assert s["blocked"] is False
        finally:
            pm.STATE_FILE = orig


def test_load_state_handles_corrupted_json(tmp_path):
    """load_state returns defaults when state file has invalid JSON."""
    state_file = tmp_path / "corrupt.json"
    state_file.write_text("{ invalid json }")
    orig = pm.STATE_FILE
    pm.STATE_FILE = str(state_file)
    try:
        s = pm.load_state()
        assert s["backlog_index"] == 0
        assert s["phase"] == "spec"
        assert s["current_task_id"] is None
    finally:
        pm.STATE_FILE = orig


def test_save_and_load_state(tmp_path):
    """State round-trips."""
    state_file = tmp_path / "state.json"
    orig = pm.STATE_FILE
    pm.STATE_FILE = str(state_file)
    try:
        pm.save_state({"backlog_index": 2, "phase": "impl", "blocked": True})
        s = pm.load_state()
        assert s["backlog_index"] == 2
        assert s["phase"] == "impl"
        assert s["blocked"] is True
    finally:
        pm.STATE_FILE = orig
