"""Tests for Spec 165: UX Homepage Readability — Dark Mode Contrast & Light Mode Toggle.

Verifies:
- CSS token values for both dark and light mode (globals.css)
- ThemeProvider and ThemeToggle components exist with required structure
- layout.tsx integrates ThemeProvider and SSR-safe inline script
- site_header.tsx includes ThemeToggle
- API endpoints consumed by the homepage remain healthy
- Opacity floor enforcement (no prose below /85 in page.tsx)
- idea_submit_form.tsx meets opacity requirements
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
GLOBALS_CSS = REPO_ROOT / "web" / "app" / "globals.css"
PAGE_TSX = REPO_ROOT / "web" / "app" / "page.tsx"
LAYOUT_TSX = REPO_ROOT / "web" / "app" / "layout.tsx"
THEME_PROVIDER = REPO_ROOT / "web" / "components" / "theme-provider.tsx"
THEME_TOGGLE = REPO_ROOT / "web" / "components" / "theme-toggle.tsx"
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"
IDEA_SUBMIT_FORM = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"


# ---------------------------------------------------------------------------
# API contract tests — homepage stat sources
# ---------------------------------------------------------------------------


def test_coherence_score_endpoint_shape() -> None:
    """GET /api/coherence/score returns a valid score payload."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= data["score"] <= 1.0


def test_ideas_list_endpoint_accessible() -> None:
    """GET /api/ideas is accessible and returns expected keys."""
    response = client.get("/api/ideas")
    assert response.status_code == 200
    payload = response.json()
    assert "ideas" in payload


def test_resonance_endpoint_valid_params() -> None:
    """GET /api/ideas/resonance with valid params returns 200."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200


def test_federation_nodes_endpoint_accessible() -> None:
    """GET /api/federation/nodes is accessible."""
    response = client.get("/api/federation/nodes")
    assert response.status_code in (200, 404)  # 404 acceptable if no nodes seeded


# ---------------------------------------------------------------------------
# CSS token tests — dark mode (spec ux-homepage-readability)
# ---------------------------------------------------------------------------


def test_css_dark_mode_foreground_token() -> None:
    """Dark mode --foreground token must be 38 32% 93% (high-lightness warm white)."""
    assert GLOBALS_CSS.is_file(), f"Missing {GLOBALS_CSS}"
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css


def test_css_dark_mode_muted_foreground_token() -> None:
    """Dark mode --muted-foreground must be 34 22% 90% (near-white warm grey)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--muted-foreground: 34 22% 90%" in css


def test_css_hero_headline_class_present() -> None:
    """.hero-headline class must exist with color: hsl(var(--foreground))."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert ".hero-headline" in css
    # The rule must assign foreground color
    hero_block_match = re.search(r"\.hero-headline\s*\{([^}]+)\}", css, re.DOTALL)
    assert hero_block_match is not None, ".hero-headline rule body not found"
    rule_body = hero_block_match.group(1)
    assert "hsl(var(--foreground))" in rule_body


def test_css_bloom_overlay_softened() -> None:
    """body::before bloom first stop must use hsl(28 92% 74% / 0.05) — softened."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "hsl(28 92% 74% / 0.05)" in css


# ---------------------------------------------------------------------------
# CSS token tests — light mode (spec 165)
# ---------------------------------------------------------------------------


def test_css_light_mode_block_exists() -> None:
    """:root.light block must be present in globals.css."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert ":root.light" in css


def test_css_light_mode_background_token() -> None:
    """Light mode --background must be 42 40% 96% (warm off-white)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--background: 42 40% 96%" in css


def test_css_light_mode_foreground_token() -> None:
    """Light mode --foreground must be 24 28% 14% (deep warm near-black)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--foreground: 24 28% 14%" in css


def test_css_light_mode_muted_foreground_token() -> None:
    """Light mode --muted-foreground must be 28 18% 38% (AA-compliant warm grey)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--muted-foreground: 28 18% 38%" in css


def test_css_light_mode_primary_token() -> None:
    """Light mode --primary must be 36 72% 42% (darker gold for AA on light bg)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--primary: 36 72% 42%" in css


def test_css_light_mode_color_scheme() -> None:
    """Light mode block must set color-scheme: light (not dark)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    light_block = re.search(r":root\.light\s*\{([^}]+)\}", css, re.DOTALL)
    assert light_block is not None
    assert "color-scheme: light" in light_block.group(1)


# ---------------------------------------------------------------------------
# page.tsx — hero class and opacity floor
# ---------------------------------------------------------------------------


def test_page_uses_hero_headline_class() -> None:
    """<h1> in page.tsx must use the hero-headline CSS class."""
    assert PAGE_TSX.is_file(), f"Missing {PAGE_TSX}"
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "hero-headline" in content


def test_page_uses_foreground_90() -> None:
    """page.tsx must contain at least one text-foreground/90 usage."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "text-foreground/90" in content


def test_page_opacity_floor_no_violations() -> None:
    """All text-foreground/<N> values in page.tsx must be >= 85."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    for match in re.findall(r"text-foreground/(\d+)", content):
        assert int(match) >= 85, (
            f"text-foreground/{match} found in page.tsx — minimum allowed is /85"
        )


# ---------------------------------------------------------------------------
# idea_submit_form.tsx — opacity requirements
# ---------------------------------------------------------------------------


