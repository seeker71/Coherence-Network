"""UX Homepage Readability — acceptance tests for spec task_e647f5766a54f6f1.

Verifies static sources meet opacity, heading, stats, and ambient-background criteria.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIN_TEXT_OPACITY_PCT = 85


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    assert path.is_file(), f"Missing {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page_tsx() -> str:
    return _read("web/app/page.tsx")


@pytest.fixture(scope="module")
def globals_css() -> str:
    return _read("web/app/globals.css")


@pytest.fixture(scope="module")
def idea_form_tsx() -> str:
    return _read("web/components/idea_submit_form.tsx")


def test_acceptance_body_copy_opacity_floor(page_tsx: str) -> None:
    """Body text (descriptions, stats labels, step copy) uses at least 85% foreground opacity."""
    for m in re.findall(r"text-foreground/(\d+)", page_tsx):
        assert int(m) >= MIN_TEXT_OPACITY_PCT, f"text-foreground/{m} below {MIN_TEXT_OPACITY_PCT}"
    for m in re.findall(r"text-muted-foreground/(\d+)", page_tsx):
        assert int(m) >= MIN_TEXT_OPACITY_PCT, f"text-muted-foreground/{m} below {MIN_TEXT_OPACITY_PCT}"


def test_acceptance_form_placeholders_opacity_floor(idea_form_tsx: str) -> None:
    """Interactive placeholders use at least 85% opacity (spec: up from 0.40/0.50)."""
    for m in re.findall(r"placeholder:text-foreground/(\d+)", idea_form_tsx):
        assert int(m) >= MIN_TEXT_OPACITY_PCT
    for m in re.findall(r"placeholder:text-muted-foreground/(\d+)", idea_form_tsx):
        assert int(m) >= MIN_TEXT_OPACITY_PCT
    assert "placeholder:text-foreground/85" in idea_form_tsx
    assert "placeholder:text-muted-foreground/40" not in idea_form_tsx
    assert "placeholder:text-muted-foreground/50" not in idea_form_tsx


def test_acceptance_headings_preserve_ambient_h1_and_no_dim_muted(page_tsx: str) -> None:
    """H1 keeps hero-headline; headings avoid legacy dim muted stacks."""
    assert '<h1 className="hero-headline' in page_tsx
    assert "text-muted-foreground/40" not in page_tsx
    assert "text-muted-foreground/50" not in page_tsx


def test_acceptance_heading_lines_opacity_floor(page_tsx: str) -> None:
    """Any opacity on h2/h3 lines stays at or above 85%."""
    for line in page_tsx.splitlines():
        if "<h2" not in line and "<h3" not in line:
            continue
        for m in re.findall(r"text-foreground/(\d+)", line):
            assert int(m) >= MIN_TEXT_OPACITY_PCT
        for m in re.findall(r"text-muted-foreground/(\d+)", line):
            assert int(m) >= MIN_TEXT_OPACITY_PCT


def test_acceptance_stats_values_full_foreground(page_tsx: str) -> None:
    """Stats numbers use full-opacity foreground for legibility."""
    assert 'className="text-foreground font-medium"' in page_tsx
    assert "ideas alive" in page_tsx
    assert "value created" in page_tsx


def test_acceptance_soft_ambient_glow_preserved(page_tsx: str, globals_css: str) -> None:
    """Soft glow layers and warm backdrop gradients remain in homepage + globals."""
    assert "blur-[120px]" in page_tsx
    assert "bg-primary/10" in page_tsx
    assert "radial-gradient" in globals_css
    assert "hsl(28 92% 74% / 0.05)" in globals_css
    assert "linear-gradient(180deg" in globals_css


def test_acceptance_hero_description_high_opacity(page_tsx: str) -> None:
    """Hero description line is clearly in the /85+ family (scenario 1)."""
    assert "A pattern you noticed" in page_tsx
    assert "text-foreground/90" in page_tsx
