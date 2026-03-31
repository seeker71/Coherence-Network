"""Contract tests for spec 181 — Automation Garden Map (`automation-garden-map`).

Verifies the spec document and web implementation markers exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent

_SPEC = _repo_root / "specs" / "181-automation-garden-map.md"
_PAGE = _repo_root / "web" / "app" / "automation" / "page.tsx"
_GARDEN = _repo_root / "web" / "components" / "automation" / "automation_garden.tsx"
_DATA = _repo_root / "web" / "lib" / "automation-page-data.ts"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_spec_181_file_exists():
    """Spec file for automation garden map must exist (spec 181)."""
    assert _SPEC.is_file()


def test_spec_181_has_verification_scenarios():
    """Spec must include Verification Scenarios with concrete setup/action/expected language."""
    content = _read(_SPEC)
    assert "## Verification Scenarios" in content
    for label in ("Setup:", "Action:", "Expected:", "Edge:"):
        assert label in content, f"spec 181 should use {label} in scenarios"


def test_spec_181_lists_automation_endpoints():
    """Spec must name automation GET endpoints used by the page."""
    content = _read(_SPEC)
    assert "/api/automation/usage" in content
    assert "/api/automation/usage/readiness" in content


def test_automation_page_imports_garden_and_details():
    """Automation page must compose AutomationGarden and technical details."""
    assert _PAGE.is_file()
    text = _read(_PAGE)
    assert "AutomationGarden" in text
    assert "automation_garden" in text
    assert "automation-technical-soil" in text
    assert "loadAutomationData" in text


def test_automation_garden_has_gauge_and_stream_markers():
    """Garden component must retain accessibility and test hooks."""
    assert _GARDEN.is_file()
    text = _read(_GARDEN)
    assert "automation-garden" in text
    assert "garden-provider-plot" in text
    assert 'role="meter"' in text


def test_automation_page_data_exports_brook_builder():
    """Shared data module must export activity stream builder."""
    assert _DATA.is_file()
    text = _read(_DATA)
    assert "export function buildActivityBrookItems" in text
    assert "loadAutomationData" in text
