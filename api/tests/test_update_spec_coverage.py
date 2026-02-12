"""Tests for update_spec_coverage.py — spec 027 auto-update framework."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Import script helpers for unit tests (script runs as main for CLI)
_api_dir = Path(__file__).resolve().parent.parent
_scripts_dir = _api_dir / "scripts"
sys.path.insert(0, str(_scripts_dir))
try:
    from update_spec_coverage import (
        _existing_spec_ids,
        _format_specs_implemented,
        _format_specs_pending,
        _parse_spec_coverage_table,
        _spec_id_from_path,
        _table_insert_point,
        _update_status_sections,
    )
finally:
    sys.path.pop(0)


def test_update_spec_coverage_dry_run():
    """--dry-run exits 0, prints preview, and does not modify SPEC-COVERAGE or STATUS (spec 027)."""
    spec_coverage = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    status_md = _api_dir.parent / "docs" / "STATUS.md"
    if not spec_coverage.exists():
        pytest.skip("SPEC-COVERAGE.md not in repo")
    before_coverage = spec_coverage.read_text()
    before_status = status_md.read_text() if status_md.exists() else None
    result = subprocess.run(
        [sys.executable, str(_scripts_dir / "update_spec_coverage.py"), "--dry-run", "--tests-passed"],
        cwd=str(_api_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    # Contract: dry-run must print a preview (spec 027 acceptance)
    assert (
        "(Dry run" in result.stdout
        or "Would add" in result.stdout
        or "No new specs" in result.stdout
    ), f"dry-run must print preview; got: {result.stdout!r}"
    assert spec_coverage.read_text() == before_coverage
    if before_status is not None:
        assert status_md.read_text() == before_status


# Contract (spec 027): exact message when omitting --tests-passed locally
SKIP_MESSAGE = "Skipping (tests not confirmed passed). Use --tests-passed or run in CI."


def test_dry_run_without_tests_passed_no_op():
    """Without --tests-passed and not in CI, script no-ops, prints skip message, exits 0 (spec 027)."""
    spec_coverage = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    if not spec_coverage.exists():
        pytest.skip("SPEC-COVERAGE.md not in repo")
    before = spec_coverage.read_text()
    env = os.environ.copy()
    env.pop("CI", None)
    result = subprocess.run(
        [sys.executable, str(_scripts_dir / "update_spec_coverage.py"), "--dry-run"],
        cwd=str(_api_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert SKIP_MESSAGE in result.stdout, f"Contract: script must print skip message; got: {result.stdout!r}"
    assert spec_coverage.read_text() == before


def test_existing_spec_ids():
    """_existing_spec_ids parses table rows."""
    content = """
| Spec | Present | Spec'd | Tested | Notes |
|------|---------|--------|--------|-------|
| 001 Health | ✓ | ✓ | ✓ | Complete |
| 002 Agent Orchestration | ✓ | ✓ | ✓ | Complete |
| 006 Overnight Backlog | ? | ? | ? | Pending |
**Present:** Implemented.
"""
    ids = _existing_spec_ids(content)
    assert "001" in ids
    assert "002" in ids
    assert "006" in ids
    assert len(ids) == 3


def test_table_insert_point():
    """_table_insert_point finds line before **Present:**."""
    content = """| 001 Health | ✓ | ✓ | ✓ | Complete |
| 002 Agent | ✓ | ✓ | ✓ | Complete |
**Present:** Implemented.
"""
    idx = _table_insert_point(content)
    lines = content.splitlines()
    assert idx == 2
    assert "**Present:**" in lines[idx]


def test_parse_spec_coverage_table():
    """_parse_spec_coverage_table returns implemented and pending from Present column."""
    content = """
