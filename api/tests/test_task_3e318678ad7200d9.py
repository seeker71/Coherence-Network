"""Contract tests for spec 156 (ux-web-ecosystem-links).

These tests verify acceptance criteria from the spec document and, when present,
validate the referenced web implementation files with static assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "specs" / "156-ux-web-ecosystem-links.md"

ECOSYSTEM_LINKS_PATH = REPO_ROOT / "web" / "lib" / "ecosystem-links.ts"
ECOSYSTEM_PAGE_PATH = REPO_ROOT / "web" / "app" / "ecosystem" / "page.tsx"
SITE_FOOTER_PATH = REPO_ROOT / "web" / "components" / "site-footer.tsx"
LAYOUT_PATH = REPO_ROOT / "web" / "app" / "layout.tsx"


def _read_spec() -> str:
    assert SPEC_PATH.exists(), "specs/156-ux-web-ecosystem-links.md must exist"
    return SPEC_PATH.read_text(encoding="utf-8")


def _require_ux_files() -> None:
    required = [ECOSYSTEM_LINKS_PATH, ECOSYSTEM_PAGE_PATH, SITE_FOOTER_PATH, LAYOUT_PATH]
    missing = [path for path in required if not path.exists()]
    if missing:
        missing_rel = ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing)
        pytest.skip(f"ux-web-ecosystem-links implementation files missing: {missing_rel}")


def test_spec_156_declares_r1_to_r7() -> None:
    """R1-R7 are required for traceable acceptance coverage."""
    spec = _read_spec()
    for req_id in range(1, 8):
        assert f"R{req_id}:" in spec


def test_spec_156_acceptance_tests_are_listed() -> None:
    """Spec must list all named acceptance tests."""
    spec = _read_spec()
    expected_tests = (
        "renders_all_required_ecosystem_rows",
        "ecosystem_entry_point_visible_in_footer",
        "external_links_use_safe_target_and_rel",
        "unavailable_link_row_is_rendered_with_non_clickable_state",
    )
    for test_name in expected_tests:
        assert test_name in spec


def test_spec_156_includes_required_destinations_and_metadata_fields() -> None:
    """R2/R3 destination and metadata contract must be explicit in the spec."""
    spec_lower = _read_spec().lower()
    for destination in ("github", "npm", "cli", "api docs", "openclaw"):
        assert destination in spec_lower
    for field in ("name", "purpose", "url", "type"):
        assert field in spec_lower


def test_spec_156_requires_safe_external_link_behavior_and_unavailable_state() -> None:
    """R4/R5 details must be documented as acceptance behavior."""
    spec = _read_spec()
    assert 'target="_blank"' in spec
    assert "noreferrer noopener" in spec
    assert "Unavailable" in spec
    assert "Link not configured yet" in spec


def test_spec_156_forbids_new_backend_endpoints() -> None:
    """R7 and task constraints require static web configuration only."""
    spec = _read_spec().lower()
    assert "no api changes" in spec or "no new backend endpoints" in spec
    assert "static web configuration" in spec or "static" in spec


def test_ux_files_include_ecosystem_entry_point_and_route() -> None:
    """R1: footer/layout should expose Ecosystem entry routing to /ecosystem."""
    _require_ux_files()
    footer_text = SITE_FOOTER_PATH.read_text(encoding="utf-8")
    layout_text = LAYOUT_PATH.read_text(encoding="utf-8")
    assert "Ecosystem" in footer_text
    assert "/ecosystem" in footer_text
    assert "SiteFooter" in layout_text or "site-footer" in layout_text.lower()


def test_ux_page_external_links_and_guidance_copy() -> None:
    """R4/R6: ecosystem page should include safe external link attrs and guidance."""
    _require_ux_files()
    page_text = ECOSYSTEM_PAGE_PATH.read_text(encoding="utf-8")
    page_lower = page_text.lower()
    assert 'target="_blank"' in page_text or "target='_blank'" in page_text
    assert "noopener" in page_lower and "noreferrer" in page_lower
    for keyword in ("build", "integrate", "contribute", "agent"):
        assert keyword in page_lower


def test_ux_config_has_required_destinations_and_unique_ids() -> None:
    """R2/R3: canonical config should include required rows with unique ids."""
    _require_ux_files()
    text = ECOSYSTEM_LINKS_PATH.read_text(encoding="utf-8")
    text_lower = text.lower()
    for destination in ("github", "npm", "cli", "api", "openclaw"):
        assert destination in text_lower

    # Keep id uniqueness check lightweight and language-agnostic.
    ids = []
    for line in text.splitlines():
        normalized = line.strip().replace(" ", "")
        if normalized.startswith("id:") and ("\"" in normalized or "'" in normalized):
            value = normalized.split(":", 1)[1].strip().strip(",")
            ids.append(value.strip("'\""))
    assert ids, "ecosystem-links config should declare id fields"
    assert len(ids) == len(set(ids)), f"duplicate ids found: {ids}"
