"""Tests for README.md contract — spec 033 (qualify or remove web/docker in Quick Start).

README must not present 'cd web' or docker compose as current, unqualified options.
Tests define the contract: do not modify these to make implementation pass.
"""

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_readme_md = _repo_root / "README.md"


def _readme_content() -> str:
    if not _readme_md.exists():
        pytest.skip("README.md not in repo")
    return _readme_md.read_text()


def _quick_start_section(content: str) -> str:
    """Extract Quick Start section (from ## Quick Start to next ## or end)."""
    if "## Quick Start" not in content:
        return ""
    start = content.index("## Quick Start")
    rest = content[start:]
    if "## " in rest[rest.index("\n") + 1 :]:
        end = rest.index("## ", rest.index("\n") + 1)
        return rest[:end]
    return rest


def test_readme_exists():
    """README.md must exist at repo root (spec 033)."""
    assert _readme_md.exists(), "README.md must exist at repo root"


def test_readme_quick_start_no_unqualified_cd_web():
    """Quick Start must not present 'cd web' as a primary/unqualified path (spec 033)."""
    content = _readme_content()
    quick = _quick_start_section(content)
    assert "## Quick Start" in content, "README must have a Quick Start section"
    if "cd web" in quick:
        qualifying = (
            "not yet available"
            in quick
            or "when web/ is added"
            in quick
            or "when web/ is set up"
            in quick
            or "specs/012"
            in quick
            or "not yet"
            in quick
        )
        assert qualifying, (
            "Quick Start contains 'cd web' but must qualify it (e.g. 'Web app: not yet available' or 'See specs/012 when web/ is added')"
        )


def test_readme_quick_start_no_unqualified_npm_run_dev():
    """Quick Start must not present 'npm run dev' as a primary/unqualified path (spec 033)."""
    content = _readme_content()
    quick = _quick_start_section(content)
    assert "## Quick Start" in content, "README must have a Quick Start section"
    if "npm run dev" in quick:
        qualifying = (
            "not yet available"
            in quick
            or "when web/ is added"
            in quick
            or "when web/ is set up"
            in quick
            or "specs/012"
            in quick
            or "not yet"
            in quick
            or "planned"
            in quick
        )
        assert qualifying, (
            "Quick Start contains 'npm run dev' but must qualify it (e.g. 'Web app: not yet available' or 'See specs/012 when web/ is added')"
        )


def test_readme_no_unqualified_docker_compose():
    """README must not contain unqualified 'docker compose' or 'docker-compose' (spec 033)."""
    content = _readme_content()
    lower = content.lower()
    if "docker compose" in lower or "docker-compose" in lower:
        qualifying = (
            "not yet" in content
            or "future" in content
            or "when docker" in content.lower()
            or "not yet available" in content
        )
        assert qualifying, (
            "README contains 'docker compose' (or docker-compose) but must remove or qualify it (e.g. 'not yet available')"
        )


def test_readme_quick_start_has_api_path():
    """Quick Start must include working API command: cd api && uvicorn (spec 033)."""
    content = _readme_content()
    quick = _quick_start_section(content)
    assert "cd api" in quick and "uvicorn" in quick, (
        "Quick Start must include a working API path (e.g. cd api && uvicorn app.main:app --reload --port 8000)"
    )
