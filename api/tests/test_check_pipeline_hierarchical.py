"""Tests for check_pipeline.py hierarchical view (spec 036).

Validates that pipeline status displays hierarchical view:
Goal → PM/Orchestration → Tasks → Artifacts

Uses mocked HTTP responses so the tests run without a live API server.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import check_pipeline module directly so we can invoke main() in-process.
# ---------------------------------------------------------------------------
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import check_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Canned API responses
# ---------------------------------------------------------------------------

_PIPELINE_STATUS = {
    "running": [
        {
            "id": "task_1",
            "task_type": "impl",
            "model": "codex/gpt-5.1",
            "running_seconds": 120,
            "direction": "Build telemetry endpoint for spec 036",
        }
    ],
    "pending": [
        {
            "id": "task_2",
            "task_type": "test",
            "wait_seconds": 30,
            "direction": "Run tests",
        }
    ],
    "recent_completed": [
        {
            "id": "task_3",
            "task_type": "impl",
            "duration_seconds": 300,
            "output_len": 1500,
            "output_preview": "All tests passed",
        }
    ],
    "project_manager": {
        "backlog_index": 4,
        "phase": "implement",
        "current_task_id": "task_1",
    },
    "attention": {"flags": []},
}

_STATUS_REPORT = {
    "layer_0_goal": {
        "status": "ok",
        "goal_proximity": 0.7,
        "summary": "goal_proximity=0.7, 5 tasks (7d), 80% success",
    },
    "layer_1_orchestration": {
        "status": "ok",
        "summary": "PM item=4, phase=implement; runner_workers=5",
    },
    "layer_2_execution": {"status": "ok", "summary": "running=1, pending=1"},
    "layer_3_attention": {"status": "ok", "flags": [], "summary": "No issues"},
}

_EFFECTIVENESS = {
    "goal_proximity": 0.7,
    "throughput": {"completed_7d": 5},
    "success_rate": 0.8,
}


def _mock_httpx_get(url: str, **kwargs):
    """Return canned httpx-like responses for known endpoints."""
    resp = MagicMock()
    if "/api/agent/pipeline-status" in url:
        resp.status_code = 200
        resp.json.return_value = _PIPELINE_STATUS
    elif "/api/agent/status-report" in url:
        resp.status_code = 200
        resp.json.return_value = _STATUS_REPORT
    elif "/api/agent/effectiveness" in url:
        resp.status_code = 200
        resp.json.return_value = _EFFECTIVENESS
    else:
        resp.status_code = 404
        resp.text = "not found"
        resp.json.side_effect = ValueError("not json")
    return resp


def _run_main(*cli_args: str) -> str:
    """Invoke check_pipeline.main() with mocked HTTP and capture stdout."""
    with (
        patch.object(sys, "argv", ["check_pipeline.py", *cli_args]),
        patch("check_pipeline.httpx.get", side_effect=_mock_httpx_get),
        patch("check_pipeline._get_pipeline_process_args", return_value={"runner_workers": 5, "pm_parallel": True}),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    return mock_out.getvalue()


def test_hierarchical_view_default_output_order():
    """Hierarchical view should show sections in order: Goal -> PM -> Tasks -> Artifacts."""
    stdout = _run_main()
    output = stdout.lower()

    goal_pos = output.find("goal (layer 0)")
    pm_pos = output.find("pm / orchestration (layer 1)")
    tasks_pos = output.find("tasks (layer 2)")
    artifacts_pos = output.find("artifacts (layer 3)")

    assert goal_pos >= 0, "Goal section must appear"
    assert goal_pos < pm_pos, "Goal should appear before PM/Orchestration"
    assert pm_pos < tasks_pos, "PM should appear before Tasks"
    assert tasks_pos < artifacts_pos, "Tasks should appear before Artifacts"


def test_hierarchical_flag_explicit():
    """--hierarchical flag should explicitly enable hierarchical view."""
    stdout = _run_main("--hierarchical")
    assert "layer 0" in stdout.lower() or "goal" in stdout.lower()


def test_flat_flag_legacy_output():
    """--flat flag should provide legacy flat output format."""
    stdout = _run_main("--flat")
    assert "layer 0" not in stdout.lower()
    assert "layer 1" not in stdout.lower()
    assert "pipeline status" in stdout.lower()


def test_json_output_includes_hierarchical_data():
    """--json flag should include hierarchical structure in output."""
    stdout = _run_main("--json")
    data = json.loads(stdout)

    assert "hierarchical" in data, "JSON output should include 'hierarchical' key"
    hierarchical = data["hierarchical"]
    assert "layer_0_goal" in hierarchical
    assert "layer_1_orchestration" in hierarchical
    assert "layer_2_execution" in hierarchical
    assert "layer_3_attention" in hierarchical


def test_json_flat_output_no_hierarchical():
    """--json --flat should not include hierarchical structure."""
    stdout = _run_main("--json", "--flat")
    data = json.loads(stdout)
    assert "hierarchical" not in data


def test_goal_section_displays_status():
    """Goal section should show status and summary when available."""
    stdout = _run_main()
    output = stdout.lower()
    assert "goal (layer 0)" in output
    assert (
        "status:" in output
        or "report not yet generated" in output
        or "goal_proximity" in output
    ), "Goal section should show status or fallback"


def test_pm_orchestration_section_displays():
    """PM/Orchestration section should show project manager and process info."""
    stdout = _run_main()
    output = stdout.lower()
    assert "pm / orchestration (layer 1)" in output
    assert (
        "project manager" in output
        or "pm not seen" in output
        or "agent_runner" in output
    ), "PM section should show orchestration info"


def test_tasks_section_displays():
    """Tasks section should show running, pending, and recent completed."""
    stdout = _run_main()
    output = stdout.lower()
    assert "tasks (layer 2)" in output
    assert (
        "running:" in output or "pending:" in output or "recent completed:" in output
    ), "Tasks section should show task status"


def test_artifacts_section_displays():
    """Artifacts section should show recent completed tasks with output info."""
    stdout = _run_main()
    output = stdout.lower()
    assert "artifacts (layer 3)" in output
    assert (
        "output:" in output
        or "no recent completed" in output
        or "chars" in output
    ), "Artifacts section should show output info"


def test_script_handles_api_unreachable():
    """Script should handle API being unreachable gracefully."""
    import httpx

    def _raise_connect_error(url: str, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with (
        patch.object(sys, "argv", ["check_pipeline.py"]),
        patch("check_pipeline.httpx.get", side_effect=_raise_connect_error),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        with pytest.raises(SystemExit):
            check_pipeline.main()
    stdout = mock_out.getvalue()
    assert "API not reachable" in stdout, "Should show meaningful error when API unreachable"


def test_help_output():
    """Script should provide help output."""
    with (
        patch.object(sys, "argv", ["check_pipeline.py", "--help"]),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        with pytest.raises(SystemExit) as exc_info:
            check_pipeline.main()
    assert exc_info.value.code == 0
    stdout = mock_out.getvalue()
    assert "--hierarchical" in stdout
    assert "--flat" in stdout
    assert "--json" in stdout
    assert "Goal" in stdout or "hierarchical" in stdout.lower()


def test_attention_flag_compatibility():
    """--attention flag should work with hierarchical view."""
    stdout = _run_main("--attention")
    assert "attention:" in stdout.lower() or "attention" in stdout.lower()


def test_layer0_goal_usable_from_report_helper():
    """Placeholder layer_0_goal summaries must not be treated as authoritative."""
    assert not check_pipeline._layer0_goal_usable_from_report(None)
    assert not check_pipeline._layer0_goal_usable_from_report({})
    assert not check_pipeline._layer0_goal_usable_from_report({"summary": "Report not yet generated"})
    assert not check_pipeline._layer0_goal_usable_from_report({"summary": "  "})
    assert check_pipeline._layer0_goal_usable_from_report(
        {"summary": "goal_proximity=0.7, 5 tasks (7d), 80% success"}
    )
