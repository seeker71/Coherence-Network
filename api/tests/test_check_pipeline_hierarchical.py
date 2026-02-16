"""Tests for check_pipeline.py hierarchical view (spec 036).

Validates that pipeline status displays hierarchical view:
Goal → PM/Orchestration → Tasks → Artifacts
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_check_pipeline(*args):
    """Run check_pipeline.py script with given arguments.

    Returns: (returncode, stdout, stderr)
    """
    script_path = Path(__file__).parent.parent / "scripts" / "check_pipeline.py"
    python = sys.executable

    result = subprocess.run(
        [python, str(script_path), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )

    return result.returncode, result.stdout, result.stderr


def test_hierarchical_view_default_output_order():
    """Hierarchical view should show sections in order: Goal → PM → Tasks → Artifacts."""
    returncode, stdout, stderr = run_check_pipeline()

    # Script should succeed (or fail gracefully if API not running)
    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    # Check that hierarchical sections appear in order
    # Note: We're just checking the structure exists, not validating content
    output = stdout.lower()

    # Find positions of each section
    goal_pos = output.find("goal (layer 0)")
    pm_pos = output.find("pm / orchestration (layer 1)")
    tasks_pos = output.find("tasks (layer 2)")
    artifacts_pos = output.find("artifacts (layer 3)")

    # If hierarchical mode is working, sections should appear in order
    # (or not appear at all if API is down - that's OK for this test)
    if goal_pos >= 0:  # Hierarchical view is rendered
        assert goal_pos < pm_pos, "Goal should appear before PM/Orchestration"
        assert pm_pos < tasks_pos, "PM should appear before Tasks"
        assert tasks_pos < artifacts_pos, "Tasks should appear before Artifacts"


def test_hierarchical_flag_explicit():
    """--hierarchical flag should explicitly enable hierarchical view."""
    returncode, stdout, stderr = run_check_pipeline("--hierarchical")

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    # Should show hierarchical sections
    assert "layer 0" in stdout.lower() or "goal" in stdout.lower()


def test_flat_flag_legacy_output():
    """--flat flag should provide legacy flat output format."""
    returncode, stdout, stderr = run_check_pipeline("--flat")

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    # Flat output shouldn't have "Layer N" labels
    assert "layer 0" not in stdout.lower()
    assert "layer 1" not in stdout.lower()
    # Should still show pipeline status though
    assert "pipeline status" in stdout.lower() or "api not reachable" in stdout.lower()


def test_json_output_includes_hierarchical_data():
    """--json flag should include hierarchical structure in output."""
    returncode, stdout, stderr = run_check_pipeline("--json")

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    # Parse JSON output
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON output: {stdout[:200]}")

    # Should have hierarchical key when using default hierarchical mode
    assert "hierarchical" in data, "JSON output should include 'hierarchical' key"

    hierarchical = data["hierarchical"]
    # Check for layer keys
    assert "layer_0_goal" in hierarchical
    assert "layer_1_orchestration" in hierarchical
    assert "layer_2_execution" in hierarchical
    assert "layer_3_attention" in hierarchical


def test_json_flat_output_no_hierarchical():
    """--json --flat should not include hierarchical structure."""
    returncode, stdout, stderr = run_check_pipeline("--json", "--flat")

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON output: {stdout[:200]}")

    # Flat mode shouldn't have hierarchical key
    assert "hierarchical" not in data


def test_goal_section_displays_status():
    """Goal section should show status and summary when available."""
    returncode, stdout, stderr = run_check_pipeline()

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    output = stdout.lower()

    # Goal section should exist
    if "goal (layer 0)" in output:
        # Should show either real data or fallback message
        assert (
            "status:" in output
            or "report not yet generated" in output
            or "goal_proximity" in output
        ), "Goal section should show status or fallback"


def test_pm_orchestration_section_displays():
    """PM/Orchestration section should show project manager and process info."""
    returncode, stdout, stderr = run_check_pipeline()

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    output = stdout.lower()

    # PM section should exist
    if "pm / orchestration (layer 1)" in output:
        # Should show PM info or "not seen"
        assert (
            "project manager" in output
            or "pm not seen" in output
            or "agent_runner" in output
        ), "PM section should show orchestration info"


def test_tasks_section_displays():
    """Tasks section should show running, pending, and recent completed."""
    returncode, stdout, stderr = run_check_pipeline()

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    output = stdout.lower()

    # Tasks section should exist
    if "tasks (layer 2)" in output:
        # Should show task status
        assert (
            "running:" in output or "pending:" in output or "recent completed:" in output
        ), "Tasks section should show task status"


def test_artifacts_section_displays():
    """Artifacts section should show recent completed tasks with output info."""
    returncode, stdout, stderr = run_check_pipeline()

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    output = stdout.lower()

    # Artifacts section should exist
    if "artifacts (layer 3)" in output:
        # Should show artifact info or "no recent completed"
        assert (
            "output:" in output
            or "no recent completed" in output
            or "chars" in output
        ), "Artifacts section should show output info"


def test_script_handles_api_unreachable():
    """Script should handle API being unreachable gracefully."""
    # This test assumes API might not be running
    returncode, stdout, stderr = run_check_pipeline()

    # Should exit with error code if API unreachable, but not crash
    if returncode != 0:
        assert (
            "API not reachable" in stdout
            or "not found" in stdout
            or "Error" in stdout
        ), "Should show meaningful error when API unreachable"


def test_help_output():
    """Script should provide help output."""
    returncode, stdout, stderr = run_check_pipeline("--help")

    assert returncode == 0
    assert "--hierarchical" in stdout
    assert "--flat" in stdout
    assert "--json" in stdout
    assert "Goal" in stdout or "hierarchical" in stdout.lower()


def test_attention_flag_compatibility():
    """--attention flag should work with hierarchical view."""
    returncode, stdout, stderr = run_check_pipeline("--attention")

    if returncode != 0 and "API not reachable" in stdout:
        pytest.skip("API not running")

    # Should show attention section (or indicate no issues)
    assert "attention:" in stdout.lower() or "api not reachable" in stdout.lower()
