"""Spec 036 acceptance: status-report missing path with API up (goal fallback + tasks/artifacts).

Does not modify `test_check_pipeline_hierarchical.py`; supplements coverage for
'When status-report file is missing and API is up: Goal section shows fallback
from effectiveness or report not yet generated; Tasks and Artifacts still
from pipeline-status.'
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import check_pipeline  # noqa: E402

_PIPELINE_STATUS = {
    "running": [
        {
            "id": "task_run",
            "task_type": "impl",
            "model": "codex/x",
            "running_seconds": 10,
            "direction": "Do work",
        }
    ],
    "pending": [{"id": "task_pend", "task_type": "test", "wait_seconds": 5, "direction": "Wait"}],
    "recent_completed": [
        {
            "id": "task_done",
            "task_type": "impl",
            "duration_seconds": 60,
            "output_len": 999,
            "output_preview": "done output",
        }
    ],
    "project_manager": {"backlog_index": 1, "phase": "test", "current_task_id": "task_run"},
    "attention": {"flags": []},
}

_EFFECTIVENESS = {
    "goal_proximity": 0.62,
    "throughput": {"completed_7d": 3},
    "success_rate": 0.75,
}


def _mock_status_report_unavailable_effectiveness_ok(url: str, **kwargs):
    """pipeline-status + effectiveness OK; status-report missing (404)."""
    resp = MagicMock()
    if "/api/agent/pipeline-status" in url:
        resp.status_code = 200
        resp.json.return_value = _PIPELINE_STATUS
    elif "/api/agent/status-report" in url:
        resp.status_code = 404
        resp.text = "not found"
    elif "/api/agent/effectiveness" in url:
        resp.status_code = 200
        resp.json.return_value = _EFFECTIVENESS
    else:
        resp.status_code = 404
        resp.text = "not found"
        resp.json.side_effect = ValueError("not json")
    return resp


def _mock_no_status_report_no_effectiveness(url: str, **kwargs):
    """pipeline-status OK; status-report and effectiveness unavailable."""
    resp = MagicMock()
    if "/api/agent/pipeline-status" in url:
        resp.status_code = 200
        resp.json.return_value = _PIPELINE_STATUS
    elif "/api/agent/status-report" in url:
        resp.status_code = 404
    elif "/api/agent/effectiveness" in url:
        resp.status_code = 404
    else:
        resp.status_code = 404
        resp.json.side_effect = ValueError("not json")
    return resp


def _run_with_mock(mock_fn, *cli_args: str) -> str:
    with (
        patch.object(sys, "argv", ["check_pipeline.py", *cli_args]),
        patch("check_pipeline.httpx.get", side_effect=mock_fn),
        patch("check_pipeline._get_pipeline_process_args", return_value={"runner_workers": 5, "pm_parallel": True}),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    return mock_out.getvalue()


def test_acceptance_goal_uses_effectiveness_when_status_report_missing():
    """Goal shows effectiveness summary; Tasks/Artifacts still list pipeline data."""
    stdout = _run_with_mock(_mock_status_report_unavailable_effectiveness_ok)
    assert "goal (layer 0)" in stdout.lower()
    assert "0.62" in stdout or "goal_proximity" in stdout.lower()
    assert "task_run" in stdout.lower()
    assert "task_pend" in stdout.lower()
    assert "artifacts (layer 3)" in stdout.lower()
    assert "999" in stdout or "chars" in stdout.lower()


def test_acceptance_goal_report_not_yet_generated_without_effectiveness():
    """No status-report and no effectiveness → placeholder; pipeline tasks still shown."""
    stdout = _run_with_mock(_mock_no_status_report_no_effectiveness)
    low = stdout.lower()
    assert "report not yet generated" in low
    assert "tasks (layer 2)" in low
    assert "task_run" in low
    assert "artifacts (layer 3)" in low
    assert "task_done" in low.lower()


def test_acceptance_json_includes_hierarchical_when_status_report_missing():
    """--json builds hierarchical from pipeline + effectiveness when monitor report absent."""
    stdout = _run_with_mock(_mock_status_report_unavailable_effectiveness_ok, "--json")
    data = json.loads(stdout)
    assert "hierarchical" in data
    h = data["hierarchical"]
    assert h["layer_0_goal"].get("goal_proximity") == pytest.approx(0.62)
    assert "task_run" in str(h["layer_2_execution"].get("running", []))
    assert "task_done" in str(h["layer_2_execution"].get("recent_completed", []))


def test_acceptance_flat_still_has_pipeline_sections_not_layer_labels():
    """--flat preserves legacy flat layout (no Layer 0/Layer 1 headings)."""
    stdout = _run_with_mock(_mock_status_report_unavailable_effectiveness_ok, "--flat")
    low = stdout.lower()
    assert "layer 0" not in low
    assert "pipeline status" in low
    assert "tasks (layer 2)" not in low
