"""Acceptance tests for Automation Page Clarity (`automation-page-clarity`).

Statically analyzes `web/app/automation/page.tsx` for user-facing clarity:
plain-language framing, predictable API wiring via `getApiBase()`, discoverable
sections, and a compact \"where to go next\" navigation.

If `specs/157-automation-page-clarity.md` is added to the repo, extend this suite
with spec-document assertions (see `test_ux_web_ecosystem_links_spec.py`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_PAGE = REPO_ROOT / "web" / "app" / "automation" / "page.tsx"
_OPTIONAL_SPEC = REPO_ROOT / "specs" / "157-automation-page-clarity.md"


def _page_source() -> str:
    assert AUTOMATION_PAGE.is_file(), f"Missing automation page: {AUTOMATION_PAGE}"
    return AUTOMATION_PAGE.read_text(encoding="utf-8")


def test_automation_page_source_exists() -> None:
    """Automation route implementation must exist."""
    assert AUTOMATION_PAGE.is_file()


def test_automation_page_metadata_clarifies_purpose() -> None:
    """Title and description orient visitors before they scan metrics."""
    src = _page_source()
    assert 'title: "Automation"' in src
    assert "description:" in src
    assert "readiness" in src.lower() or "subscription" in src.lower() or "automation" in src.lower()


def test_automation_page_single_h1_and_intro() -> None:
    """One primary heading plus a short plain-language summary (scanability)."""
    src = _page_source()
    assert src.count("<h1") == 1
    assert "Automation Capacity" in src
    assert "live view" in src.lower() or "provider" in src.lower()


def test_automation_page_uses_get_api_base_for_all_fetches() -> None:
    """API URL resolution goes through `getApiBase()` (single source of truth)."""
    src = _page_source()
    assert 'const api = getApiBase()' in src
    # No direct origin literals inside fetch() templates for the API surface.
    assert re.search(r'fetch\s*\(\s*[`"\'](?:https?://)', src) is None


def test_automation_page_wires_core_automation_endpoints() -> None:
    """Primary dashboard calls match the automation usage/readiness contract surface."""
    src = _page_source()
    assert "`${api}/api/automation/usage" in src or "${api}/api/automation/usage" in src
    assert "/api/automation/usage/alerts" in src
    assert "/api/automation/usage/readiness" in src
    assert "/api/automation/usage/provider-validation" in src
    assert "/api/providers/stats" in src
    assert "/api/federation/nodes/stats" in src


def test_automation_page_major_sections_have_h2_headings() -> None:
    """Major blocks are labeled for quick orientation (not a wall of anonymous cards)."""
    src = _page_source()
    for title in (
        "Provider Validation Contract",
        "Provider Execution Stats",
        "Provider Readiness",
        "Provider Usage",
        "Capacity Alerts",
    ):
        assert f'<h2 className="text-xl font-semibold">{title}</h2>' in src


def test_automation_page_federation_sections_when_present_are_labeled() -> None:
    """Optional federation blocks keep explicit section titles."""
    src = _page_source()
    assert "Federation Network — Provider Stats by Node" in src
    assert "Federation Node Capability Discovery" in src


def test_automation_page_where_to_go_next_navigation() -> None:
    """End-of-page navigation uses plain label + related destinations (progressive disclosure)."""
    src = _page_source()
    assert 'aria-label="Where to go next"' in src
    assert "Where to go next" in src
    assert 'href="/usage"' in src
    assert 'href="/flow"' in src
    assert 'href="/specs"' in src


def test_automation_page_avoids_placeholder_copy() -> None:
    """No lorem / TODO stubs in user-visible copy."""
    src = _page_source()
    lowered = src.lower()
    assert "lorem" not in lowered
    assert "todo" not in lowered


def test_optional_spec_157_when_present_lists_requirements() -> None:
    """When spec 157 lands, it should remain traceable (optional — skip if absent)."""
    if not _OPTIONAL_SPEC.is_file():
        pytest.skip("specs/157-automation-page-clarity.md not present in this worktree")
    text = _OPTIONAL_SPEC.read_text(encoding="utf-8")
    assert "## Requirements" in text or "## Purpose" in text
    assert "automation" in text.lower()
