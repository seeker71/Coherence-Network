"""Acceptance tests for UX New Contributor Orientation.

This suite validates that the implemented web orientation flow exposes
the expected onboarding affordances and that backing API endpoints used
by the orientation screens are reachable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRIBUTORS_PAGE = REPO_ROOT / "web" / "app" / "contributors" / "page.tsx"
CONTRIBUTE_PAGE = REPO_ROOT / "web" / "app" / "contribute" / "page.tsx"


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


def test_contributors_page_points_new_contributors_to_contribution_console() -> None:
    """Contributors page contains explicit orientation link to the contribution console."""
    content = _read(CONTRIBUTORS_PAGE)
    assert "To register a new contributor and submit changes" in content
    assert 'href="/contribute"' in content
    assert "Contribution Console" in content


def test_contribute_page_contains_new_contributor_orientation_sections() -> None:
    """Contribute page exposes contributor-first sections instead of admin-first forms."""
    content = _read(CONTRIBUTE_PAGE)
    assert "What needs help right now" in content
    assert "Pick something interesting" in content
    assert "I did something" in content
    assert "Recent contributions" in content
    assert "Where to go next" in content


def test_contribute_page_orientation_navigation_links_exist() -> None:
    """Orientation navigation includes next-step destinations for new contributors."""
    content = _read(CONTRIBUTE_PAGE)
    assert 'href="/ideas"' in content
    assert 'href="/specs"' in content
    assert 'href="/resonance"' in content


def test_contribute_page_keeps_admin_controls_behind_advanced_toggle() -> None:
    """Admin workflows are available but no longer positioned as the default contributor path."""
    content = _read(CONTRIBUTE_PAGE)
    assert "Register as a Contributor" not in content
    assert "Select Proposer and Reviewer" not in content
    assert "Create an Idea" not in content
    assert "Update an Idea" not in content
    assert "Advanced admin tools" in content
    assert "Machine API" in content


def test_orientation_backing_endpoints_are_reachable() -> None:
    """APIs consumed by the orientation flow return successful responses."""
    contributors = client.get("/api/contributors")
    assert contributors.status_code == 200

    spec_registry = client.get("/api/spec-registry")
    assert spec_registry.status_code == 200

    queue = client.get("/api/governance/change-requests")
    assert queue.status_code == 200
