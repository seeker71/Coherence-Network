"""Acceptance tests for Ux My Portfolio (ux-my-portfolio).

Locks product copy, navigation, and client-side API wiring described in the idea:
personal view of identities, CC balance, ideas contributed, stakes, and completed tasks.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MY_PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "my-portfolio" / "page.tsx"
CONTRIBUTOR_PORTFOLIO_PAGE = (
    REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "page.tsx"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_acceptance_my_portfolio_landing_copy_and_cta() -> None:
    """User sees plain-language purpose and a clear call to open their portfolio."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert MY_PORTFOLIO_PAGE.is_file()
    assert "My Portfolio" in text
    assert "What have I built?" in text
    assert "Enter your contributor ID to see your identities" in text
    assert "CC balance" in text and "stakes" in text and "completed tasks" in text
    assert "Contributor ID or handle" in text
    assert "View Portfolio" in text


def test_acceptance_my_portfolio_does_not_navigate_on_empty_id() -> None:
    """Submitting with a blank ID does not push a route (guards accidental navigation)."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert "if (!id) return;" in text
    assert "router.push" in text
    assert "/contributors/${encodeURIComponent(id)}/portfolio" in text


def test_acceptance_contributor_portfolio_fetches_all_personal_surfaces() -> None:
    """Detail page loads summary, history, ideas, stakes, and tasks in one pass."""
    text = _read(CONTRIBUTOR_PORTFOLIO_PAGE)
    assert CONTRIBUTOR_PORTFOLIO_PAGE.is_file()
    assert "Promise.all" in text
    assert 'fetch(`${base}/portfolio`)' in text
    assert "cc-history?window=90d&bucket=7d" in text
    assert "idea-contributions?sort=cc_attributed_desc&limit=20" in text
    assert "stakes?sort=roi_desc&limit=20" in text
    assert "tasks?status=completed&limit=20" in text
    assert "encodeURIComponent(contributorId)" in text


def test_acceptance_contributor_portfolio_sections_and_recovery_paths() -> None:
    """Visible sections match the personal portfolio story; errors offer a way back."""
    text = _read(CONTRIBUTOR_PORTFOLIO_PAGE)
    assert "CC Earning History" in text
    assert "90 days · 7d buckets" in text
    assert "Ideas I Contributed To" in text
    assert "Ideas I Staked On" in text
    assert "Tasks I Completed" in text
    assert "← Back to My Portfolio" in text
    assert "← Change Contributor" in text
    assert "Full Profile →" in text


def test_acceptance_idea_drilldown_route_from_portfolio_list() -> None:
    """Each idea row links into per-idea portfolio drill-down for deeper lineage."""
    text = _read(CONTRIBUTOR_PORTFOLIO_PAGE)
    assert "/portfolio/ideas/${encodeURIComponent(idea.idea_id)}" in text
