"""Static acceptance tests for UX Homepage Readability (ux-homepage-readability).

Maps to specs/task_e647f5766a54f6f1.md — verifies contrast/opacity rules on the
homepage (`web/app/page.tsx`), shared form (`web/components/idea_submit_form.tsx`),
and preserves ambient background treatments without running a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_TSX = REPO_ROOT / "web" / "app" / "page.tsx"
FORM_TSX = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"

# Spec: body copy and labels use at least 0.85 opacity vs foreground.
MIN_OPACITY = 85

_TEXT_FG_OPACITY = re.compile(r"text-foreground/(\d+)")
_PLACEHOLDER_OPACITY = re.compile(r"placeholder:text-foreground/(\d+)")


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


def _assert_min_opacity(matches: list[str], *, label: str) -> None:
    for raw in matches:
        value = int(raw)
        assert value >= MIN_OPACITY, f"{label}: text-foreground/{value} is below minimum {MIN_OPACITY}"


def test_homepage_body_text_opacity_at_least_85_percent() -> None:
    """Body text (descriptions, stats labels, feed copy) uses ≥ 0.85 opacity classes."""
    content = _read(PAGE_TSX)
    matches = _TEXT_FG_OPACITY.findall(content)
    assert matches, "expected at least one text-foreground/N class on homepage"
    _assert_min_opacity(matches, label="page.tsx")


def test_form_placeholders_and_inputs_meet_opacity_floor() -> None:
    """Form placeholders and interactive text use ≥ 0.85 opacity (placeholders explicitly)."""
    content = _read(FORM_TSX)
    ph = _PLACEHOLDER_OPACITY.findall(content)
    assert len(ph) >= 2, "textarea and name input should set placeholder opacity"
    _assert_min_opacity(ph, label="placeholder")
    body = _TEXT_FG_OPACITY.findall(content)
    assert body, "form should use text-foreground/N for typed text and links"
    _assert_min_opacity(body, label="idea_submit_form.tsx")


def test_hero_headline_retains_ambient_styling_without_dimming_modifiers() -> None:
    """H1 keeps hero-headline; primary heading must not use text-foreground/N dimming."""
    content = _read(PAGE_TSX)
    assert "hero-headline" in content
    start = content.index("<h1")
    end = content.index("</h1>") + len("</h1>")
    h1_block = content[start:end]
    assert "hero-headline" in h1_block
    assert not re.search(r"text-foreground/\d+", h1_block), (
        "H1 should not use opacity-modified foreground (preserves ambient heading look)"
    )


def test_h2_h3_headings_not_over_dimmed() -> None:
    """Section H2 uses readable opacity; step H3 titles stay unmodified foreground weight."""
    content = _read(PAGE_TSX)
    h2_start = content.index("<h2")
    h2_end = content.index("</h2>") + len("</h2>")
    h2_block = content[h2_start:h2_end]
    m = re.search(r"text-foreground/(\d+)", h2_block)
    assert m is not None, "H2 should carry a text-foreground/N class for readability"
    assert int(m.group(1)) >= MIN_OPACITY

    h3_start = content.index("<h3")
    h3_end = content.index("</h3>") + len("</h3>")
    h3_block = content[h3_start:h3_end]
    assert "text-base font-medium" in h3_block
    assert "text-foreground/" not in h3_block


def test_how_it_works_step_descriptions_meet_opacity_floor() -> None:
    """Step description paragraphs use ≥ 0.85 opacity (spec scenario 3 / how-it-works)."""
    content = _read(PAGE_TSX)
    assert "{step.description}" in content
    assert 'className="text-sm text-foreground/90' in content


def test_stats_labels_soft_and_numbers_full_foreground() -> None:
    """Stats labels use ≥ 0.85 opacity; numeric values use full text-foreground."""
    content = _read(PAGE_TSX)
    assert "ideas alive" in content
    assert "text-sm text-foreground/90" in content
    assert re.search(
        r'<span className="text-foreground font-medium">\{formatNumber',
        content,
    ), "stats values should use full-opacity text-foreground for numbers"
    assert re.search(
        r'<span className="text-foreground font-medium">\{formatCoherenceScore',
        content,
    ), "coherence stat value should stay full foreground"


def test_soft_ambient_glow_and_gradients_preserved() -> None:
    """Soft ambient glow + card gradients remain (spec: preserve background aesthetic)."""
    content = _read(PAGE_TSX)
    assert "blur-[120px]" in content
    assert "bg-primary/10" in content
    assert "bg-gradient-to-b" in content

