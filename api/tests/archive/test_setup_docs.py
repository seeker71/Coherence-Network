"""Tests for docs/SETUP.md contract — spec 031 (Troubleshooting, venv path note for scripts).

Tests define the contract: do not modify these to make implementation pass.
"""

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_setup_md = _repo_root / "docs" / "SETUP.md"


def _setup_content() -> str:
    if not _setup_md.exists():
        pytest.skip("docs/SETUP.md not in repo")
    return _setup_md.read_text()


def test_setup_md_exists():
    """docs/SETUP.md must exist (spec 031)."""
    assert _setup_md.exists(), "docs/SETUP.md must exist"


def test_setup_has_troubleshooting_section():
    """SETUP.md must have a Troubleshooting section (spec 031)."""
    content = _setup_content()
    assert "## Troubleshooting" in content, "SETUP.md must contain ## Troubleshooting"


def test_troubleshooting_covers_required_topics():
    """Troubleshooting must include: ModuleNotFoundError/import errors, pytest not found, port in use, venv activation vs path (spec 031)."""
    content = _setup_content()
    # Require section exists so we're asserting within it; headings don't guarantee order
    assert "## Troubleshooting" in content
    troubleshooting = content.split("## Troubleshooting", 1)[-1].split("## ", 1)[0]
    problems = troubleshooting.lower()
    assert ("modulenotfounderror" in problems or "import error" in problems) and (
        "script" in problems or "scripts" in problems
    ), "Troubleshooting must cover ModuleNotFoundError/import errors when running scripts"
    assert "pytest" in problems and ("not found" in problems or "command not found" in problems or "path" in problems), (
        "Troubleshooting must cover pytest not found"
    )
    assert "port" in problems and ("use" in problems or "8000" in problems or "in use" in problems), (
        "Troubleshooting must cover port in use"
    )
    assert "venv" in problems and ("activation" in problems or "path" in problems or "activate" in problems), (
        "Troubleshooting must cover venv activation vs path"
    )


def test_setup_has_venv_path_note_for_scripts():
    """SETUP.md must recommend api/.venv/bin/python or .venv/bin/python for api/scripts/* (spec 031)."""
    content = _setup_content()
    assert "venv" in content and "script" in content.lower(), "SETUP.md must mention venv and scripts"
    has_unix_path = "api/.venv/bin/python" in content or ".venv/bin/python" in content
    assert has_unix_path, "SETUP.md must recommend api/.venv/bin/python or .venv/bin/python for scripts"
    # Windows equivalent if applicable
    has_windows_note = "windows" in content.lower() and ("Scripts" in content or "python.exe" in content)
    assert has_windows_note, "SETUP.md must note Windows equivalent (e.g. .venv\\Scripts\\python.exe) for scripts"


def test_troubleshooting_entries_actionable():
    """Troubleshooting entries must be specific and actionable (problem → fix) (spec 031)."""
    content = _setup_content()
    assert "## Troubleshooting" in content
    # Table or list with fix guidance
    assert "|" in content or "fix" in content.lower() or "use " in content or "run " in content, (
        "Troubleshooting must include actionable fixes (table or problem→fix)"
    )
