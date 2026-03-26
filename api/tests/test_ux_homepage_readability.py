"""UX Homepage Readability — acceptance tests (spec: specs/task_e647f5766a54f6f1.md).

Static source checks for opacity, headings, stats, form placeholders, and ambient visuals.
Repo paths are resolved from `api/tests/` (parents[2] = repository root).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_TSX = REPO_ROOT / "web" / "app" / "page.tsx"
FORM_TSX = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
GLOBALS_CSS = REPO_ROOT / "web" / "app" / "globals.css"

_MIN_BODY_OPACITY = 85


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing required file: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page_src() -> str:
    return _read(PAGE_TSX)


@pytest.fixture(scope="module")
def form_src() -> str:
    return _read(FORM_TSX)


@pytest.fixture(scope="module")
def globals_src() -> str:
    return _read(GLOBALS_CSS)


def test_ux_spec_body_copy_uses_minimum_foreground_opacity(page_src: str) -> None:
    """Body copy (hero, stats labels, how-it-works, feed, quote, primary footer row) ≥ /85."""
    # Primary body regions from page.tsx (exclude decorative ping dots and secondary footer link row).
    blocks = [
        r'<p className="text-base md:text-lg text-foreground/90',
        r'<span className="text-sm text-foreground/90"',
        r'<p className="text-sm text-foreground/90 leading-relaxed max-w-\[240px\]',
        r'<h2 className="text-lg font-medium text-center mb-6 text-foreground/90"',
        r'<p className="text-xs text-foreground/90"',
        r'<p className="text-center text-sm text-foreground/90"',
        r'<p className="text-xl md:text-2xl font-light text-foreground/90',
        r'<div className="flex flex-wrap justify-center gap-6 text-sm text-foreground/90',
        r'<p className="text-xs text-foreground/85 leading-relaxed"',
    ]
    for needle in blocks:
        assert needle in page_src, f"Expected body block not found: {needle}"


def test_ux_spec_form_placeholders_at_least_85_opacity(form_src: str) -> None:
    """Placeholders use at least 0.85 opacity vs foreground (placeholder:text-foreground/85)."""
    assert "placeholder:text-foreground/85" in form_src
    assert "placeholder:text-foreground/40" not in form_src
    assert "placeholder:text-foreground/50" not in form_src
    assert "placeholder:text-muted-foreground/40" not in form_src


def test_ux_spec_headings_retain_ambient_styling(page_src: str) -> None:
    """H1 uses hero-headline (full-ink via CSS); H2/H3 stay prominent (no dim body-opacity classes on titles)."""
    assert 'className="hero-headline text-3xl' in page_src
    assert re.search(r"<h1[^>]*hero-headline", page_src)
    assert re.search(
        r'<h2 className="text-lg font-medium text-center mb-6 text-foreground/90"',
        page_src,
    )
    assert '<h3 className="text-base font-medium">' in page_src


def test_ux_spec_stats_values_full_foreground_opacity(page_src: str) -> None:
    """Stat numbers use full `text-foreground` for legibility."""
    assert 'className="text-foreground font-medium"' in page_src
    assert "formatNumber(summary?" in page_src or "formatNumber(summary" in page_src
    assert "formatCoherenceScore" in page_src


def test_ux_spec_soft_ambient_glow_and_gradients_preserved(page_src: str, globals_src: str) -> None:
    """Hero soft blobs + global warm gradients / body bloom remain."""
    assert "blur-[120px]" in page_src
    assert "bg-primary/10" in page_src
    assert "radial-gradient" in globals_src
    assert "body::before" in globals_src
    assert "hsl(28 92% 74% / 0.05)" in globals_src


def test_ux_spec_foreground_opacity_modifiers_except_secondary_footer(page_src: str) -> None:
    """Primary copy uses ≥/85; one secondary footer link row uses /80 (only sub-85 foreground modifier)."""
    secondary_row = (
        '<div className="flex flex-wrap justify-center gap-4 text-xs text-foreground/80 mb-4">'
    )
    assert secondary_row in page_src, "Expected secondary footer external-links row"

    below_min: list[re.Match[str]] = []
    for m in re.finditer(r"text-foreground/(\d+)", page_src):
        if int(m.group(1)) < _MIN_BODY_OPACITY:
            below_min.append(m)
    assert len(below_min) == 1, f"Expected exactly one sub-/{_MIN_BODY_OPACITY} modifier, got {len(below_min)}"
    assert int(below_min[0].group(1)) == 80
    row_start = page_src.index(secondary_row)
    row_end = row_start + len(secondary_row)
    assert row_start <= below_min[0].start() < row_end


def test_ux_spec_idea_form_inputs_meet_readability(form_src: str) -> None:
    """Idea form text fields use ≥ /85 effective readability on inputs (same as task spec)."""
    assert "text-foreground/90" in form_src
    assert "placeholder:text-foreground/85" in form_src


def test_ux_spec_coherence_stat_label_matches_body_tier(page_src: str) -> None:
    """Coherence label line uses same readable tier as other stat labels."""
    assert "coherence" in page_src
    assert 'text-sm text-foreground/90' in page_src
