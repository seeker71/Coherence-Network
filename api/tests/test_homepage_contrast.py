"""
WCAG AA contrast tests for homepage CSS palette (ux-homepage-readability).

Parses the CSS variable values directly from globals.css and asserts
≥4.5:1 contrast for all foreground/background pairs.
"""
import math
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# WCAG helpers
# ---------------------------------------------------------------------------

def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    hi = int(h / 60) % 6
    if hi == 0:
        r, g, b = c, x, 0
    elif hi == 1:
        r, g, b = x, c, 0
    elif hi == 2:
        r, g, b = 0, c, x
    elif hi == 3:
        r, g, b = 0, x, c
    elif hi == 4:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (r + m, g + m, b + m)


def _linearize(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(r: float, g: float, b: float) -> float:
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(h1: float, s1: float, l1: float,
                   h2: float, s2: float, l2: float) -> float:
    lum1 = _luminance(*_hsl_to_rgb(h1, s1, l1))
    lum2 = _luminance(*_hsl_to_rgb(h2, s2, l2))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_css_var(css_text: str, var_name: str) -> tuple[float, float, float]:
    """Extract HSL triple from a CSS variable definition."""
    pattern = rf"--{re.escape(var_name)}:\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%"
    matches = list(re.finditer(pattern, css_text))
    if not matches:
        raise ValueError(f"CSS variable --{var_name} not found")
    h, s, l = matches[0].group(1), matches[0].group(2), matches[0].group(3)
    return float(h), float(s), float(l)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dark_vars(globals_css: str) -> dict[str, tuple[float, float, float]]:
    """Extract dark-mode CSS variable values (the :root / :root.dark block)."""
    # Dark-mode block ends before ':root.light' or ':root.dark' (re-definition)
    dark_section = globals_css.split(":root.light")[0]
    return {
        "background": _parse_css_var(dark_section, "background"),
        "foreground": _parse_css_var(dark_section, "foreground"),
        "primary": _parse_css_var(dark_section, "primary"),
        "primary-foreground": _parse_css_var(dark_section, "primary-foreground"),
        "muted": _parse_css_var(dark_section, "muted"),
        "muted-foreground": _parse_css_var(dark_section, "muted-foreground"),
    }


@pytest.fixture(scope="module")
def light_vars(globals_css: str) -> dict[str, tuple[float, float, float]]:
    """Extract light-mode CSS variable values from the :root.light block."""
    m = re.search(r":root\.light\s*\{([^}]+)\}", globals_css, re.DOTALL)
    if not m:
        raise ValueError(":root.light block not found in globals.css")
    block = m.group(1)
    return {
        "background": _parse_css_var(block, "background"),
        "foreground": _parse_css_var(block, "foreground"),
        "card": _parse_css_var(block, "card"),
        "card-foreground": _parse_css_var(block, "card-foreground"),
        "primary": _parse_css_var(block, "primary"),
        "primary-foreground": _parse_css_var(block, "primary-foreground"),
        "muted": _parse_css_var(block, "muted"),
        "muted-foreground": _parse_css_var(block, "muted-foreground"),
    }


@pytest.fixture(scope="module")
def globals_css() -> str:
    css_path = Path(__file__).parents[2] / "web" / "app" / "globals.css"
    return css_path.read_text()


# ---------------------------------------------------------------------------
# WCAG AA assertions — dark mode
# ---------------------------------------------------------------------------

WCAG_AA = 4.5


class TestDarkModeContrast:
    def test_foreground_on_background(self, dark_vars):
        r = contrast_ratio(*dark_vars["foreground"], *dark_vars["background"])
        assert r >= WCAG_AA, f"dark foreground/bg: {r:.3f} < 4.5"

    def test_primary_on_background(self, dark_vars):
        r = contrast_ratio(*dark_vars["primary"], *dark_vars["background"])
        assert r >= WCAG_AA, f"dark primary/bg: {r:.3f} < 4.5"

    def test_primary_foreground_on_primary(self, dark_vars):
        r = contrast_ratio(*dark_vars["primary-foreground"], *dark_vars["primary"])
        assert r >= WCAG_AA, f"dark primary-fg/primary: {r:.3f} < 4.5"

    def test_muted_foreground_on_background(self, dark_vars):
        r = contrast_ratio(*dark_vars["muted-foreground"], *dark_vars["background"])
        assert r >= WCAG_AA, f"dark muted-fg/bg: {r:.3f} < 4.5"

    def test_muted_foreground_on_muted(self, dark_vars):
        r = contrast_ratio(*dark_vars["muted-foreground"], *dark_vars["muted"])
        assert r >= WCAG_AA, f"dark muted-fg/muted: {r:.3f} < 4.5"

    def test_foreground_minimum_luminance_difference(self, dark_vars):
        """Foreground must be visually distinct from background (not just AA)."""
        r = contrast_ratio(*dark_vars["foreground"], *dark_vars["background"])
        assert r >= 7.0, f"dark foreground/bg is only {r:.3f}:1, expected ≥7:1 for AAA"


# ---------------------------------------------------------------------------
# WCAG AA assertions — light mode
# ---------------------------------------------------------------------------

class TestLightModeContrast:
    def test_foreground_on_background(self, light_vars):
        r = contrast_ratio(*light_vars["foreground"], *light_vars["background"])
        assert r >= WCAG_AA, f"light foreground/bg: {r:.3f} < 4.5"

    def test_primary_on_background(self, light_vars):
        r = contrast_ratio(*light_vars["primary"], *light_vars["background"])
        assert r >= WCAG_AA, f"light primary/bg: {r:.3f} < 4.5"

    def test_primary_foreground_on_primary(self, light_vars):
        r = contrast_ratio(*light_vars["primary-foreground"], *light_vars["primary"])
        assert r >= WCAG_AA, f"light primary-fg/primary: {r:.3f} < 4.5"

    def test_muted_foreground_on_background(self, light_vars):
        r = contrast_ratio(*light_vars["muted-foreground"], *light_vars["background"])
        assert r >= WCAG_AA, f"light muted-fg/bg: {r:.3f} < 4.5"

    def test_muted_foreground_on_card(self, light_vars):
        r = contrast_ratio(*light_vars["muted-foreground"], *light_vars["card"])
        assert r >= WCAG_AA, f"light muted-fg/card: {r:.3f} < 4.5"

    def test_card_foreground_on_card(self, light_vars):
        r = contrast_ratio(*light_vars["card-foreground"], *light_vars["card"])
        assert r >= WCAG_AA, f"light card-fg/card: {r:.3f} < 4.5"

    def test_foreground_on_background_strong(self, light_vars):
        """Main body text should exceed AAA (7:1) for max readability."""
        r = contrast_ratio(*light_vars["foreground"], *light_vars["background"])
        assert r >= 7.0, f"light foreground/bg is only {r:.3f}:1, expected ≥7:1 for AAA"

    def test_primary_lightness_ceiling(self, light_vars):
        """Primary L% must be ≤35 to guarantee ≥4.5:1 on warm off-white background."""
        _, _, l = light_vars["primary"]
        assert l <= 35, f"light --primary L={l}% exceeds ceiling of 35% — contrast will fail"