def test_idea_submit_form_placeholder_opacity() -> None:
    """Textarea and input must use placeholder:text-foreground/85."""
    assert IDEA_SUBMIT_FORM.is_file(), f"Missing {IDEA_SUBMIT_FORM}"
    content = IDEA_SUBMIT_FORM.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in content


def test_idea_submit_form_body_text_opacity() -> None:
    """Form body text must use text-foreground/90."""
    content = IDEA_SUBMIT_FORM.read_text(encoding="utf-8")
    assert "text-foreground/90" in content


def test_idea_submit_form_no_low_opacity() -> None:
    """idea_submit_form.tsx must not use text-foreground/70."""
    content = IDEA_SUBMIT_FORM.read_text(encoding="utf-8")
    assert "text-foreground/70" not in content


# ---------------------------------------------------------------------------
# ThemeProvider component (spec 165)
# ---------------------------------------------------------------------------


def test_theme_provider_file_exists() -> None:
    """ThemeProvider component file must exist."""
    assert THEME_PROVIDER.is_file(), f"Missing {THEME_PROVIDER}"


def test_theme_provider_exports_use_client() -> None:
    """ThemeProvider must be a client component."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert '"use client"' in content or "'use client'" in content


def test_theme_provider_exports_theme_provider() -> None:
    """ThemeProvider must export ThemeProvider function."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "export function ThemeProvider" in content


def test_theme_provider_exports_use_theme() -> None:
    """ThemeProvider must export useTheme hook."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "export function useTheme" in content


def test_theme_provider_uses_local_storage() -> None:
    """ThemeProvider must persist theme to localStorage."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "localStorage" in content


def test_theme_provider_handles_system_preference() -> None:
    """ThemeProvider must respect system prefers-color-scheme."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "prefers-color-scheme" in content


def test_theme_provider_storage_key() -> None:
    """ThemeProvider must use 'coherence-theme' as the localStorage key."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "coherence-theme" in content


def test_theme_provider_toggle_theme() -> None:
    """ThemeProvider must export a toggleTheme function."""
    content = THEME_PROVIDER.read_text(encoding="utf-8")
    assert "toggleTheme" in content


# ---------------------------------------------------------------------------
# ThemeToggle component (spec 165)
# ---------------------------------------------------------------------------


def test_theme_toggle_file_exists() -> None:
    """ThemeToggle component file must exist."""
    assert THEME_TOGGLE.is_file(), f"Missing {THEME_TOGGLE}"


def test_theme_toggle_is_client_component() -> None:
    """ThemeToggle must be a client component."""
    content = THEME_TOGGLE.read_text(encoding="utf-8")
    assert '"use client"' in content or "'use client'" in content


def test_theme_toggle_exports_theme_toggle() -> None:
    """ThemeToggle must export ThemeToggle function."""
    content = THEME_TOGGLE.read_text(encoding="utf-8")
    assert "export function ThemeToggle" in content


def test_theme_toggle_has_aria_label() -> None:
    """ThemeToggle button must have an aria-label for accessibility."""
    content = THEME_TOGGLE.read_text(encoding="utf-8")
    assert "aria-label" in content


def test_theme_toggle_has_focus_styles() -> None:
    """ThemeToggle must have focus ring styles for keyboard accessibility."""
    content = THEME_TOGGLE.read_text(encoding="utf-8")
    assert "focus:" in content


def test_theme_toggle_has_sun_and_moon_icons() -> None:
    """ThemeToggle must render both sun and moon SVG icons."""
    content = THEME_TOGGLE.read_text(encoding="utf-8")
    # Both icons are SVGs with aria-hidden
    assert content.count("aria-hidden") >= 2


# ---------------------------------------------------------------------------
# layout.tsx — ThemeProvider integration + SSR-safe inline script
# ---------------------------------------------------------------------------


def test_layout_imports_theme_provider() -> None:
    """layout.tsx must import ThemeProvider."""
    assert LAYOUT_TSX.is_file(), f"Missing {LAYOUT_TSX}"
    content = LAYOUT_TSX.read_text(encoding="utf-8")
    assert "ThemeProvider" in content


def test_layout_wraps_children_in_theme_provider() -> None:
    """layout.tsx must wrap children with <ThemeProvider>."""
    content = LAYOUT_TSX.read_text(encoding="utf-8")
    assert "<ThemeProvider>" in content or "<ThemeProvider " in content


def test_layout_has_ssr_safe_inline_script() -> None:
    """layout.tsx must have an inline script to prevent flash-of-unstyled-theme."""
    content = LAYOUT_TSX.read_text(encoding="utf-8")
    assert "coherence-theme" in content
    # The inline script should set classList before paint
    assert "classList" in content


def test_layout_ssr_script_handles_system_preference() -> None:
    """Inline script in layout.tsx must check prefers-color-scheme."""
    content = LAYOUT_TSX.read_text(encoding="utf-8")
    assert "prefers-color-scheme" in content


# ---------------------------------------------------------------------------
# site_header.tsx — ThemeToggle integration
# ---------------------------------------------------------------------------


def test_site_header_imports_theme_toggle() -> None:
    """site_header.tsx must import ThemeToggle."""
    assert SITE_HEADER.is_file(), f"Missing {SITE_HEADER}"
    content = SITE_HEADER.read_text(encoding="utf-8")
    assert "ThemeToggle" in content


def test_site_header_renders_theme_toggle() -> None:
    """site_header.tsx must render <ThemeToggle /> in the header."""
    content = SITE_HEADER.read_text(encoding="utf-8")
    assert "<ThemeToggle" in content
