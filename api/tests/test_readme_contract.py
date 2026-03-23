"""Tests for README.md contract — spec 033 (qualify or remove web/docker in Quick Start).

README must not present 'cd web' or docker compose as current, unqualified options.
The getting-started section (Quick Start or Your first 5 minutes) must provide
a working path to interact with the API.
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


def _getting_started_section(content: str) -> str:
    """Extract getting-started section (Quick Start or Your first 5 minutes)."""
    for heading in ("## Quick Start", "## Your first 5 minutes"):
        if heading in content:
            start = content.index(heading)
            rest = content[start:]
            if "## " in rest[rest.index("\n") + 1 :]:
                end = rest.index("## ", rest.index("\n") + 1)
                return rest[:end]
            return rest
    return ""


def test_readme_exists():
    """README.md must exist at repo root (spec 033)."""
    assert _readme_md.exists(), "README.md must exist at repo root"


def test_readme_has_getting_started():
    """README must have a getting-started section (spec 033)."""
    content = _readme_content()
    has_section = "## Quick Start" in content or "## Your first 5 minutes" in content
    assert has_section, "README must have a '## Quick Start' or '## Your first 5 minutes' section"


def test_readme_getting_started_no_unqualified_cd_web():
    """Getting started must not present 'cd web' as a primary/unqualified path (spec 033)."""
    content = _readme_content()
    section = _getting_started_section(content)
    if not section:
        pytest.skip("No getting-started section found")
    if "cd web" in section:
        qualifying = (
            "not yet available" in section
            or "when web/ is added" in section
            or "when web/ is set up" in section
            or "specs/012" in section
            or "not yet" in section
        )
        assert qualifying, (
            "Getting started contains 'cd web' but must qualify it"
        )


def test_readme_getting_started_no_unqualified_npm_run_dev():
    """Getting started must not present 'npm run dev' as a primary/unqualified path (spec 033)."""
    content = _readme_content()
    section = _getting_started_section(content)
    if not section:
        pytest.skip("No getting-started section found")
    if "npm run dev" in section:
        qualifying = (
            "not yet available" in section
            or "when web/ is added" in section
            or "when web/ is set up" in section
            or "specs/012" in section
            or "not yet" in section
            or "planned" in section
        )
        assert qualifying, (
            "Getting started contains 'npm run dev' but must qualify it"
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
            "README contains 'docker compose' (or docker-compose) but must remove or qualify it"
        )


def test_readme_has_working_api_path():
    """README must include a working path to interact with the API (spec 033)."""
    content = _readme_content()
    has_api_path = (
        ("cd api" in content and "uvicorn" in content)
        or "api.coherencycoin.com" in content
        or "coherence-cli" in content
    )
    assert has_api_path, (
        "README must include a working API path (local uvicorn, public API URL, or CLI)"
    )
