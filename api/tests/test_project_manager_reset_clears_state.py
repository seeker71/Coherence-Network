"""Spec 042: --reset clears persisted state; run starts from backlog index 0."""

import json
import os
import subprocess
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


def test_reset_with_state_file_and_dry_run_clears_high_index_to_start(tmp_path):
    """Run project_manager with --reset --dry-run --state-file: state starts at index 0 / default phase."""
    state_path = tmp_path / "pm_reset_spec042.json"
    state_path.write_text(
        json.dumps(
            {
                "backlog_index": 17,
                "phase": "review",
                "current_task_id": "task-not-default",
                "iteration": 4,
                "blocked": True,
            }
        ),
        encoding="utf-8",
    )
    assert state_path.is_file()

    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    project_root = os.path.dirname(_api_dir)
    result = subprocess.run(
        [
            sys.executable,
            script,
            "--reset",
            "--dry-run",
            "--state-file",
            str(state_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)

    pm.STATE_FILE = str(state_path)
    data = pm.load_state()
    assert data["backlog_index"] == 0
    assert data["phase"] == "spec"
    assert data["current_task_id"] is None
    assert data["iteration"] == 1
    assert data["blocked"] is False

    out = (result.stdout or "") + (result.stderr or "")
    assert "index=0" in out
    assert "phase=spec" in out


def test_reset_removes_state_file_when_present_before_dry_run(tmp_path):
    """After --reset, dry-run does not repopulate stale index; missing file loads as defaults (spec branch 1)."""
    state_path = tmp_path / "pm_removed.json"
    state_path.write_text('{"backlog_index": 3, "phase": "test"}', encoding="utf-8")

    script = os.path.join(_api_dir, "scripts", "project_manager.py")
    project_root = os.path.dirname(_api_dir)
    subprocess.run(
        [
            sys.executable,
            script,
            "--reset",
            "--dry-run",
            "--state-file",
            str(state_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )

    assert not state_path.is_file()
    pm.STATE_FILE = str(state_path)
    assert pm.load_state()["backlog_index"] == 0
