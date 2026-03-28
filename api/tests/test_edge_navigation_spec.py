"""Contract tests for Edge Navigation (`edge-navigation`).

Traces acceptance criteria to Spec 161 (Node and Task Visibility) — especially **R3.9**
and **Scenario 5 — Navigation and discoverability** — plus baseline accessibility for
the sticky header (top-edge global navigation): skip link, landmarks, and consistent
primary/secondary structure.

Implementation sources (static analysis only; no mocks):
- `specs/161-node-task-visibility.md`
- `web/components/site_header.tsx`
- `web/components/active_nav_link.tsx`
- `web/app/layout.tsx`
- `web/app/pipeline/page.tsx`
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent

_SPEC_161 = _repo_root / "specs" / "161-node-task-visibility.md"
_SITE_HEADER = _repo_root / "web" / "components" / "site_header.tsx"
_ACTIVE_NAV = _repo_root / "web" / "components" / "active_nav_link.tsx"
_LAYOUT = _repo_root / "web" / "app" / "layout.tsx"
_PIPELINE_PAGE = _repo_root / "web" / "app" / "pipeline" / "page.tsx"


def _read(p: Path) -> str:
    assert p.is_file(), f"required file missing: {p.relative_to(_repo_root)}"
    return p.read_text(encoding="utf-8")


# --- Spec 161 (document contract) ---


def test_spec_161_exists():
    """Spec 161 must be present (source of navigation requirements)."""
    assert _SPEC_161.is_file()


def test_spec_161_r39_requires_pipeline_in_web_navigation():
    """R3.9: Add `/pipeline` to the web navigation (spec 161)."""
    text = _read(_SPEC_161)
    assert "R3.9" in text
    assert "/pipeline" in text.lower() or "`/pipeline`" in text
    assert "nav" in text.lower()


def test_spec_161_scenario_5_mentions_pipeline_link_and_tasks():
    """Scenario 5: Pipeline link, /pipeline route, /tasks still works (spec 161)."""
    text = _read(_SPEC_161)
    assert "Scenario 5" in text or "Navigation and discoverability" in text
    assert "Pipeline" in text
    assert "/tasks" in text or "tasks" in text.lower()


# --- Sticky header (edge) global navigation ---


def test_site_header_defines_primary_nav_with_pipeline():
    """Primary nav must expose Pipeline at `/pipeline` (spec 161 R3.9, Scenario 5)."""
    text = _read(_SITE_HEADER)
    assert "PRIMARY_NAV" in text
    assert 'href: "/pipeline"' in text or "href: '/pipeline'" in text
    assert "Pipeline" in text


def test_site_header_sticky_top_edge_semantics():
    """Header stays at the top viewport edge (sticky) for persistent navigation."""
    text = _read(_SITE_HEADER)
    assert "sticky" in text and "top-0" in text
    assert 'role="banner"' in text or "role='banner'" in text


def test_site_header_primary_nav_has_accessible_name():
    """Desktop primary `<nav>` exposes an accessible name (WCAG landmark)."""
    text = _read(_SITE_HEADER)
    assert 'aria-label="Primary navigation"' in text


def test_site_header_mobile_menu_includes_pipeline_and_tasks():
    """Mobile menu repeats primary routes and secondary links (Scenario 5 mobile usability)."""
    text = _read(_SITE_HEADER)
    assert "md:hidden" in text
    assert "PRIMARY_NAV.map" in text
    assert "SECONDARY_NAV.map" in text
    assert "/pipeline" in text
    assert "/tasks" in text


def test_site_header_secondary_nav_includes_tasks_work_cards():
    """Edge case: `/tasks` remains reachable (Work Cards) while Pipeline is primary."""
    text = _read(_SITE_HEADER)
    assert 'href: "/tasks"' in text or 'href: "/tasks",' in text
    assert "Work Cards" in text


def test_active_nav_link_supports_current_route_highlighting():
    """Active route highlighting uses pathname prefix/suffix rules for edge nav clarity."""
    text = _read(_ACTIVE_NAV)
    assert "usePathname" in text
    assert "pathname" in text
    assert "isActive" in text


def test_layout_skip_link_targets_main_content():
    """Skip link lets keyboard users bypass the edge header to `#main-content`."""
    text = _read(_LAYOUT)
    assert '#main-content' in text or "#main-content" in text
    assert "Skip to main content" in text
    assert 'id="main-content"' in text


def test_pipeline_route_page_exists_for_direct_navigation():
    """Direct navigation to `/pipeline` is backed by a page module (Scenario 5 edge case)."""
    assert _PIPELINE_PAGE.is_file()
    body = _read(_PIPELINE_PAGE)
    assert "use client" in body[:80].lower() or '"use client"' in body[:120]


def test_pipeline_page_imports_link_for_internal_navigation():
    """Pipeline dashboard should support in-app navigation (Next.js Link)."""
    body = _read(_PIPELINE_PAGE)
    assert "from \"next/link\"" in body or "from 'next/link'" in body


def test_site_header_brand_links_to_home():
    """Brand control navigates to `/` (consistent entry point from every page)."""
    text = _read(_SITE_HEADER)
    assert 'href="/"' in text
    assert "Coherence Network" in text


def test_more_dropdown_exposes_api_docs_external_pattern():
    """Secondary edge affordance: API docs open in a new tab with noopener."""
    text = _read(_SITE_HEADER)
    assert "/docs" in text
    assert "noopener" in text and "noreferrer" in text
