"""Tests for project_manager --reset flag: clears persisted state and starts from index 0."""
import json
import os
import subprocess
import sys
import tempfile

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_script = os.path.join(_api_dir, "scripts", "project_manager.py")
_repo_root = os.path.dirname(_api_dir)

sys.path.insert(0, _api_dir)
from scripts import project_manager as pm


def _write_state(path: str, backlog_index: int, phase: str = "impl") -> None:
    with open(path, "w") as f:
        json.dump({"backlog_index": backlog_index, "phase": phase, "iteration": 2, "blocked": False}, f)


def _load_state_from(path: str) -> dict:
    """Load state defaults merged with file contents (mirrors pm.load_state logic)."""
    defaults = {"backlog_index": 0, "phase": "spec", "current_task_id": None, "iteration": 1, "blocked": False, "split_parent": None}
    if not os.path.isfile(path):
        return defaults
    with open(path) as f:
        data = json.load(f)
    defaults.update(data)
    return defaults


class TestResetClearsStateFileRemoved:
    """--reset removes a pre-existing state file so load_state returns index 0."""

    def test_reset_removes_state_file(self, tmp_path):
        """After --reset with pre-populated state file, the file is removed."""
        state_file = str(tmp_path / "pm_state.json")
        _write_state(state_file, backlog_index=5, phase="impl")
        assert os.path.isfile(state_file), "Pre-condition: state file should exist"

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"Script exited non-zero: {result.stderr}"
        # After reset, file should be gone (reset removes it before dry-run re-loads state)
        assert not os.path.isfile(state_file), (
            "Expected state file to be removed after --reset, but it still exists"
        )

    def test_reset_load_state_yields_index_zero(self, tmp_path):
        """After --reset run, load_state from that path yields backlog_index=0."""
        state_file = str(tmp_path / "pm_state.json")
        _write_state(state_file, backlog_index=7, phase="review")

        subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )

        # Whether file was removed or reset to defaults, load gives index 0
        state = _load_state_from(state_file)
        assert state["backlog_index"] == 0, (
            f"Expected backlog_index=0 after reset, got {state['backlog_index']}"
        )

    def test_reset_load_state_yields_default_phase(self, tmp_path):
        """After --reset run, load_state from that path yields phase='spec'."""
        state_file = str(tmp_path / "pm_state.json")
        _write_state(state_file, backlog_index=3, phase="test")

        subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )

        state = _load_state_from(state_file)
        assert state["phase"] == "spec", (
            f"Expected phase='spec' after reset, got '{state['phase']}'"
        )


class TestResetNoPreexistingState:
    """--reset with no pre-existing state file works without error."""

    def test_reset_no_state_file_exits_zero(self, tmp_path):
        """--reset with nonexistent state file exits 0 (nothing to remove)."""
        state_file = str(tmp_path / "nonexistent_state.json")
        assert not os.path.isfile(state_file), "Pre-condition: file must not exist"

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"Script exited non-zero: {result.stderr}"

    def test_reset_no_state_file_starts_at_index_zero(self, tmp_path):
        """With no prior state and --reset, dry-run output reflects index 0."""
        state_file = str(tmp_path / "nonexistent_state.json")

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        # dry-run prints "DRY-RUN: backlog index=0"
        assert "index=0" in result.stdout, (
            f"Expected 'index=0' in dry-run output, got: {result.stdout!r}"
        )


class TestResetDryRunOutput:
    """--reset + --dry-run outputs confirm state was reset to index 0."""

    def test_reset_dry_run_prints_index_zero(self, tmp_path):
        """dry-run output says backlog index=0 after reset."""
        state_file = str(tmp_path / "pm_state.json")
        _write_state(state_file, backlog_index=4, phase="impl")

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"Exit {result.returncode}: {result.stderr}"
        assert "index=0" in result.stdout, (
            f"Expected 'index=0' in stdout after reset, got: {result.stdout!r}"
        )

    def test_reset_dry_run_does_not_print_old_index(self, tmp_path):
        """dry-run output must not show the old backlog_index after reset."""
        state_file = str(tmp_path / "pm_state.json")
        _write_state(state_file, backlog_index=9, phase="review")

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        # The old index (9) must not appear; instead we expect 0
        assert "index=9" not in result.stdout, (
            f"Old index=9 should not appear in output after reset: {result.stdout!r}"
        )

    def test_reset_dry_run_contains_dry_run_marker(self, tmp_path):
        """Smoke test: --dry-run output always contains DRY-RUN marker."""
        state_file = str(tmp_path / "pm_state.json")

        result = subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "DRY-RUN" in result.stdout or "dry-run" in result.stdout.lower(), (
            f"Expected DRY-RUN marker in output: {result.stdout!r}"
        )


class TestResetIsolation:
    """--state-file ensures reset does not touch the default state file."""

    def test_reset_uses_dedicated_state_path(self, tmp_path):
        """Reset with --state-file only removes that file, not others."""
        state_file_a = str(tmp_path / "state_a.json")
        state_file_b = str(tmp_path / "state_b.json")
        _write_state(state_file_a, backlog_index=3)
        _write_state(state_file_b, backlog_index=5)

        # Reset only state_file_a
        subprocess.run(
            [sys.executable, _script, "--reset", "--dry-run", "--state-file", state_file_a],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )

        # state_file_b must be untouched
        assert os.path.isfile(state_file_b), "state_file_b should not be touched by reset targeting state_file_a"
        state_b = _load_state_from(state_file_b)
        assert state_b["backlog_index"] == 5, "state_file_b backlog_index must remain 5"