| 001 Health | ✓ | ✓ | ✓ | Complete |
| 002 Agent | ✓ | ✓ | ✓ | Complete |
| 006 Backlog | ? | ? | ? | Pending |
"""
    impl, pend = _parse_spec_coverage_table(content)
    assert len(impl) == 2
    assert (impl[0][0], impl[0][1]) == ("001", "Health")
    assert (impl[1][0], impl[1][1]) == ("002", "Agent")
    assert len(pend) == 1
    assert (pend[0][0], pend[0][1]) == ("006", "Backlog")


def test_format_specs_implemented():
    """_format_specs_implemented produces STATUS-style bullets."""
    implemented = [("001", "Health"), ("002", "Agent API")]
    out = _format_specs_implemented(implemented)
    assert "- 001 Health" in out
    assert "- 002 Agent API" in out
    assert _format_specs_implemented([]) == "- None"


def test_script_without_tests_passed_or_ci_prints_exact_skip_message():
    """Contract (spec 027): without --tests-passed and not in CI, script prints exact skip message."""
    env = os.environ.copy()
    env.pop("CI", None)
    result = subprocess.run(
        [sys.executable, str(_scripts_dir / "update_spec_coverage.py")],
        cwd=str(_api_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert SKIP_MESSAGE in result.stdout, f"Contract: script must print '{SKIP_MESSAGE}'; got: {result.stdout!r}"


def test_format_specs_pending():
    """_format_specs_pending produces STATUS-style bullets."""
    pending = [("006", "Overnight Backlog")]
    out = _format_specs_pending(pending)
    assert "- 006 Overnight Backlog" in out
    assert _format_specs_pending([]) == "- None"


def test_update_status_sections_reflects_spec_coverage():
    """STATUS update: Specs Implemented / Pending derived from SPEC-COVERAGE (integration)."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    status_path = _api_dir.parent / "docs" / "STATUS.md"
    if not spec_coverage_path.exists() or not status_path.exists():
        pytest.skip("docs not in repo")
    coverage_content = spec_coverage_path.read_text()
    status_content = status_path.read_text()
    updated = _update_status_sections(status_content, coverage_content, test_count=74)
    assert "## Specs Implemented" in updated
    assert "## Specs Pending Implementation" in updated
    assert "74 tests" in updated or "## Test Count" in updated


def test_ci_workflow_runs_script_after_pytest_non_blocking():
    """CI workflow runs update_spec_coverage after pytest; step has continue-on-error (spec 027)."""
    workflow_path = _api_dir.parent / ".github" / "workflows" / "test.yml"
    if not workflow_path.exists():
        pytest.skip(".github/workflows/test.yml not in repo")
    content = workflow_path.read_text()
    run_api_tests_pos = content.find("Run API tests")
    update_spec_pos = content.find("Update spec coverage")
    assert run_api_tests_pos != -1, "Workflow must have 'Run API tests' step"
    assert update_spec_pos != -1, "Workflow must have 'Update spec coverage' step"
    assert run_api_tests_pos < update_spec_pos, "Script must run after pytest step"
    # continue-on-error must appear in the Update spec coverage step (before next - name:)
    after_update = content[update_spec_pos:]
    next_step = after_update.find("\n      - name:", 1)
    step_block = after_update[: next_step if next_step != -1 else len(after_update)]
    assert "continue-on-error: true" in step_block, (
        "Update spec coverage step must have continue-on-error: true so CI does not fail on script failure"
    )


def test_script_idempotent_second_run_unchanged():
    """Repeated run with no new specs or test changes leaves SPEC-COVERAGE and STATUS unchanged (spec 027)."""
    spec_coverage = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    status_md = _api_dir.parent / "docs" / "STATUS.md"
    if not spec_coverage.exists():
        pytest.skip("SPEC-COVERAGE.md not in repo")
    env = os.environ.copy()
    env["TEST_COUNT"] = "74"  # deterministic test count
    cmd = [sys.executable, str(_scripts_dir / "update_spec_coverage.py"), "--tests-passed"]
    subprocess.run(cmd, cwd=str(_api_dir), env=env, capture_output=True, text=True, timeout=30)
    after_first = (spec_coverage.read_text(), status_md.read_text() if status_md.exists() else "")
    subprocess.run(cmd, cwd=str(_api_dir), env=env, capture_output=True, text=True, timeout=30)
    assert spec_coverage.read_text() == after_first[0], "Second run must not change SPEC-COVERAGE"
    if after_first[1]:
        assert status_md.read_text() == after_first[1], "Second run must not change STATUS.md"


