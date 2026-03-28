"""Homepage readability + landing data contract (spec 150).

Ensures CSS tokens and `web/app/page.tsx` keep body copy at least `text-foreground/85`,
and that public API endpoints used by `/` remain healthy for reviewers.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mutating portfolio routes that require API key (PATCH /ideas/{id})
AUTH_HEADERS = {"X-API-Key": "dev-key"}


def test_get_coherence_score_endpoint() -> None:
    """Coherence score is shown on the homepage when the API returns data."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= data["score"] <= 1.0


def test_homepage_readability_css_tokens() -> None:
    """globals.css raises base foreground/muted lightness and softens the fixed bloom."""
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    assert css_path.is_file(), f"Missing {css_path}"
    css = css_path.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%" in css
    assert ".hero-headline" in css
    assert "hsl(28 92% 74% / 0.05)" in css


def test_homepage_readability_page_classes() -> None:
    """Hero uses .hero-headline; body copy uses /90 or /85 (never below 85)."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    assert page_path.is_file(), f"Missing {page_path}"
    content = page_path.read_text(encoding="utf-8")
    assert "hero-headline" in content
    assert "text-foreground/90" in content
    for match in re.findall(r"text-foreground/(\d+)", content):
        assert int(match) >= 85, f"Found text-foreground/{match} (minimum allowed is 85)"


def test_idea_submit_form_readability() -> None:
    """Form placeholders and optional field meet minimum opacity."""
    form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
    assert form_path.is_file(), f"Missing {form_path}"
    content = form_path.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in content
    assert "text-foreground/90" in content
    assert "text-foreground/70" not in content


def test_ideas_create_read_update_list_cycle() -> None:
    """Create → read → patch → list (homepage consumes GET /api/ideas and GET /ideas/{id})."""
    idea_id = f"ui-read-{uuid.uuid4().hex[:12]}"
    body = {
        "id": idea_id,
        "name": "Readability contract",
        "description": "Seeded for spec 150 UI readability tests.",
        "potential_value": 10.0,
        "estimated_cost": 1.0,
        "confidence": 0.5,
        "manifestation_status": "none",
    }
    create = client.post("/api/ideas", json=body)
    assert create.status_code == 201, create.text
    assert create.json()["id"] == idea_id

    duplicate = client.post("/api/ideas", json=body)
    assert duplicate.status_code == 409

    got = client.get(f"/api/ideas/{idea_id}")
    assert got.status_code == 200
    assert got.json()["id"] == idea_id

    patched = client.patch(
        f"/api/ideas/{idea_id}",
        json={"manifestation_status": "partial"},
        headers=AUTH_HEADERS,
    )
    assert patched.status_code == 200
    assert patched.json()["manifestation_status"] == "partial"

    listed = client.get("/api/ideas")
    assert listed.status_code == 200
    payload = listed.json()
    ids = {str(i.get("id")) for i in payload.get("ideas", [])}
    assert idea_id in ids


def test_resonance_invalid_window_returns_422() -> None:
    """Bad query params are rejected (homepage uses resonance with valid window)."""
    response = client.get("/api/ideas/resonance?window_hours=-1&limit=3")
    assert response.status_code == 422


def test_get_nonexistent_idea_returns_404() -> None:
    response = client.get("/api/ideas/__does_not_exist_idea__")
    assert response.status_code == 404


def test_spec_150_documents_decision_and_evidence_links() -> None:
    """Spec 150 records the dark-contrast-first decision, evidence table, and idea id for ROI follow-up."""
    spec_path = REPO_ROOT / "specs" / "150-homepage-readability-contrast.md"
    assert spec_path.is_file(), f"Missing {spec_path}"
    text = spec_path.read_text(encoding="utf-8")
    assert "Dark contrast fix only" in text
    assert "ux-homepage-readability" in text
    assert "## Evidence (spec → test → impl)" in text
    assert "api/tests/test_ui_readability.py" in text
