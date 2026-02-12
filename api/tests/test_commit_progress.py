"""Tests for commit_progress.py — spec 030 pipeline full automation."""

import subprocess
import sys
from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_scripts_dir = _api_dir / "scripts"


def test_commit_progress_exits_0_when_no_changes():
    """commit_progress.py exits 0 when no changes (no-op). Spec 030."""
    result = subprocess.run(
        [sys.executable, str(_scripts_dir / "commit_progress.py"), "--task-id", "task_test", "--task-type", "impl"],
        cwd=str(_api_dir.parent),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
