"""Proof that the ideas router has a high-level Form expression."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
ROUTER_PATH = ROOT / "api" / "app" / "routers" / "ideas.py"


def _form_text() -> str:
    return FORM_PATH.read_text(encoding="utf-8")


def _router_text() -> str:
    return ROUTER_PATH.read_text(encoding="utf-8")


def test_ideas_router_form_declares_route_shapes_and_whole_structure():
    text = _form_text()

    for required in (
        "form idea_route_shape",
        "form idea_route_recipe_shape",
        "defn idea_route(",
        "defn idea_route_recipe(",
        "defn ideas_router_structure()",
        "defn ideas_router_reading()",
        "example_ideas_router_structure",
    ):
        assert required in text


def test_ideas_router_form_names_shifted_recipe_families():
    text = _form_text()

    for recipe in (
        "browse_ideas_recipe",
        "sense_governance_recipe",
        "choose_next_idea_recipe",
        "mutate_idea_recipe",
        "question_answer_recipe",
        "link_idea_recipe",
        "translate_idea_recipe",
        "invest_in_idea_recipe",
        "rollup_super_idea_recipe",
        "inspect_idea_recipe",
    ):
        assert f"defn {recipe}" in text

    for shifted in (
        "endpoint list -> recipe family lattice",
        "imperative branches -> named movements with service carriers",
        "hidden route intent -> source-backed route_trace",
        "Python ownership -> Python carrier for Form-declared choreography",
    ):
        assert shifted in text


def test_ideas_router_form_keeps_python_as_carrier_with_gap_named():
    text = _form_text()

    assert 'carrier:        "api/app/routers/ideas.py"' in text
    assert "idea_service.list_ideas" in text
    assert "stake_compute_service.execute_stake" in text
    assert "GAP-I1: front-door dispatch still enters through FastAPI" in text
    assert "native kernel route dispatch can consume this recipe" in text


def test_ideas_router_form_describes_live_router_carrier():
    form_text = _form_text()
    router_text = _router_text()

    assert 'route_source: "api/app/routers/ideas.py"' in form_text
    assert 'form_source: "docs/coherence-substrate/ideas-router.form"' in form_text

    for live_route in (
        '@router.get("/ideas"',
        '@router.post("/ideas"',
        '@router.get("/ideas/{idea_id}"',
        '@router.patch("/ideas/{idea_id}"',
        '@router.post("/ideas/{idea_id}/questions"',
        '@router.post("/ideas/{idea_id}/stake"',
    ):
        assert live_route in router_text
