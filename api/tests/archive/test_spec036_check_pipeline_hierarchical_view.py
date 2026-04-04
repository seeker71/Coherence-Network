"""Spec 036 — Check Pipeline Hierarchical View: acceptance-oriented tests.

Covers monitor-written status-report path (Goal/PM from API) and JSON merge
behavior. Uses mocked HTTP; no live API required.

See specs/036-check-pipeline-hierarchical-view.md — Acceptance Tests.
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
            "direction": "Implement feature",
        }
    ],
    "pending": [{"id": "task_pend", "task_type": "test", "wait_seconds": 5, "direction": "Wait"}],
    "recent_completed": [
        {
            "id": "task_done",
            "task_type": "impl",
            "duration_seconds": 60,
            "output_len": 42,
            "output_preview": "artifact line",
        }
    ],
    "project_manager": {"backlog_index": 2, "phase": "implement", "current_task_id": "task_run"},
    "attention": {"flags": []},
}

# Distinct from effectiveness fallback so we can assert Goal uses status-report.
_STATUS_REPORT = {
    "layer_0_goal": {
        "status": "ok",
        "goal_proximity": 0.91,
        "summary": "goal_proximity=0.91, 9 tasks (7d), 91% success from monitor",
    },
    "layer_1_orchestration": {
        "status": "ok",
        "summary": "PM item=2, phase=implement; runner_workers=5",
    },
    "layer_2_execution": {"status": "ok", "summary": "running=1, pending=1"},
    "layer_3_attention": {"status": "ok", "flags": [], "summary": "No issues"},
}

_EFFECTIVENESS = {
    "goal_proximity": 0.11,
    "throughput": {"completed_7d": 1},
    "success_rate": 0.22,
}


def _mock_all_ok(url: str, **kwargs):
    """pipeline-status + status-report + effectiveness return 200."""
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


def _run(*cli_args: str) -> str:
    with (
        patch.object(sys, "argv", ["check_pipeline.py", *cli_args]),
        patch("check_pipeline.httpx.get", side_effect=_mock_all_ok),
        patch("check_pipeline._get_pipeline_process_args", return_value={"runner_workers": 5, "pm_parallel": True}),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    return mock_out.getvalue()


def test_acceptance_human_output_four_sections_in_order():
    """No --json: Goal, PM/Orchestration, Tasks, Artifacts in that order."""
    stdout = _run()
    low = stdout.lower()
    g = low.find("goal (layer 0)")
    pm = low.find("pm / orchestration (layer 1)")
    tasks = low.find("tasks (layer 2)")
    art = low.find("artifacts (layer 3)")
    assert g >= 0 and pm >= 0 and tasks >= 0 and art >= 0
    assert g < pm < tasks < art


def test_acceptance_goal_uses_status_report_not_effectiveness_when_present():
    """When status-report exists, Goal section shows monitor summary (not effectiveness fallback)."""
    stdout = _run()
    assert "from monitor" in stdout
    assert "0.91" in stdout
    # Effectiveness has 0.11 — should not drive the printed Goal line
    assert "0.11" not in stdout


def test_acceptance_json_includes_hierarchical_from_status_report():
    """--json includes hierarchical data; layers match status-report when monitor wrote file."""
    stdout = _run("--json")
    data = json.loads(stdout)
    assert "hierarchical" in data
    h = data["hierarchical"]
    assert h["layer_0_goal"].get("summary") == _STATUS_REPORT["layer_0_goal"]["summary"]
    assert h["layer_1_orchestration"].get("summary") == _STATUS_REPORT["layer_1_orchestration"]["summary"]
    assert "task_run" in str(h.get("layer_2_execution", {}))


def test_acceptance_flat_legacy_no_layer_labels():
    """--flat preserves legacy flat output (no Layer 0/Layer 1 headings)."""
    stdout = _run("--flat")
    low = stdout.lower()
    assert "layer 0" not in low
    assert "pipeline status" in low
    assert "tasks (layer 2)" not in low


def test_explicit_hierarchical_matches_default_sections():
    """--hierarchical prints same four section headers as default human run."""
    a = _run()
    b = _run("--hierarchical")
    for needle in ("Goal (Layer 0)", "PM / Orchestration (Layer 1)", "Tasks (Layer 2)", "Artifacts (Layer 3)"):
        assert needle in a
        assert needle in b


def test_json_flat_has_no_hierarchical_key():
    """--json --flat omits hierarchical payload (legacy flat JSON)."""
    stdout = _run("--json", "--flat")
    data = json.loads(stdout)
    assert "hierarchical" not in data
