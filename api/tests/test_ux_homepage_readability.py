"""Ux Homepage Readability — acceptance tests for specs/task_e647f5766a54f6f1.md.

Verifies body copy and placeholder opacity floors, heading/stats treatment,
and preservation of ambient gradients (no implementation edits; static contract).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MIN_READABILITY_OPACITY = 85


def _opacity_violations(
    content: str,
    *,
    patterns: tuple[str, ...] = (
        r"text-foreground/(\d+)",
        r"text-muted-foreground/(\d+)",
        r"placeholder:text-foreground/(\d+)",
        r"placeholder:text-muted-foreground/(\d+)",
    ),
) -> list[str]:
    bad: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, content):
            val = int(m.group(1))
            if val < MIN_READABILITY_OPACITY:
                bad.append(f"{m.group(0)} (opacity {val} < {MIN_READABILITY_OPACITY})")
    return bad


def test_ux_body_and_labels_meet_minimum_opacity() -> None:
    """Body text, stats labels, step descriptions use at least 85% foreground opacity."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    text = page_path.read_text(encoding="utf-8")
    bad = _opacity_violations(text)
    assert not bad, "page.tsx opacity below minimum:\n" + "\n".join(bad)


def test_ux_form_placeholders_meet_minimum_opacity() -> None:
    """Form placeholders are at least 0.85 opacity (spec: up from 0.40/0.50)."""
    form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
    text = form_path.read_text(encoding="utf-8")
    bad = _opacity_violations(text)
    assert not bad, "idea_submit_form.tsx opacity below minimum:\n" + "\n".join(bad)
    assert "placeholder:text-foreground/85" in text


def test_ux_headings_preserve_ambient_h1_and_readable_sections() -> None:
    """H1 keeps hero-headline; section headings stay legible (H2/H3 present, no dim heading hack)."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    text = page_path.read_text(encoding="utf-8")
    assert 'className="hero-headline' in text or "className='hero-headline" in text
    assert "<h1" in text and "hero-headline" in text
    assert "<h2" in text
    assert "<h3" in text
    # Headings should not use sub-85 opacity on the title element itself
    for m in re.finditer(r"<h[123][^>]*className=\{?\"([^\"]+)\"", text):
        cls = m.group(1)
        for sub in re.finditer(r"text-foreground/(\d+)", cls):
            assert int(sub.group(1)) >= MIN_READABILITY_OPACITY


def test_ux_stats_numbers_full_foreground() -> None:
    """Stats values use full `text-foreground` (100% opacity) for the numeric span."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    text = page_path.read_text(encoding="utf-8")
    assert "text-foreground font-medium" in text
    assert "formatNumber(summary" in text or "formatNumber" in text
    # Contract: value spans are un-slashed foreground
    assert re.search(
        r'<span className="text-foreground font-medium">\{(?:formatNumber|formatCoherenceScore)',
        text,
    ), "expected stat values wrapped in text-foreground font-medium"


def test_ux_soft_ambient_glow_and_gradients_preserved() -> None:
    """Hero blur layers + globals backdrop gradients remain (warm ambient, not removed)."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    ptxt = page_path.read_text(encoding="utf-8")
    assert "blur-[120px]" in ptxt or "blur-" in ptxt
    assert "bg-primary/" in ptxt

    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    css = css_path.read_text(encoding="utf-8")
    assert "body::before" in css
    assert "radial-gradient" in css
    assert "html" in css and "radial-gradient" in css.split("html", 1)[1][:2000]


def test_ux_globals_supports_hero_headline_contrast() -> None:
    """globals.css keeps .hero-headline and softened blooms for legibility."""
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    css = css_path.read_text(encoding="utf-8")
    assert ".hero-headline" in css
    assert "hsl(28 92% 74% / 0.05)" in css
