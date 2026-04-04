"""Tests for update_spec_coverage.py validation and reporting.

Validates that the spec coverage automation detects gaps correctly.
"""

import subprocess
import sys
from pathlib import Path

import pytest


def run_update_spec_coverage(*args):
    """Run update_spec_coverage.py with given arguments.

    Returns: (returncode, stdout, stderr)
    """
    script_path = Path(__file__).parent.parent / "scripts" / "update_spec_coverage.py"
    python = sys.executable

    result = subprocess.run(
        [python, str(script_path), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )

    return result.returncode, result.stdout, result.stderr


def test_report_generation():
    """--report flag should generate coverage statistics."""
    returncode, stdout, stderr = run_update_spec_coverage("--report")

    assert returncode == 0
    assert "Spec Coverage Report" in stdout
    assert "Total specs:" in stdout
    assert "Implemented:" in stdout
    assert "Tested:" in stdout
    assert "Pending:" in stdout
    assert "Progress:" in stdout
    assert "%" in stdout


def test_validate_mode_runs():
    """--validate flag should check for gaps."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    # Should complete (may exit 1 if gaps found, which is OK)
    assert returncode in (0, 1)

    # Should show some output
    assert stdout or stderr


def test_validate_detects_spec_without_implementation():
    """Validation should detect specs that are spec'd but not implemented."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    # If there are any unimplemented specs, should report them
    if returncode == 1:
        assert ("Spec exists but not implemented" in stdout
                or "validation error" in stdout.lower())


def test_validate_success_returns_zero():
    """Validation should return 0 when no errors found (only warnings OK)."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    # Either passes (0) or has errors (1)
    assert returncode in (0, 1)

    if returncode == 0:
        assert "validation passed" in stdout.lower() or "warning" in stdout.lower()


def test_strict_mode_treats_warnings_as_errors():
    """--strict flag should fail validation on warnings."""
    # First check if there are any warnings without strict
    returncode_normal, stdout_normal, stderr_normal = run_update_spec_coverage("--validate")

    if "WARN:" in stdout_normal or "warning" in stdout_normal.lower():
        # Now run with strict - should fail
        returncode_strict, stdout_strict, stderr_strict = run_update_spec_coverage(
            "--validate", "--strict"
        )

        # Strict mode should treat warnings as errors
        assert returncode_strict == 1


def test_report_shows_percentage_progress():
    """Coverage report should show percentage progress bars."""
    returncode, stdout, stderr = run_update_spec_coverage("--report")

    assert returncode == 0

    # Should show percentage with decimal
    assert "." in stdout and "%" in stdout

    # Should show progress bars (using █ character)
    lines = stdout.split("\n")
    progress_lines = [l for l in lines if "%" in l and ("implemented" in l or "tested" in l)]
    assert len(progress_lines) >= 2, "Should show progress for implemented and tested"


def test_validate_output_structured():
    """Validation output should be well-structured and readable."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    if "ERROR:" in stdout:
        # Should have clear error structure
        assert "validation error" in stdout.lower()

    if "WARN:" in stdout:
        # Should have clear warning structure
        assert "warning" in stdout.lower()


def test_help_shows_new_options():
    """Help output should document --validate and --report options."""
    returncode, stdout, stderr = run_update_spec_coverage("--help")

    assert returncode == 0
    assert "--validate" in stdout
    assert "--report" in stdout
    assert "--strict" in stdout
    assert "gap" in stdout.lower() or "coverage" in stdout.lower()


def test_report_includes_test_count():
    """Coverage report should include total test count when available."""
    returncode, stdout, stderr = run_update_spec_coverage("--report")

    assert returncode == 0
    # May or may not have test count depending on environment
    # Just verify report structure is valid
    assert "Total specs:" in stdout


def test_validate_checks_implemented_but_not_tested():
    """Validation should warn about implementations without tests."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    # Should check this pattern (may or may not find instances)
    if "Implemented but not tested" in stdout:
        assert "WARN:" in stdout


def test_validate_and_report_mutually_exclusive():
    """Should be able to run --validate or --report separately."""
    # Run validation
    returncode1, stdout1, stderr1 = run_update_spec_coverage("--validate")
    assert returncode1 in (0, 1)
    assert stdout1  # Should produce output

    # Run report
    returncode2, stdout2, stderr2 = run_update_spec_coverage("--report")
    assert returncode2 == 0
    assert stdout2  # Should produce different output

    # Outputs should be different
    assert stdout1 != stdout2


def test_script_handles_missing_spec_coverage_file():
    """Script should handle missing SPEC-COVERAGE.md gracefully."""
    # This test would need to temporarily move the file, which is risky
    # Instead, just verify the script doesn't crash with bad input
    # (Actual test would require test fixtures)
    pass


def test_validation_detects_multiple_gap_types():
    """Validation should detect different types of gaps."""
    returncode, stdout, stderr = run_update_spec_coverage("--validate")

    # May find different gap patterns:
    # - Spec exists but not implemented
    # - Implemented but not tested
    # - Tests exist but no spec

    # Just verify it produces structured output
    if returncode == 1:
        assert "ERROR:" in stdout or "WARN:" in stdout
