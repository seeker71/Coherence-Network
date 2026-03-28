"""Acceptance tests for specs/ux-homepage-readability.md (exact assertions + R5).

Dedicated module so CI can run `pytest api/tests/test_ux_homepage_readability_acceptance.py -v`
without relying on edits to other test files.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_get_coherence_score_endpoint() -> None:
    """Spec Exact Test Assertions — Test 1."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= data["score"] <= 1.0


def test_homepage_readability_css_tokens() -> None:
    """Spec Exact Test Assertions — Test 2."""
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    assert css_path.is_file()
    css = css_path.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%" in css
    assert ".hero-headline" in css
    assert "hsl(28 92% 74% / 0.05)" in css


def test_homepage_readability_page_classes() -> None:
    """Spec Exact Test Assertions — Test 3."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    assert page_path.is_file()
    content = page_path.read_text(encoding="utf-8")
    assert "hero-headline" in content
    assert "text-foreground/90" in content
    for match in re.findall(r"text-foreground/(\d+)", content):
        assert int(match) >= 85, f"Found text-foreground/{match} — minimum allowed is 85"


def test_idea_submit_form_readability() -> None:
    """Spec Exact Test Assertions — Test 4."""
    form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
    assert form_path.is_file()
    content = form_path.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in content
    assert "text-foreground/90" in content
    assert "text-foreground/70" not in content


def test_r5_get_ideas_contract_unchanged() -> None:
    """R5 — GET /api/ideas remains available for homepage stats."""
    response = client.get("/api/ideas")
    assert response.status_code == 200
    data = response.json()
    assert "ideas" in data
    assert isinstance(data["ideas"], list)


def test_r5_get_resonance_contract_unchanged() -> None:
    """R5 — GET /api/ideas/resonance?window_hours=72&limit=3 feed shape."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 3


def test_r5_get_federation_nodes_contract_unchanged() -> None:
    """R5 — GET /api/federation/nodes for node count."""
    response = client.get("/api/federation/nodes")
    assert response.status_code == 200
    data = response.json()
    assert data is not None


def test_verification_scenario_grep_foreground_lines() -> None:
    """Verification Scenario 1 — token lines match expected grep (line numbers not asserted)."""
    css = (REPO_ROOT / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%;" in css or "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%;" in css or "--muted-foreground: 34 22% 90%" in css