def test_spec_coverage_additive_all_specs_have_row():
    """Contract: after script run, every spec id from specs/ appears in SPEC-COVERAGE (additive, spec 027)."""
    specs_dir = _api_dir.parent / "specs"
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    status_path = _api_dir.parent / "docs" / "STATUS.md"
    if not specs_dir.exists() or not spec_coverage_path.exists():
        pytest.skip("specs/ or SPEC-COVERAGE.md not in repo")
    before_coverage = spec_coverage_path.read_text()
    before_status = status_path.read_text() if status_path.exists() else None
    try:
        env = os.environ.copy()
        env["TEST_COUNT"] = "74"
        result = subprocess.run(
            [sys.executable, str(_scripts_dir / "update_spec_coverage.py"), "--tests-passed"],
            cwd=str(_api_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        coverage_content = spec_coverage_path.read_text()
        existing_ids = _existing_spec_ids(coverage_content)
        for f in specs_dir.iterdir():
            if not f.suffix == ".md":
                continue
            sid = _spec_id_from_path(str(f))
            if sid is not None:
                assert sid in existing_ids, (
                    f"Spec {sid} ({f.name}) must have a row in SPEC-COVERAGE after script run (additive)"
                )
    finally:
        spec_coverage_path.write_text(before_coverage)
        if before_status is not None and status_path.exists():
            status_path.write_text(before_status)


def test_status_after_script_has_specs_implemented_and_test_count():
    """After script run, STATUS.md has Specs Implemented and Test count from SPEC-COVERAGE (spec 027)."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    status_path = _api_dir.parent / "docs" / "STATUS.md"
    if not spec_coverage_path.exists() or not status_path.exists():
        pytest.skip("docs not in repo")
    before_status = status_path.read_text()
    before_coverage = spec_coverage_path.read_text()
    try:
        env = os.environ.copy()
        env["TEST_COUNT"] = "74"
        result = subprocess.run(
            [sys.executable, str(_scripts_dir / "update_spec_coverage.py"), "--tests-passed"],
            cwd=str(_api_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        status_content = status_path.read_text()
        assert "## Specs Implemented" in status_content
        assert "- " in status_content.split("## Specs Implemented")[1].split("## ")[0]
        assert "## Test Count" in status_content
        assert re.search(r"\d+\s+tests?", status_content), "Test count number must appear in STATUS"
    finally:
        status_path.write_text(before_status)
        spec_coverage_path.write_text(before_coverage)


# --- Contract tests: SPEC-COVERAGE must accurately reflect specs 007, 008, 034, 038 and new specs ---

def test_spec_coverage_includes_specs_007_008_034_038():
    """Contract: SPEC-COVERAGE.md has a row for specs 007, 008, 034, and 038 (and other new specs)."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    if not spec_coverage_path.exists():
        pytest.skip("SPEC-COVERAGE.md not in repo")
    content = spec_coverage_path.read_text()
    existing = _existing_spec_ids(content)
    assert "007" in existing, "SPEC-COVERAGE must list spec 007 (Sprint 0 Landing)"
    assert "008" in existing, "SPEC-COVERAGE must list spec 008 (Sprint 1 Graph)"
    assert "034" in existing, "SPEC-COVERAGE must list spec 034 (Ops Runbook)"
    assert "038" in existing, "SPEC-COVERAGE must list spec 038 (POST empty direction 422)"


def test_spec_007_coverage_references_existing_tests():
    """Contract: Spec 007 section references test_root_returns_landing_info and test_docs_returns_200; those tests exist."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    test_health_path = _api_dir / "tests" / "test_health.py"
    if not spec_coverage_path.exists() or not test_health_path.exists():
        pytest.skip("SPEC-COVERAGE.md or test_health.py not in repo")
    coverage_content = spec_coverage_path.read_text()
    health_content = test_health_path.read_text()
    assert "007" in coverage_content and "Sprint 0" in coverage_content
    assert "test_root_returns_landing_info" in coverage_content, "SPEC-COVERAGE 007 must reference test_root_returns_landing_info"
    assert "test_docs_returns_200" in coverage_content, "SPEC-COVERAGE 007 must reference test_docs_returns_200"
    assert "def test_root_returns_landing_info" in health_content, "test_health.py must define test_root_returns_landing_info"
    assert "def test_docs_returns_200" in health_content, "test_health.py must define test_docs_returns_200"


def test_spec_008_coverage_references_implementation_and_tests():
    """Contract: Spec 008 section references 019, projects/graph tests; those test modules and functions exist."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    test_projects_path = _api_dir / "tests" / "test_projects.py"
    test_graph_path = _api_dir / "tests" / "test_graph_store.py"
    if not spec_coverage_path.exists() or not test_projects_path.exists() or not test_graph_path.exists():
        pytest.skip("SPEC-COVERAGE.md or test_projects/test_graph_store not in repo")
    coverage_content = spec_coverage_path.read_text()
    projects_content = test_projects_path.read_text()
    graph_content = test_graph_path.read_text()
    assert "008" in coverage_content and "Sprint 1" in coverage_content
    assert "019" in coverage_content or "test_projects" in coverage_content or "test_graph" in coverage_content
    assert "test_get_project_returns_200_when_exists" in projects_content
    assert "test_get_project_returns_404_when_missing" in projects_content
    assert "test_search_returns_matching_results" in projects_content
    assert "def test_search" in graph_content or "test_get_project_missing" in graph_content


def test_spec_034_runbook_exists_with_required_sections():
    """Contract (spec 034): docs/RUNBOOK.md exists and contains Log Locations, API Restart, Pipeline Recovery, and one of (Autonomous Pipeline, Pipeline Effectiveness, Key Endpoints)."""
    runbook_path = _api_dir.parent / "docs" / "RUNBOOK.md"
    if not runbook_path.exists():
        pytest.fail("docs/RUNBOOK.md must exist (spec 034)")
    content = runbook_path.read_text()
    required = ["Log Locations", "API Restart", "Pipeline Recovery"]
    for heading in required:
        assert heading in content, f"RUNBOOK.md must contain section '{heading}' (spec 034)"
    optional = ["Autonomous Pipeline", "Pipeline Effectiveness", "Key Endpoints"]
    found = sum(1 for h in optional if h in content)
    assert found >= 1, f"RUNBOOK.md must contain at least one of {optional} (spec 034)"


def test_spec_038_coverage_references_existing_test():
    """Contract: Spec 038 section in SPEC-COVERAGE references test_post_task_empty_direction_returns_422; that test exists."""
    spec_coverage_path = _api_dir.parent / "docs" / "SPEC-COVERAGE.md"
    test_agent_path = _api_dir / "tests" / "test_agent.py"
    if not spec_coverage_path.exists() or not test_agent_path.exists():
        pytest.skip("SPEC-COVERAGE.md or test_agent.py not in repo")
    coverage_content = spec_coverage_path.read_text()
    agent_content = test_agent_path.read_text()
    assert "038" in coverage_content and "empty direction" in coverage_content.lower()
    assert "test_post_task_empty_direction_returns_422" in coverage_content, (
        "SPEC-COVERAGE 038 must reference test_post_task_empty_direction_returns_422"
    )
    assert "def test_post_task_empty_direction_returns_422" in agent_content or "async def test_post_task_empty_direction_returns_422" in agent_content, (
        "test_agent.py must define test_post_task_empty_direction_returns_422 (spec 038)"
    )
