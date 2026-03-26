"""Contract tests for spec 156 — Web Ecosystem Links Surface (`ux-web-ecosystem-links`).

Verifies acceptance criteria via static analysis of the spec document and (when present)
the web implementation files listed in specs/156-ux-web-ecosystem-links.md.

Tests define the contract: do not modify these to make implementation pass.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent

_SPEC = _repo_root / "specs" / "156-ux-web-ecosystem-links.md"
_ECOSYSTEM_LINKS_TS = _repo_root / "web" / "lib" / "ecosystem-links.ts"
_ECOSYSTEM_PAGE = _repo_root / "web" / "app" / "ecosystem" / "page.tsx"
_SITE_FOOTER = _repo_root / "web" / "components" / "site-footer.tsx"
_LAYOUT = _repo_root / "web" / "app" / "layout.tsx"
_VITEST = _repo_root / "web" / "tests" / "integration" / "ecosystem-links.test.tsx"


def _spec_text() -> str:
    assert _SPEC.exists(), "specs/156-ux-web-ecosystem-links.md must exist"
    return _SPEC.read_text(encoding="utf-8")


def _require_implementation_files() -> None:
    missing = [p for p in (_ECOSYSTEM_LINKS_TS, _ECOSYSTEM_PAGE, _SITE_FOOTER) if not p.exists()]
    if missing:
        pytest.skip(
            "spec 156 web implementation files not present: "
            + ", ".join(str(p.relative_to(_repo_root)) for p in missing)
        )


# --- Spec document (always-on) ---


def test_spec_156_file_exists():
    """Spec file for ux-web-ecosystem-links must exist (spec 156)."""
    assert _SPEC.is_file()


def test_spec_156_documents_requirements_r1_through_r7():
    """Spec must enumerate R1–R7 for traceability (spec 156)."""
    content = _spec_text()
    for n in range(1, 8):
        assert f"R{n}:" in content, f"spec 156 must include requirement R{n}"


def test_spec_156_no_new_backend_endpoints():
    """R7 and task card forbid new backend endpoints (spec 156)."""
    content = _spec_text()
    assert "R7:" in content and "static" in content.lower()
    assert "No API changes" in content or "no new backend" in content.lower()


def test_spec_156_lists_acceptance_test_names():
    """Acceptance Tests section must name the four Vitest cases (spec 156)."""
    content = _spec_text()
    assert "## Acceptance Tests" in content
    for name in (
        "renders_all_required_ecosystem_rows",
        "ecosystem_entry_point_visible_in_footer",
        "external_links_use_safe_target_and_rel",
        "unavailable_link_row_is_rendered_with_non_clickable_state",
    ):
        assert name in content, f"spec 156 acceptance tests must reference {name}"


def test_spec_156_verification_lists_vitest_and_build():
    """Verification block must include Vitest and web build (spec 156)."""
    content = _spec_text()
    assert "npx vitest run tests/integration/ecosystem-links.test.tsx" in content
    assert "npm run build" in content


def test_spec_156_data_model_lists_ecosystem_link_fields():
    """Data model section must describe EcosystemLink fields (spec 156)."""
    content = _spec_text()
    assert "EcosystemLink:" in content
    for key in ("id", "name", "purpose", "url", "type", "status"):
        assert key in content, f"spec 156 data model should mention {key}"


# --- Implementation (skipped until web files exist) ---


def test_ecosystem_links_ts_exports_canonical_config():
    """web/lib/ecosystem-links.ts must export a typed list of destinations (spec 156)."""
    _require_implementation_files()
    text = _ECOSYSTEM_LINKS_TS.read_text(encoding="utf-8")
    assert "export" in text
    assert "ECOSYSTEM" in text or "ecosystem" in text.lower()


def test_ecosystem_links_ts_unique_ids():
    """Duplicate link ids must be detectable; all ids unique (spec 156 edge case)."""
    _require_implementation_files()
    text = _ECOSYSTEM_LINKS_TS.read_text(encoding="utf-8")
    ids = re.findall(r'\bid\s*:\s*["\']([^"\']+)["\']', text)
    assert ids, "ecosystem-links.ts must define id fields"
    assert len(ids) == len(set(ids)), f"duplicate ecosystem link ids: {ids}"


def test_ecosystem_links_ts_covers_required_destinations():
    """Config must cover GitHub, npm, CLI, API docs, and OpenClaw (spec R2, Expected UI)."""
    _require_implementation_files()
    text = _ECOSYSTEM_LINKS_TS.read_text(encoding="utf-8").lower()
    assert "github" in text
    assert "npm" in text
    assert "cli" in text
    assert "api" in text and ("doc" in text or "docs" in text)
    assert "openclaw" in text


def test_ecosystem_links_ts_includes_typed_metadata_fields():
    """Each entry must be representable with name, purpose, url, type (spec R3)."""
    _require_implementation_files()
    text = _ECOSYSTEM_LINKS_TS.read_text(encoding="utf-8")
    for field in ("name", "purpose", "type"):
        assert field in text, f"ecosystem-links.ts should include {field}"
    assert "url" in text


def test_ecosystem_page_renders_safe_external_links():
    """Available links use target _blank and noreferrer noopener (spec R4)."""
    _require_implementation_files()
    text = _ECOSYSTEM_PAGE.read_text(encoding="utf-8")
    assert 'target="_blank"' in text or "target='_blank'" in text or 'target={"_blank"}' in text
    assert "noopener" in text and "noreferrer" in text


def test_ecosystem_page_unavailable_row_copy():
    """Unavailable rows show status and helper copy (spec Expected UI #3)."""
    _require_implementation_files()
    text = _ECOSYSTEM_PAGE.read_text(encoding="utf-8")
    assert "Unavailable" in text
    assert "Link not configured yet" in text


def test_ecosystem_page_includes_contributor_guidance():
    """R6: lightweight guidance for build / integrate / contribute / agents."""
    _require_implementation_files()
    text = _ECOSYSTEM_PAGE.read_text(encoding="utf-8").lower()
    assert "build" in text
    assert "integrate" in text
    assert "contribute" in text
    assert "agent" in text


def test_ecosystem_page_fallback_on_config_failure():
    """Edge case: fallback heading and retry guidance if config import fails (spec 156)."""
    _require_implementation_files()
    text = _ECOSYSTEM_PAGE.read_text(encoding="utf-8")
    assert "Ecosystem links temporarily unavailable" in text
    assert "Refresh" in text or "refresh" in text


def test_site_footer_has_ecosystem_entry_to_ecosystem_route():
    """R1: footer exposes Ecosystem entry navigating to /ecosystem."""
    _require_implementation_files()
    text = _SITE_FOOTER.read_text(encoding="utf-8")
    assert "Ecosystem" in text
    assert "/ecosystem" in text


def test_layout_includes_site_footer():
    """Footer must render from layout for global discoverability (spec files to modify)."""
    _require_implementation_files()
    text = _LAYOUT.read_text(encoding="utf-8")
    assert "site-footer" in text.lower() or "SiteFooter" in text


def test_vitest_integration_file_exists():
    """Spec lists web/tests/integration/ecosystem-links.test.tsx as acceptance harness."""
    _require_implementation_files()
    assert _VITEST.is_file(), "web/tests/integration/ecosystem-links.test.tsx must exist per spec 156"
