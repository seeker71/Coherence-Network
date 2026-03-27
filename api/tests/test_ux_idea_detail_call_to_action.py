"""Acceptance tests for UX Idea Detail Call To Action (ux-idea-detail-call-to-action).

The idea detail page ends with a primary navigation block so visitors can take
the next step after reading an idea: browse all ideas, open progress for this
idea, or go to the contribution entry point.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IDEA_DETAIL_PAGE = REPO_ROOT / "web" / "app" / "ideas" / "[idea_id]" / "page.tsx"


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


def test_idea_detail_page_has_call_to_action_nav_region() -> None:
    """Bottom CTA is a named nav landmark for assistive tech and scanning."""
    content = _read(IDEA_DETAIL_PAGE)
    assert 'aria-label="Where to go next"' in content
    assert "Where to go next" in content


def test_idea_detail_call_to_action_links_core_destinations() -> None:
    """CTA exposes the three core next-step routes: list, progress for this idea, contribute."""
    content = _read(IDEA_DETAIL_PAGE)
    assert (
        '<Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">All Ideas</Link>'
        in content
    )
    assert (
        '<Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="text-amber-600 dark:text-amber-400 hover:underline">Progress</Link>'
        in content
    )
    assert (
        '<Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">Contribute</Link>'
        in content
    )
