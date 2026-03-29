"""Additional contract tests for Ux My Portfolio (ux-my-portfolio).

Covers interaction wiring on the landing page: submit handling, disabled CTA until
a non-empty ID is entered, and focus/placeholder affordances. Complements
test_ux_my_portfolio_acceptance.py without modifying it.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MY_PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "my-portfolio" / "page.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_my_portfolio_client_component_and_submit_handler() -> None:
    """Landing page is a client component with a guarded submit handler."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert MY_PORTFOLIO_PAGE.is_file()
    assert '"use client"' in text
    assert "function handleGo" in text
    assert "e.preventDefault()" in text


def test_my_portfolio_cta_disabled_until_id_present() -> None:
    """View Portfolio stays disabled until the user enters a non-whitespace ID."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert "disabled={!contributorId.trim()}" in text
    assert 'type="submit"' in text


def test_my_portfolio_input_affordances() -> None:
    """Input shows the expected placeholder and receives initial focus."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert 'placeholder="Contributor ID or handle"' in text
    assert "autoFocus" in text


def test_my_portfolio_centered_layout_shell() -> None:
    """Page uses a centered, readable column suitable for a focused entry flow."""
    text = _read(MY_PORTFOLIO_PAGE)
    assert "min-h-screen" in text
    assert "max-w-2xl" in text
    assert "<main " in text
