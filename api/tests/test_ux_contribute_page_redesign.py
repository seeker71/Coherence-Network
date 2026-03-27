"""Acceptance tests for UX Contribute Page Redesign (ux-contribute-page-redesign).

Validates the redesigned /contribute console: layout, section structure, governance
workflows, live data hooks, and backing API contracts described in the feature spec.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRIBUTE_PAGE = REPO_ROOT / "web" / "app" / "contribute" / "page.tsx"


def _read_contribute_source() -> str:
    assert CONTRIBUTE_PAGE.is_file(), f"Missing contribute page: {CONTRIBUTE_PAGE}"
    return CONTRIBUTE_PAGE.read_text(encoding="utf-8")


def test_contribute_page_imports_live_refresh() -> None:
    """Redesign keeps client-side refresh aligned with other dashboard pages."""
    src = _read_contribute_source()
    assert 'from "@/lib/live_refresh"' in src
    assert "useLiveRefresh(loadData)" in src


def test_contribute_page_loads_parallel_read_apis() -> None:
    """Console batches the four read endpoints used for contributor governance."""
    src = _read_contribute_source()
    assert 'fetch(`${API}/api/contributors`' in src
    assert 'fetch(`${API}/api/ideas`' in src
    assert 'fetch(`${API}/api/spec-registry`' in src
    assert 'fetch(`${API}/api/governance/change-requests`' in src
    assert "Promise.all" in src


def test_contribute_page_redesign_layout_and_visual_system() -> None:
    """Page uses the shared wide layout and card system (gradient panels, rounded chrome)."""
    src = _read_contribute_source()
    assert "max-w-6xl" in src
    assert "min-h-screen" in src
    assert "rounded-2xl" in src
    assert "bg-gradient-to-b" in src
    assert "border-border/30" in src


def test_contribute_page_section_headings_cover_workflow() -> None:
    """Redesign surfaces the full governed-change workflow in labeled sections."""
    src = _read_contribute_source()
    assert '<h1 className="text-3xl font-bold' in src or 'text-3xl font-bold tracking-tight' in src
    assert "Contribute</h1>" in src
    assert "Register as a Contributor" in src
    assert "Select Proposer and Reviewer" in src
    assert "Create an Idea" in src
    assert "Update an Idea" in src
    assert "Questions" in src
    assert "Specs" in src
    assert "Review Queue" in src
    assert "Machine API" in src


def test_contribute_page_review_queue_explains_policy() -> None:
    """Review queue documents approval policy for operators."""
    src = _read_contribute_source()
    assert "CHANGE_REQUEST_MIN_APPROVALS" in src
    assert "Vote YES" in src
    assert "Vote NO" in src


def test_contribute_page_request_type_labels_for_readability() -> None:
    """Human-readable labels map governance request_type codes."""
    src = _read_contribute_source()
    assert "Idea Create" in src
    assert "Spec Create" in src
    assert "idea_create" in src


def test_contribute_page_machine_api_documents_writes() -> None:
    """Footer section lists the same POST/GET routes the UI uses."""
    src = _read_contribute_source()
    assert "POST /api/contributors" in src
    assert "POST /api/governance/change-requests" in src
    assert "POST /api/governance/change-requests/" in src and "/votes" in src


def test_contribute_page_orientation_footer_navigation() -> None:
    """Where-to-next strip links newcomers to Ideas, Specs, and Resonance."""
    src = _read_contribute_source()
    assert 'aria-label="Where to go next"' in src
    assert 'href="/ideas"' in src
    assert 'href="/specs"' in src
    assert 'href="/resonance"' in src


def test_contribute_page_loading_and_error_states() -> None:
    """Loading and destructive error copy remain visible for API failures."""
    src = _read_contribute_source()
    assert "Loading…" in src
    assert "text-destructive" in src


def test_backing_apis_for_contribute_page_are_healthy() -> None:
    """GET endpoints consumed on load return 200 in the test app."""
    for path in (
        "/api/contributors",
        "/api/ideas",
        "/api/spec-registry",
        "/api/governance/change-requests",
    ):
        res = client.get(path)
        assert res.status_code == 200, f"{path} returned {res.status_code}"
