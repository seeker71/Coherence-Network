"""Tests for docs/RUNBOOK.md contract — spec 034 (Ops Runbook).

Tests define the contract: do not modify these to make implementation pass.
Ops runbook must cover API restart, log locations, pipeline recovery.
"""

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_runbook_path = _repo_root / "docs" / "RUNBOOK.md"

# Required section headings per spec 034 acceptance
REQUIRED_HEADINGS = ["Log Locations", "API Restart", "Pipeline Recovery"]
# At least one of these must be present (spec 034)
OPTIONAL_HEADINGS = ["Autonomous Pipeline", "Pipeline Effectiveness", "Key Endpoints"]


def _runbook_content() -> str:
    if not _runbook_path.exists():
        pytest.fail("docs/RUNBOOK.md must exist (spec 034)")
    return _runbook_path.read_text()


def test_runbook_md_exists():
    """docs/RUNBOOK.md must exist (spec 034)."""
    assert _runbook_path.exists(), "docs/RUNBOOK.md must exist"


def test_runbook_has_log_locations_section():
    """RUNBOOK.md must contain a Log Locations section (spec 034)."""
    content = _runbook_content()
    assert "Log Locations" in content, "RUNBOOK.md must contain section 'Log Locations'"


def test_runbook_log_locations_has_table():
    """Log Locations section must list log paths in a table with path and purpose (spec 034, 013)."""
    content = _runbook_content()
    assert "|" in content, "RUNBOOK.md Log Locations must use a table"
    assert "Path" in content and "Purpose" in content, (
        "RUNBOOK.md must have Path and Purpose columns for log locations"
    )
    assert "api/logs" in content, "RUNBOOK.md must list api/logs paths"


def test_runbook_has_api_restart_section():
    """RUNBOOK.md must contain an API Restart section (spec 034)."""
    content = _runbook_content()
    assert "API Restart" in content, "RUNBOOK.md must contain section 'API Restart'"


def test_runbook_api_restart_documents_uvicorn_pkill_port():
    """API Restart section must document uvicorn, process cleanup (pkill), and port (spec 034)."""
    content = _runbook_content()
    assert "uvicorn" in content, "RUNBOOK.md API Restart must mention uvicorn"
    assert "pkill" in content, "RUNBOOK.md API Restart must mention pkill for process cleanup"
    assert "8000" in content, "RUNBOOK.md API Restart must mention port 8000"


def test_runbook_has_pipeline_recovery_section():
    """RUNBOOK.md must contain a Pipeline Recovery section (spec 034)."""
    content = _runbook_content()
    assert "Pipeline Recovery" in content, "RUNBOOK.md must contain section 'Pipeline Recovery'"


def test_runbook_pipeline_recovery_documents_effectiveness_restart_needs_decision():
    """Pipeline Recovery must describe effectiveness check, restart, and unblocking needs_decision (spec 034)."""
    content = _runbook_content()
    assert "effectiveness" in content.lower() or "ensure_effective" in content, (
        "RUNBOOK.md Pipeline Recovery must mention effectiveness check"
    )
    assert "restart" in content.lower(), (
        "RUNBOOK.md Pipeline Recovery must mention restart (API or pipeline)"
    )
    assert "needs_decision" in content or "needs decision" in content.lower(), (
        "RUNBOOK.md Pipeline Recovery must describe unblocking needs_decision"
    )


def test_runbook_has_one_of_autonomous_effectiveness_key_endpoints():
    """RUNBOOK.md must contain at least one of: Autonomous Pipeline, Pipeline Effectiveness, Key Endpoints (spec 034)."""
    content = _runbook_content()
    found = sum(1 for h in OPTIONAL_HEADINGS if h in content)
    assert found >= 1, (
        f"RUNBOOK.md must contain at least one of {OPTIONAL_HEADINGS} (spec 034)"
    )


def test_runbook_has_all_required_sections():
    """RUNBOOK.md must contain all required section headings: Log Locations, API Restart, Pipeline Recovery (spec 034)."""
    content = _runbook_content()
    for heading in REQUIRED_HEADINGS:
        assert heading in content, f"RUNBOOK.md must contain section '{heading}' (spec 034)"


def test_runbook_documents_indexing():
    """RUNBOOK.md must document index_npm.py and index_pypi.py usage (spec 034, 008, 024)."""
    content = _runbook_content()
    assert "index_npm" in content, "RUNBOOK.md must document index_npm.py"
    assert "index_pypi" in content, "RUNBOOK.md must document index_pypi.py"


def test_runbook_documents_check_pipeline():
    """RUNBOOK.md must document check_pipeline.py and --json for scripting (spec 034)."""
    content = _runbook_content()
    assert "check_pipeline" in content, "RUNBOOK.md must document check_pipeline.py"
    assert "--json" in content, "RUNBOOK.md must document --json for scripting"


def test_runbook_documents_tests_and_cleanup():
    """RUNBOOK.md must document how to run tests and cleanup of old task logs (spec 034)."""
    content = _runbook_content()
    assert "pytest" in content, "RUNBOOK.md must document how to run tests"
    assert "task" in content.lower() and ("cleanup" in content.lower() or "delete" in content.lower() or "find" in content), (
        "RUNBOOK.md must document cleanup of old task logs (e.g. find task_*.log or cleanup script)"
    )
