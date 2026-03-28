"""Acceptance tests for Resonance Navigation (resonance-navigation).

Validates global navigation surfaces that route users to the live resonance feed
(`/resonance`): primary nav entries, heartbeat-styled emphasis link, mobile
parity, active-route helper behavior, and the backing API contract used by the
resonance page loader.

Source of truth: `web/components/site_header.tsx`, `web/components/active_nav_link.tsx`,
`web/app/layout.tsx`, `web/app/resonance/page.tsx`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"
ACTIVE_NAV = REPO_ROOT / "web" / "components" / "active_nav_link.tsx"
LAYOUT = REPO_ROOT / "web" / "app" / "layout.tsx"
RESONANCE_PAGE = REPO_ROOT / "web" / "app" / "resonance" / "page.tsx"


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


def test_site_header_primary_nav_lists_resonance_as_core_route() -> None:
    """Primary navigation exposes Resonance among the five always-visible actions."""
    src = _read(SITE_HEADER)
    assert '{ href: "/resonance", label: "Resonance" }' in src
    assert "PRIMARY_NAV" in src
    assert 'aria-label="Primary navigation"' in src


def test_site_header_includes_heartbeat_resonance_link() -> None:
    """Heartbeat nav targets the resonance feed and is wired with isHeartbeat styling."""
    src = _read(SITE_HEADER)
    assert "HEARTBEAT_NAV" in src
    assert '{ href: "/resonance", label: "Resonance" }' in src
    assert "isHeartbeat" in src
    assert 'href={HEARTBEAT_NAV.href}' in src


def test_active_nav_link_supports_pulse_heartbeat_variant() -> None:
    """Resonance heartbeat uses pulsing dot + active path detection."""
    src = _read(ACTIVE_NAV)
    assert "isHeartbeat" in src
    assert "animate-ping" in src
    assert "usePathname" in src


def test_root_layout_mounts_site_header_globally() -> None:
    """Every page inherits the header so resonance links are always discoverable."""
    src = _read(LAYOUT)
    assert 'import SiteHeader from "@/components/site_header"' in src
    assert "<SiteHeader" in src


def test_resonance_route_page_metadata_and_api_usage() -> None:
    """`/resonance` page documents title and loads the resonance JSON feed."""
    src = _read(RESONANCE_PAGE)
    assert 'title: "Resonance"' in src
    assert "/api/ideas/resonance" in src
    assert "window_hours" in src


def test_mobile_menu_includes_resonance_and_heartbeat_row() -> None:
    """Mobile drawer lists primary routes plus the highlighted Resonance row."""
    src = _read(SITE_HEADER)
    assert 'aria-label="Mobile navigation"' in src
    assert "md:hidden" in src
    assert "PRIMARY_NAV.map" in src
    assert "HEARTBEAT_NAV" in src


def test_ideas_resonance_api_ok_for_navigation_destination() -> None:
    """Backing feed returns 200 so the navigation destination does not hard-fail."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=30")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
