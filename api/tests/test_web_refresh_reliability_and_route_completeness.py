"""Executable checks for spec 092 — Web refresh reliability and route completeness.

See specs/092-web-refresh-reliability-and-route-completeness.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SITE_HEADER = _REPO_ROOT / "web" / "components" / "site_header.tsx"
_LIVE_UPDATES = _REPO_ROOT / "web" / "components" / "live_updates_controller.tsx"
_PAGE_CONTEXT = _REPO_ROOT / "web" / "components" / "page_context_links.tsx"
_PAGES = [
    _REPO_ROOT / "web" / "app" / "friction" / "page.tsx",
    _REPO_ROOT / "web" / "app" / "gates" / "page.tsx",
    _REPO_ROOT / "web" / "app" / "search" / "page.tsx",
    _REPO_ROOT / "web" / "app" / "project" / "[ecosystem]" / "[name]" / "page.tsx",
]


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.skip(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def test_site_header_includes_key_routes() -> None:
    """Acceptance: global navigation includes /friction, /import, /api-health."""
    text = _read(_SITE_HEADER)
    for href in ('href: "/friction"', 'href: "/import"', 'href: "/api-health"'):
        assert href in text, f"Expected {href} in site_header"


def test_page_context_shared_band_includes_key_routes() -> None:
    """Acceptance: context-link band exposes friction, import, api-health."""
    text = _read(_PAGE_CONTEXT)
    for href in ('href: "/friction"', 'href: "/import"', 'href: "/api-health"'):
        assert href in text, f"Expected {href} in page_context_links SHARED_RELATED"


def test_live_updates_controller_mount_and_focus_behavior() -> None:
    """Acceptance: immediate tick on mount; focus/visibility hooks; version + no-store fetches."""
    text = _read(_LIVE_UPDATES)
    assert "void checkWebVersion();" in text
    assert "void runTick();" in text
    assert 'fetch("/api/web-version", { cache: "no-store" })' in text
    assert 'fetch("/api/runtime/change-token", { cache: "no-store" })' in text
    assert 'window.addEventListener("focus"' in text
    assert 'document.addEventListener("visibilitychange"' in text


def test_interactive_pages_use_no_store_for_data_reads() -> None:
    """Acceptance: listed pages use cache: no-store for fetches."""
    for path in _PAGES:
        text = _read(path)
        assert 'cache: "no-store"' in text or "cache: 'no-store'" in text, f"Expected no-store fetch in {path}"


def test_live_updates_version_reload_guard() -> None:
    """Web version change triggers reload when baseline already set."""
    text = _read(_LIVE_UPDATES)
    assert "window.location.reload()" in text
    assert "webVersionRef" in text
