"""Tests for project manager orchestrator — spec 005."""

import json
import os
import subprocess
import sys
import tempfile

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
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
    """When BACKLOG_FILE is set to alternate path, load_backlog reads from it."""
    alt_backlog = tmp_path / "custom-backlog.md"
    alt_backlog.write_text("# Custom\n1. Item A\n2. Item B\n")
    orig = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = str(alt_backlog)
    try:
        items = pm.load_backlog()
        assert items == ["Item A", "Item B"]
    finally:
        pm.BACKLOG_FILE = orig


def test_backlog_flag_uses_alternate_file(tmp_path):
    """Contract: project_manager --backlog <path> uses that file as the backlog source.

    When invoked with --backlog <path>, the CLI must load items from the given path
    (not the default specs/005-backlog.md). Dry-run output must reflect the alternate
    file's content (e.g. next item text from that file). Exit code must be 0.
    """
    alt_backlog = tmp_path / "alternate-backlog.md"
    distinctive_item = "Alternate backlog item for --backlog flag test"
    alt_backlog.write_text("# Alternate\n1. " + distinctive_item + "\n")
    state_path = tmp_path / "project_manager_state.json"
    script_path = os.path.join(_api_dir, "scripts", "project_manager.py")
    result = subprocess.run(
        [sys.executable, script_path, "--dry-run", "--backlog", str(alt_backlog), "--state-file", str(state_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--backlog dry-run failed. stderr: {result.stderr!r} stdout: {result.stdout!r}"
    out = (result.stdout or "") + (result.stderr or "")
    assert distinctive_item in out, f"Output must show item from alternate backlog. Got: {out!r}"


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


def test_load_backlog_malformed_missing_numbers(tmp_path):
    """Contract: only lines matching ^\\d+\\.\\s+(.+)$ are included; others are skipped; order preserved.
    Backlog with mixed numbered and unnumbered lines: load_backlog returns only numbered items, no crash."""
    backlog_file = tmp_path / "mixed.md"
    backlog_file.write_text(
        "1. First item\n"
        "Unnumbered line\n"
        "2. Second item\n"
        "Another line without number\n"
    )
    orig = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = str(backlog_file)
    try:
        items = pm.load_backlog()
        # Contract: only parsed text from numbered lines; unnumbered lines never appear
        assert "Unnumbered line" not in items
        assert "Another line without number" not in items
        assert items == ["First item", "Second item"]
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


def test_state_file_flag_uses_alternate_path(tmp_path):
    """When --state-file is used (or STATE_FILE set to alternate path), load_state/save_state use that path."""
    alt_state = tmp_path / "alt_state.json"
    alt_state.write_text(
        '{"backlog_index": 4, "phase": "impl", "current_task_id": null, "iteration": 2, "blocked": true}'
    )
    orig = pm.STATE_FILE
    pm.STATE_FILE = str(alt_state)
    try:
        s = pm.load_state()
        assert s["backlog_index"] == 4
        assert s["phase"] == "impl"
        assert s["blocked"] is True
        pm.save_state(
            {"backlog_index": 10, "phase": "review", "current_task_id": None, "iteration": 1, "blocked": False}
        )
        assert alt_state.exists()
        data = json.loads(alt_state.read_text())
        assert data["backlog_index"] == 10
        assert data["phase"] == "review"
    finally:
        pm.STATE_FILE = orig


def test_project_manager_state_file_flag_uses_alternate_state_path(tmp_path):
    """Contract: project_manager --state-file <path> uses that path for state (read and write).

    When invoked with --state-file <path>, the script must read state from the given path
    (not the default api/logs/project_manager_state.json). Pre-populate the alternate file
    with backlog_index=1, phase=impl; run --dry-run; assert stdout reflects that state
    (backlog index 1, phase impl, and the second backlog item as next task).
    """
    state_path = tmp_path / "alt_state.json"
    state_path.write_text(
        '{"backlog_index": 1, "phase": "impl", "current_task_id": null, "iteration": 1, "blocked": false}'
    )
    backlog_path = tmp_path / "backlog.md"
    second_item = "Second backlog item for --state-file flag contract test"
    backlog_path.write_text(
        "# Backlog\n1. First item\n2. " + second_item + "\n3. Third item\n"
    )
    script_path = os.path.join(_api_dir, "scripts", "project_manager.py")
    result = subprocess.run(
        [
            sys.executable,
            script_path,
            "--dry-run",
            "--state-file",
            str(state_path),
            "--backlog",
            str(backlog_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"--state-file dry-run failed. stderr: {result.stderr!r} stdout: {result.stdout!r}"
    )
    out = (result.stdout or "") + (result.stderr or "")
    assert "backlog index=1" in out, f"Output must show state was read from alternate path (index=1). Got: {out!r}"
    assert "phase=impl" in out, f"Output must show phase from alternate state. Got: {out!r}"
    assert second_item[:40] in out or second_item in out, (
        f"Output must show next item (index 1) from backlog. Got: {out!r}"
    )


def test_reset_clears_state_and_starts_from_index_zero(tmp_path):
    """Contract: project_manager --reset clears state and starts from index 0.

    When invoked with --reset (and --state-file <path> so the default state file is not used),
    any existing state at that path is cleared and the run proceeds from the beginning:
    backlog_index is 0 and phase is the default "spec". Either the state file is removed and
    a subsequent load_state() from that path yields defaults, or the file exists with
    backlog_index 0 and phase "spec". This test pre-populates state with backlog_index > 0,
    runs --reset --dry-run --state-file <tmp_path>, then asserts post-run state is cleared
    to index 0 and default phase.
    """
    state_path = tmp_path / "project_manager_state.json"
    state_path.write_text(
        '{"backlog_index": 5, "phase": "impl", "current_task_id": null, "iteration": 1, "blocked": false}'
    )
    backlog_path = tmp_path / "backlog.md"
    backlog_path.write_text("# Backlog\n1. First item\n")
    script_path = os.path.join(_api_dir, "scripts", "project_manager.py")
    result = subprocess.run(
        [
            sys.executable,
            script_path,
            "--reset",
            "--dry-run",
            "--state-file",
            str(state_path),
            "--backlog",
            str(backlog_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"reset dry-run failed. stderr: {result.stderr!r} stdout: {result.stdout!r}"
    )
    if state_path.exists():
        data = json.loads(state_path.read_text())
        assert data["backlog_index"] == 0
        assert data["phase"] == "spec"
    else:
        orig = pm.STATE_FILE
        pm.STATE_FILE = str(state_path)
        try:
            s = pm.load_state()
            assert s["backlog_index"] == 0
            assert s["phase"] == "spec"
        finally:
            pm.STATE_FILE = orig
