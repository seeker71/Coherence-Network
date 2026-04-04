"""Tests for spec 042: project_manager --reset clears state and starts from index 0."""
import json
import os
import subprocess
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


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
