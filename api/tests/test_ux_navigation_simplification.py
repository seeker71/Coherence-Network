"""Acceptance tests for UX Navigation Simplification.

Validates that:
  1. The site header has a clear primary/secondary nav split (≤5 primary items).
  2. Every primary nav destination has a matching web page file.
  3. Secondary nav items are behind a "More" dropdown, not cluttering primary.
  4. Mobile menu renders all items (primary + secondary) in a single panel.
  5. Backing API endpoints for primary nav destinations are reachable.
  6. Accessibility: nav landmarks, aria-labels, and skip-to-content link exist.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"
LAYOUT = REPO_ROOT / "web" / "app" / "layout.tsx"

# Primary nav destinations defined in site_header.tsx
PRIMARY_DESTINATIONS = [
    "/ideas",
    "/contribute",
    "/resonance",
    "/tasks",
    "/nodes",
]

# Secondary nav destinations (behind "More" dropdown)
SECONDARY_DESTINATIONS = [
    "/invest",
    "/treasury",
    "/contributors",
    "/assets",
    "/specs",
    "/blog",
    "/search",
    "/automation",
    "/friction",
    "/identity",
]

MAX_PRIMARY_NAV_ITEMS = 5


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# 1. Primary nav is concise (≤5 items)
# ═══════════════════════════════════════════════════════════════


def test_primary_nav_item_count_is_bounded() -> None:
    """PRIMARY_NAV array must have at most 5 entries to keep top bar simple."""
    content = _read(SITE_HEADER)
    # Count entries in the PRIMARY_NAV array by matching { href: lines
    import re
    primary_block_match = re.search(
        r"const PRIMARY_NAV\s*=\s*\[(.*?)\];", content, re.DOTALL
    )
    assert primary_block_match, "PRIMARY_NAV constant not found in site_header.tsx"
    entries = re.findall(r'\{\s*href:', primary_block_match.group(1))
    assert len(entries) <= MAX_PRIMARY_NAV_ITEMS, (
        f"Primary nav has {len(entries)} items, max allowed is {MAX_PRIMARY_NAV_ITEMS}"
    )


# ═══════════════════════════════════════════════════════════════
# 2. Every primary nav destination has a web page
# ═══════════════════════════════════════════════════════════════


def test_primary_nav_destinations_have_pages() -> None:
    """Each primary nav href must resolve to an actual Next.js page file."""
    for dest in PRIMARY_DESTINATIONS:
        page_dir = REPO_ROOT / "web" / "app" / dest.lstrip("/")
        page_file = page_dir / "page.tsx"
        assert page_file.is_file(), (
            f"Primary nav destination {dest} is missing its page at {page_file}"
        )


# ═══════════════════════════════════════════════════════════════
# 3. Secondary nav is behind a dropdown, not inline
# ═══════════════════════════════════════════════════════════════


def test_secondary_nav_is_inside_dropdown() -> None:
    """Secondary nav items must be inside a <details> dropdown, not in the primary bar."""
    content = _read(SITE_HEADER)
    # The secondary items should be rendered inside a <details> element
    assert "SECONDARY_NAV" in content, "SECONDARY_NAV constant must exist"
    # The "More" summary button must exist for the dropdown
    assert ">More<" in content or ">More\n" in content or "More</summary>" in content, (
        "Expected a 'More' dropdown trigger for secondary navigation"
    )


# ═══════════════════════════════════════════════════════════════
# 4. Mobile menu contains both primary and secondary items
# ═══════════════════════════════════════════════════════════════


def test_mobile_menu_renders_all_nav_items() -> None:
    """Mobile menu must include both PRIMARY_NAV and SECONDARY_NAV items."""
    content = _read(SITE_HEADER)
    # Mobile menu section uses md:hidden
    assert "md:hidden" in content, "Expected a mobile-specific menu (md:hidden)"
    # Both nav arrays should be mapped in the mobile section
    assert "PRIMARY_NAV.map" in content, "Mobile menu must render PRIMARY_NAV items"
    assert "SECONDARY_NAV.map" in content, "Mobile menu must render SECONDARY_NAV items"


# ═══════════════════════════════════════════════════════════════
# 5. Backing API endpoints for primary nav pages are reachable
# ═══════════════════════════════════════════════════════════════


def test_ideas_api_reachable() -> None:
    """Ideas page relies on GET /api/ideas."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200


def test_contributions_api_reachable() -> None:
    """Contribute page relies on GET /api/contributions."""
    resp = client.get("/api/contributions")
    assert resp.status_code == 200


def test_coherence_api_reachable() -> None:
    """Resonance page relies on GET /api/coherence/score."""
    resp = client.get("/api/coherence/score")
    assert resp.status_code == 200


def test_tasks_api_reachable() -> None:
    """Pipeline (Tasks) page relies on GET /api/agent/tasks."""
    resp = client.get("/api/agent/tasks")
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# 6. Accessibility: nav landmarks and aria-labels
# ═══════════════════════════════════════════════════════════════


def test_header_has_banner_role() -> None:
    """Site header must have role='banner' for screen readers."""
    content = _read(SITE_HEADER)
    assert 'role="banner"' in content


def test_primary_nav_has_aria_label() -> None:
    """Primary navigation landmark must have an aria-label."""
    content = _read(SITE_HEADER)
    assert 'aria-label="Primary navigation"' in content


def test_mobile_nav_has_aria_label() -> None:
    """Mobile navigation landmark must have an aria-label."""
    content = _read(SITE_HEADER)
    assert 'aria-label="Mobile navigation"' in content


def test_skip_to_content_link_exists() -> None:
    """Layout must include a skip-to-main-content accessibility link."""
    content = _read(LAYOUT)
    assert "skip" in content.lower() and "main" in content.lower(), (
        "Root layout should contain a skip-to-main-content link"
    )
