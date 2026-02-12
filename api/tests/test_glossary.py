"""Tests for docs/GLOSSARY.md contract — spec 035 (Project Terms).

Tests define the contract: do not modify these to make implementation pass.
"""

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_glossary_md = _repo_root / "docs" / "GLOSSARY.md"

# Required terms per spec 035; headings may vary (e.g. "Task type" vs "task_type")
REQUIRED_TERMS = [
    "Backlog",
    "Coherence",
    "Pipeline",
    "Task type",   # or task_type
    "Direction",
    "needs_decision",
    "Agent runner",
    "Project manager",
    "Holdout tests",
    "Spec-driven",
]


def _glossary_content() -> str:
    if not _glossary_md.exists():
        pytest.skip("docs/GLOSSARY.md not in repo")
    return _glossary_md.read_text()


def test_glossary_md_exists():
    """docs/GLOSSARY.md must exist (spec 035)."""
    assert _glossary_md.exists(), "docs/GLOSSARY.md must exist"


def test_glossary_has_table_format():
    """GLOSSARY.md must use table or equivalent (Term | Definition) (spec 035)."""
    content = _glossary_content()
    # Table header: | Term | Definition | or similar
    assert "|" in content, "GLOSSARY.md must contain a table (|)"
    assert "Term" in content and "Definition" in content, (
        "GLOSSARY.md must have Term and Definition columns"
    )


def test_glossary_defines_all_required_terms():
    """GLOSSARY.md must define: Backlog, Coherence, Pipeline, Task type, Direction, needs_decision, Agent runner, Project manager, Holdout tests, Spec-driven (spec 035)."""
    content = _glossary_content()
    missing = []
    for term in REQUIRED_TERMS:
        # Allow "Task type" or "task_type" etc.
        if term == "Task type":
            if "Task type" not in content and "task_type" not in content:
                missing.append(term)
        elif term not in content:
            missing.append(term)
    assert not missing, f"GLOSSARY.md must define: {missing}"


def test_glossary_definitions_non_empty():
    """Each required term must have a non-trivial definition (spec 035)."""
    content = _glossary_content()
    lines = content.splitlines()
    for term in REQUIRED_TERMS:
        # Accept "Task type" or "task_type" in table (spec 035)
        search_alternatives = ["task_type", "Task type"] if term == "Task type" else [term]
        found = False
        for line in lines:
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 2:
                continue
            first_col = parts[0].replace("**", "").strip()
            if any(s in first_col or s.lower() in first_col.lower() for s in search_alternatives):
                definition = parts[1].replace("**", "").strip()
                assert len(definition) >= 20, (
                    f"Term {term!r} must have a definition of at least 20 characters; got {definition!r}"
                )
                found = True
                break
        assert found, f"Term {term!r} not found in table form in GLOSSARY.md"


def test_glossary_coherence_score_range():
    """Coherence definition must mention 0.0–1.0 (or equivalent) (spec 035)."""
    content = _glossary_content()
    assert "Coherence" in content
    # Definition should state score range
    assert ("0.0" in content and "1.0" in content) or "0.0–1.0" in content or "0-1" in content, (
        "Coherence definition must mention score range (e.g. 0.0–1.0)"
    )


def test_glossary_task_type_values():
    """Task type definition must mention allowed values: spec, test, impl, review, heal (spec 035)."""
    content = _glossary_content()
    required_values = ["spec", "test", "impl", "review", "heal"]
    for val in required_values:
        assert val in content, f"Task type definition must mention allowed value {val!r}"
