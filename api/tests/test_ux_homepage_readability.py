"""Ux homepage readability acceptance tests (spec 150-homepage-readability-contrast).

Maps to idea/slug: ux-homepage-readability — verifies R1–R4 without modifying shared
`test_ui_readability.py` (parallel contract file).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing {path}"
    return path.read_text(encoding="utf-8")


def test_r1_homepage_body_text_foreground_opacity_floor() -> None:
    """R1: Primary body copy on `/` uses text-foreground opacity >= 0.85 (Tailwind /85+)."""
    page = _read(REPO_ROOT / "web" / "app" / "page.tsx")
    for match in re.findall(r"text-foreground/(\d+)", page):
        assert int(match) >= 85, f"text-foreground/{match} below minimum 85"
    assert "text-foreground/70" not in page
    assert "text-foreground/80" not in page


def test_r1_idea_submit_form_readability_classes() -> None:
    """R1: Form placeholders and body lines meet minimum opacity (no /70 body copy)."""
    form = _read(REPO_ROOT / "web" / "components" / "idea_submit_form.tsx")
    assert "placeholder:text-foreground/85" in form
    assert "text-foreground/90" in form
    assert "text-foreground/85" in form
    assert "text-foreground/70" not in form


def test_r2_globals_css_readability_tokens_and_softer_bloom() -> None:
    """R2: Brighter default foreground/muted tokens; body::before bloom toned down."""
    css = _read(REPO_ROOT / "web" / "app" / "globals.css")
    assert "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%" in css
    assert "body::before" in css
    assert "hsl(28 92% 74% / 0.05)" in css


def test_r3_hero_headline_full_opacity_ink() -> None:
    """R3: Hero H1 uses .hero-headline with full foreground color in CSS."""
    page = _read(REPO_ROOT / "web" / "app" / "page.tsx")
    css = _read(REPO_ROOT / "web" / "app" / "globals.css")
    assert "hero-headline" in page
    assert ".hero-headline" in css
    assert "color: hsl(var(--foreground))" in css


def test_r4_api_coherence_score_contract_for_homepage() -> None:
    """R4: GET /api/coherence/score shape unchanged for homepage consumers."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= float(data["score"]) <= 1.0


def test_r4_api_ideas_list_contract_for_homepage() -> None:
    """R4: GET /api/ideas returns ideas array + summary (homepage loadIdeas)."""
    response = client.get("/api/ideas")
    assert response.status_code == 200
    data = response.json()
    assert "ideas" in data
    assert "summary" in data
    assert isinstance(data["ideas"], list)


def test_r4_api_resonance_feed_contract_for_homepage() -> None:
    """R4: GET /api/ideas/resonance returns a JSON array for homepage feed."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_r4_api_federation_nodes_contract_for_homepage() -> None:
    """R4: GET /api/federation/nodes returns a list (node count on hero)."""
    response = client.get("/api/federation/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_scenario_3_static_contract_homepage_sources_present() -> None:
    """Verification scenario 3: required homepage assets exist at repo paths."""
    assert (REPO_ROOT / "web" / "app" / "page.tsx").is_file()
    assert (REPO_ROOT / "web" / "app" / "globals.css").is_file()
    assert (REPO_ROOT / "web" / "components" / "idea_submit_form.tsx").is_file()
