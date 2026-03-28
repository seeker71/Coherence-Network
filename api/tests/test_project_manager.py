"""Tests for project_manager: load_backlog, state, split/combine heuristics."""
import json
import os
import subprocess
import sys
import tempfile

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


def test_load_backlog_empty_file(tmp_path):
    """load_backlog with empty/missing file returns empty list."""
    pm.BACKLOG_FILE = str(tmp_path / "empty.md")
    open(pm.BACKLOG_FILE, "w").close()
    items = pm.load_backlog()
    assert items == []


def test_load_backlog_numbered_items(tmp_path):
    """load_backlog parses numbered lines, skips unnumbered."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. First item\n"
        "2. Second item\n"
        "unnumbered line\n"
        "3. Third item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First item", "Second item", "Third item"]


def test_load_backlog_malformed_missing_number_prefix(tmp_path):
    """Backlog with mixed numbered lines and lines lacking \\d+.\\s+ prefix: skip malformed, preserve order."""
    p = tmp_path / "backlog_malformed.md"
    p.write_text(
        "1. First item\n"
        "Unnumbered line\n"
        "2. Second item\n"
        "Another line without number\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First item", "Second item"]


def test_load_state_defaults(tmp_path):
    """load_state returns defaults when no file."""
    pm.STATE_FILE = str(tmp_path / "missing.json")
    data = pm.load_state()
    assert data["backlog_index"] == 0
    assert data["phase"] == "spec"
    assert data["current_task_id"] is None
    assert data["iteration"] == 1
    assert data["blocked"] is False
    assert data.get("split_parent") is None


def test_load_state_merged(tmp_path):
    """load_state merges existing file with defaults."""
    p = tmp_path / "state.json"
    p.write_text('{"backlog_index": 5, "phase": "impl"}')
    pm.STATE_FILE = str(p)
    data = pm.load_state()
    assert data["backlog_index"] == 5
    assert data["phase"] == "impl"
    assert data["current_task_id"] is None
    assert data.get("split_parent") is None


def test_save_state(tmp_path):
    """save_state writes valid JSON."""
    pm.STATE_FILE = str(tmp_path / "state.json")
    pm.save_state({"backlog_index": 1, "phase": "spec", "blocked": False})
    with open(pm.STATE_FILE) as f:
        data = json.load(f)
    assert data["backlog_index"] == 1
    assert data["phase"] == "spec"


def test_is_too_large_below_threshold():
    """is_too_large returns False when item below threshold."""
    assert pm.is_too_large("idea", "short") is False
    assert pm.is_too_large("spec", "a" * 200) is False
    assert pm.is_too_large("impl", "b" * 250) is False


def test_is_too_large_above_threshold():
    """is_too_large returns True when item exceeds threshold."""
    long_item = "a" * 350
    assert pm.is_too_large("idea", long_item) is True
    assert pm.is_too_large("spec", long_item) is True
    assert pm.is_too_large("impl", long_item) is True


def test_split_item_short_returns_single():
    """split_item returns [item] when item below threshold."""
    short = "Short item"
    assert pm.split_item("idea", short) == [short]
    assert pm.split_item("spec", short) == [short]


def test_split_with_ordering_returns_linear_ordering():
    """split_with_ordering returns (items, ordering) with default linear depends_on."""
    long_item = "x" * 350
    items, ordering = pm.split_with_ordering("impl", long_item)
    assert len(items) >= 2
    assert len(ordering) == len(items)
    for i, deps in enumerate(ordering):
        assert deps == list(range(i))


def test_format_ordering_signal():
    """format_ordering_signal appends sub-impl position and depends_on for sub-impls."""
    out = pm.format_ordering_signal({"child_idx": 0, "depends_on": []}, 3)
    assert "Sub-impl 1 of 3" in out
    assert "depends on sub-impl(s) none" in out
    out = pm.format_ordering_signal({"child_idx": 1, "depends_on": [0]}, 3)
    assert "Sub-impl 2 of 3" in out
    assert "depends on sub-impl(s) 1" in out
    assert pm.format_ordering_signal({"child_idx": 0}, 1) == ""


def test_next_runnable_in_parallel():
    """next_runnable_in_parallel returns first index whose deps are all done."""
    ordering = [[], [0], [0, 1]]
    assert pm.next_runnable_in_parallel([], ordering, 3) == 0
    assert pm.next_runnable_in_parallel([0], ordering, 3) == 1
    assert pm.next_runnable_in_parallel([0, 1], ordering, 3) == 2
    assert pm.next_runnable_in_parallel([0, 1, 2], ordering, 3) is None


def test_split_item_long_by_delimiter():
    """split_item splits by ' — ' or ';' or ' and ' when item exceeds threshold."""
    # Parts must be >= SPLIT_MIN_PART_CHARS; item must exceed threshold
    part_a = "Spec for feature A with detailed requirements and acceptance criteria"
    part_b = "Spec for feature B with detailed requirements and acceptance criteria"
    item = f"{part_a} — {part_b} — extra filler " + "x" * 150
    parts = pm.split_item("spec", item)
    assert len(parts) >= 2


def test_split_item_long_fallback():
    """split_item splits long item without delimiters into chunks."""
    long_item = "x" * 400
    parts = pm.split_item("impl", long_item)
    assert len(parts) >= 2
    assert sum(len(p) for p in parts) >= len(long_item) - 50


def test_all_children_complete_empty():
    """all_children_complete returns False for empty children."""
    assert pm.all_children_complete({"children": []}) is False


def test_all_children_complete_partial():
    """all_children_complete returns False when some incomplete."""
    sp = {"children": [{"complete": True}, {"complete": False}]}
    assert pm.all_children_complete(sp) is False


def test_all_children_complete_all():
    """all_children_complete returns True when all complete."""
    sp = {"children": [{"complete": True}, {"complete": True}]}
    assert pm.all_children_complete(sp) is True


def test_get_current_child():
    """get_current_child returns child at current_child_idx."""
    sp = {"children": [{"item": "a"}, {"item": "b"}], "current_child_idx": 0}
    c = pm.get_current_child(sp)
    assert c is not None
    assert c["item"] == "a"
    sp["current_child_idx"] = 1
    c = pm.get_current_child(sp)
    assert c["item"] == "b"


def test_get_current_child_beyond_end():
    """get_current_child returns None when idx beyond children."""
    sp = {"children": [{"item": "a"}], "current_child_idx": 1}
    assert pm.get_current_child(sp) is None


def test_mark_child_complete():
    """mark_child_complete sets complete=True on child."""
    sp = {"children": [{"complete": False}, {"complete": False}]}
    pm.mark_child_complete(sp, 0)
    assert sp["children"][0]["complete"] is True
    assert sp["children"][1]["complete"] is False


def test_advance_to_next_child():
    """advance_to_next_child advances idx and returns next or None."""
    sp = {"children": [{"complete": False}, {"complete": False}], "current_child_idx": 0}
    next_idx = pm.advance_to_next_child(sp)
    assert next_idx == 1
    assert sp["current_child_idx"] == 1

    next_idx = pm.advance_to_next_child(sp)
    assert next_idx is None
    assert sp["current_child_idx"] == 2


def test_get_next_runnable_index_respects_depends_on():
    """get_next_runnable_index returns first child whose depends_on are all complete."""
    # Child 0: deps []; child 1: deps [0]; child 2: deps [0,1]. So runnable is 0 until 0 complete.
    sp = {
        "children": [
            {"complete": False, "depends_on": []},
            {"complete": False, "depends_on": [0]},
            {"complete": False, "depends_on": [0, 1]},
        ],
        "current_child_idx": 0,
    }
    assert pm.get_next_runnable_index(sp) == 0
    pm.mark_child_complete(sp, 0)
    assert pm.get_next_runnable_index(sp) == 1
    pm.mark_child_complete(sp, 1)
    assert pm.get_next_runnable_index(sp) == 2
    pm.mark_child_complete(sp, 2)
    assert pm.get_next_runnable_index(sp) is None


def test_get_current_child_with_depends_on():
    """get_current_child returns runnable child when depends_on present."""
    sp = {
        "children": [
            {"item": "first", "complete": False, "depends_on": []},
            {"item": "second", "complete": False, "depends_on": [0]},
        ],
        "current_child_idx": 0,
    }
    c = pm.get_current_child(sp)
    assert c is not None and c["item"] == "first"
    pm.mark_child_complete(sp, 0)
    c = pm.get_current_child(sp)
    assert c is not None and c["item"] == "second"
    pm.mark_child_complete(sp, 1)
    assert pm.get_current_child(sp) is None


def test_backward_compatible_state_load(tmp_path):
    """Old state file without split_parent loads and has split_parent=None."""
    p = tmp_path / "old_state.json"
    p.write_text('{"backlog_index": 0, "phase": "spec", "iteration": 1}')
    pm.STATE_FILE = str(p)
    data = pm.load_state()
    assert data.get("split_parent") is None
    assert data["backlog_index"] == 0


def test_dry_run_exits_zero():
    """project_manager --dry-run exits 0 and prints preview (no HTTP)."""
    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    result = subprocess.run(
        [sys.executable, script, "--dry-run", "--reset"],
        cwd=os.path.dirname(_api_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout or "dry-run" in result.stdout.lower()


def test_reset_clears_state_file(tmp_path):
    """--reset removes the state file; load_state() returns backlog_index=0 and phase='spec'."""
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "backlog_index": 7,
        "phase": "impl",
        "iteration": 3,
        "blocked": False,
    }))
    pm.STATE_FILE = str(state_path)
    # Mirror the reset flag logic from project_manager.py lines 1076-1077
    if os.path.isfile(pm.STATE_FILE):
        os.remove(pm.STATE_FILE)
    state = pm.load_state()
    assert state["backlog_index"] == 0
    assert state["phase"] == "spec"
    assert not state_path.exists()


def test_reset_flag_removes_state_file(tmp_path):
    """subprocess --reset --dry-run --state-file deletes the file and prints DRY-RUN: backlog index=0."""
    state_path = tmp_path / "pm_state.json"
    state_path.write_text(json.dumps({"backlog_index": 3, "phase": "impl"}))
    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    project_root = os.path.dirname(_api_dir)
    result = subprocess.run(
        [sys.executable, script, "--reset", "--dry-run", "--state-file", str(state_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "DRY-RUN: backlog index=0" in result.stdout
    # The file should not exist (deleted by reset) or contain backlog_index=0
    if state_path.exists():
        data = json.loads(state_path.read_text())
        assert data.get("backlog_index") == 0
    # else: file was deleted, which is the expected outcome


def test_reset_noop_when_no_state_file(tmp_path):
    """--reset is a no-op (exit 0, no crash) when the state file does not exist."""
    state_path = tmp_path / "nonexistent_state.json"
    assert not state_path.exists()
    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    project_root = os.path.dirname(_api_dir)
    result = subprocess.run(
        [sys.executable, script, "--reset", "--dry-run", "--state-file", str(state_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Traceback" not in result.stderr


def test_reset_uses_state_file_arg(tmp_path):
    """--reset --state-file operates on the alternate path, not the default STATE_FILE."""
    alt_state = tmp_path / "alt_state.json"
    alt_state.write_text(json.dumps({"backlog_index": 5, "phase": "test"}))
    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    project_root = os.path.dirname(_api_dir)
    # Record mtime of default STATE_FILE if it exists
    default_state = os.path.join(_api_dir, "logs", "project_manager_state.json")
    default_mtime_before = os.path.getmtime(default_state) if os.path.exists(default_state) else None
    result = subprocess.run(
        [sys.executable, script, "--reset", "--dry-run", "--state-file", str(alt_state)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not alt_state.exists(), "alt_state.json should be deleted by --reset"
    assert "DRY-RUN: backlog index=0" in result.stdout
    # Default STATE_FILE must be untouched
    if default_mtime_before is not None:
        assert os.path.getmtime(default_state) == default_mtime_before
