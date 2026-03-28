"""Node Task Visibility — acceptance tests for spec 036 (hierarchical check_pipeline).

Maps operator-facing "task visibility" to Goal → PM/Orchestration → Tasks → Artifacts.
Uses mocked HTTP so tests run without a live API.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import check_pipeline  # noqa: E402

_PIPELINE_BASE = {
    "running": [
        {
            "id": "vis_run_1",
            "task_type": "test",
            "model": "openrouter/test",
            "running_seconds": 10,
            "direction": "Visibility smoke",
        }
    ],
    "pending": [
        {
            "id": "vis_pend_1",
            "task_type": "review",
            "wait_seconds": 5,
            "direction": "Review queue",
        }
    ],
    "recent_completed": [
        {
            "id": "vis_done_1",
            "task_type": "impl",
            "duration_seconds": 60,
            "output_len": 900,
            "output_preview": "artifact line one",
        }
    ],
    "project_manager": {
        "backlog_index": 1,
        "phase": "test",
        "current_task_id": "vis_run_1",
    },
    "attention": {"flags": []},
}

_EFFECTIVENESS = {
    "goal_proximity": 0.55,
    "throughput": {"completed_7d": 3},
    "success_rate": 0.9,
}


def _mock_httpx_get_factory(
    *,
    status_report_response: dict | None,
    effectiveness_response: dict | None,
    status_report_status: int = 200,
    effectiveness_status: int = 200,
):
    """Build a side_effect for httpx.get that serves pipeline-status, optional status-report, effectiveness."""

    def _mock(url: str, **kwargs):
        resp = MagicMock()
        if "/api/agent/pipeline-status" in url:
            resp.status_code = 200
            resp.json.return_value = _PIPELINE_BASE
            return resp
        if "/api/agent/status-report" in url:
            if status_report_status == 200 and status_report_response is not None:
                resp.status_code = 200
                resp.json.return_value = status_report_response
            else:
                resp.status_code = status_report_status
            return resp
        if "/api/agent/effectiveness" in url:
            if effectiveness_status == 200 and effectiveness_response is not None:
                resp.status_code = 200
                resp.json.return_value = effectiveness_response
            else:
                resp.status_code = effectiveness_status
            return resp
        resp.status_code = 404
        resp.text = "not found"
        return resp

    return _mock


def _run_with_mock(mock_get):
    with (
        patch.object(sys, "argv", ["check_pipeline.py"]),
        patch("check_pipeline.httpx.get", side_effect=mock_get),
        patch(
            "check_pipeline._get_pipeline_process_args",
            return_value={"runner_workers": 2, "pm_parallel": False},
        ),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    return mock_out.getvalue()


def test_acceptance_four_sections_order_goal_pm_tasks_artifacts():
    """Spec 036: no --json, output shows Goal, PM/Orchestration, Tasks, Artifacts in order."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=_STATUS_REPORT_FULL,
        effectiveness_response=_EFFECTIVENESS,
    )
    out = _run_with_mock(mock_get).lower()
    g = out.find("goal (layer 0)")
    pm = out.find("pm / orchestration (layer 1)")
    t = out.find("tasks (layer 2)")
    a = out.find("artifacts (layer 3)")
    assert g >= 0 and pm >= 0 and t >= 0 and a >= 0
    assert g < pm < t < a


_STATUS_REPORT_FULL = {
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


def test_acceptance_json_includes_hierarchical_structure():
    """Spec 036: --json includes hierarchical data for script consumers."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=_STATUS_REPORT_FULL,
        effectiveness_response=_EFFECTIVENESS,
    )
    with (
        patch.object(sys, "argv", ["check_pipeline.py", "--json"]),
        patch("check_pipeline.httpx.get", side_effect=mock_get),
        patch(
            "check_pipeline._get_pipeline_process_args",
            return_value={"runner_workers": 2, "pm_parallel": False},
        ),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    data = json.loads(mock_out.getvalue())
    assert "hierarchical" in data
    h = data["hierarchical"]
    assert "layer_0_goal" in h and "layer_1_orchestration" in h
    assert "layer_2_execution" in h and "layer_3_attention" in h


def test_acceptance_flat_legacy_human_output():
    """Spec 036: --flat preserves legacy flat pipeline view (no layer labels)."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=_STATUS_REPORT_FULL,
        effectiveness_response=_EFFECTIVENESS,
    )
    with (
        patch.object(sys, "argv", ["check_pipeline.py", "--flat"]),
        patch("check_pipeline.httpx.get", side_effect=mock_get),
        patch(
            "check_pipeline._get_pipeline_process_args",
            return_value={"runner_workers": 2, "pm_parallel": False},
        ),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    out = mock_out.getvalue().lower()
    assert "pipeline status" in out
    assert "layer 0" not in out
    assert "running" in out


def test_acceptance_status_report_missing_effectiveness_fallback_goal_and_tasks_remain():
    """When status-report is unavailable but API is up: Goal from effectiveness; Tasks/Artifacts from pipeline-status."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=None,
        effectiveness_response=_EFFECTIVENESS,
        status_report_status=404,
    )
    out = _run_with_mock(mock_get).lower()
    assert "goal (layer 0)" in out
    assert "goal_proximity" in out or "0.55" in out
    assert "tasks (layer 2)" in out
    assert "vis_run_1" in out
    assert "artifacts (layer 3)" in out
    assert "900" in out or "chars" in out


def test_acceptance_status_report_placeholder_no_effectiveness_shows_not_generated():
    """Monitor placeholder summary: Goal falls through; without effectiveness, show not-yet-generated."""
    placeholder = {
        "layer_0_goal": {
            "status": "unknown",
            "summary": "Report not yet generated by monitor",
        },
        "layer_1_orchestration": {"status": "unknown", "summary": ""},
    }
    mock_get = _mock_httpx_get_factory(
        status_report_response=placeholder,
        effectiveness_response=None,
        effectiveness_status=404,
    )
    out = _run_with_mock(mock_get).lower()
    assert "goal (layer 0)" in out
    assert "report not yet generated" in out


def test_acceptance_json_hierarchical_when_status_report_missing_uses_built_layers():
    """JSON hierarchical key populated from pipeline + effectiveness when status-report file/API has no layers."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=None,
        effectiveness_response=_EFFECTIVENESS,
        status_report_status=404,
    )
    with (
        patch.object(sys, "argv", ["check_pipeline.py", "--json"]),
        patch("check_pipeline.httpx.get", side_effect=mock_get),
        patch(
            "check_pipeline._get_pipeline_process_args",
            return_value={"runner_workers": 2, "pm_parallel": False},
        ),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        check_pipeline.main()
    data = json.loads(mock_out.getvalue())
    h = data["hierarchical"]
    assert h["layer_0_goal"].get("goal_proximity") == 0.55
    assert len(h["layer_2_execution"].get("running", [])) >= 1


def test_visibility_pending_tasks_show_wait_times():
    """Layer 2: pending tasks include wait time (operator visibility)."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=_STATUS_REPORT_FULL,
        effectiveness_response=_EFFECTIVENESS,
    )
    out = _run_with_mock(mock_get)
    assert "vis_pend_1" in out
    assert "wait:" in out.lower() or "5s" in out


def test_visibility_artifacts_show_output_char_counts():
    """Layer 3: recent completed shows output size for artifact health."""
    mock_get = _mock_httpx_get_factory(
        status_report_response=_STATUS_REPORT_FULL,
        effectiveness_response=_EFFECTIVENESS,
    )
    out = _run_with_mock(mock_get).lower()
    assert "artifacts (layer 3)" in out
    assert "900" in out
    assert "chars" in out
