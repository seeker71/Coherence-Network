"""Tests for CI pipeline contract — spec 004 (workflow, local equivalent, badge).

Verification: workflow present and triggers on push/PR; local equivalent passes;
badge in README displays status. Tests define the contract: do not modify these
to make implementation pass.
"""

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_workflow_yml = _repo_root / ".github" / "workflows" / "test.yml"
_readme_md = _repo_root / "README.md"


def _workflow_content() -> str:
    if not _workflow_yml.exists():
        pytest.skip(".github/workflows/test.yml not in repo")
    return _workflow_yml.read_text()


def _readme_content() -> str:
    if not _readme_md.exists():
        pytest.skip("README.md not in repo")
    return _readme_md.read_text()


def test_workflow_file_exists():
    """GitHub Actions workflow must exist at .github/workflows/test.yml (spec 004)."""
    assert _workflow_yml.exists(), (
        ".github/workflows/test.yml must exist (spec 004)"
    )


def test_workflow_triggers_on_push_and_pull_request():
    """Workflow must run on push to main/master and on pull_request (spec 004)."""
    content = _workflow_content()
    assert "on:" in content or "on:\n" in content, "Workflow must define 'on:' triggers"
    assert "push" in content, "Workflow must trigger on push"
    assert "pull_request" in content, "Workflow must trigger on pull_request"
    assert ("main" in content or "master" in content), (
        "Workflow must target main or master branch"
    )


def test_workflow_uses_python_39_or_newer():
    """Workflow must install Python 3.9+ (spec 004)."""
    content = _workflow_content()
    assert "3.9" in content or "3.10" in content or "3.11" in content or "3.12" in content, (
        "Workflow must use Python 3.9 or newer (e.g. python-version: \"3.9\")"
    )


def test_workflow_installs_api_dev_deps():
    """Workflow must run pip install -e \".[dev]\" in api/ (spec 004)."""
    content = _workflow_content()
    assert "api" in content and "pip install" in content and ".[dev]" in content, (
        "Workflow must install API dev deps: cd api && pip install -e \".[dev]\""
    )


def test_workflow_runs_pytest_in_api():
    """Workflow must run pytest -v in api/ (spec 004)."""
    content = _workflow_content()
    assert "pytest" in content and "api" in content, (
        "Workflow must run pytest in api/ (e.g. cd api && pytest -v)"
    )
    assert "-v" in content or "pytest -v" in content, (
        "Workflow must run pytest with -v (verbose)"
    )


def test_readme_has_ci_badge():
    """README must include a CI status badge linking to the test workflow (spec 004)."""
    content = _readme_content()
    assert "badge.svg" in content or "badge" in content.lower(), (
        "README must include a CI status badge (e.g. .../workflows/test.yml/badge.svg)"
    )
    assert "test.yml" in content or "workflows" in content, (
        "README badge must reference the test workflow (test.yml)"
    )
