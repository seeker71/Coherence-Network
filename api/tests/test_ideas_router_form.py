"""Proof that the ideas router has a high-level Form expression."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
ROUTER_PATH = ROOT / "api" / "app" / "routers" / "ideas.py"
KERNEL_ROUTES_PATH = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
IDEAS_INDEX_PATH = ROOT / "ideas" / "INDEX.md"


def _form_text() -> str:
    return FORM_PATH.read_text(encoding="utf-8")


def _router_text() -> str:
    return ROUTER_PATH.read_text(encoding="utf-8")


def _kernel_routes_text() -> str:
    return KERNEL_ROUTES_PATH.read_text(encoding="utf-8")


def _ideas_index_text() -> str:
    return IDEAS_INDEX_PATH.read_text(encoding="utf-8")


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
        "Form-declared choreography -> kernel-router native structure route",
    ):
        assert shifted in text


def test_ideas_router_form_keeps_python_as_carrier_with_gap_named():
    text = _form_text()

    assert 'carrier:        "api/app/routers/ideas.py"' in text
    assert "idea_service.list_ideas" in text
    assert "stake_compute_service.execute_stake" in text
    assert "GAP-I1: /api/ideas/router-structure and /api/ideas/source-index are kernel-first capable" in text
    assert "graph-node-port.fk exposes native get/list/count" in text
    assert "ideas-graph-projection.fk now emits an IdeaPortfolioResponse-shaped read" in text
    assert "mutable DB-backed portfolio routes still enter through FastAPI until route-manifest binding" in text


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


def test_ideas_router_form_has_native_structure_route():
    form_text = _form_text()
    kernel_text = _kernel_routes_text()

    assert 'path: "/api/ideas/router-structure"' in form_text
    assert "deploy/kernel-router/production-routes.fk::route_ideas_router_structure" in form_text
    assert "kernel-first capable" in form_text

    assert "defn route_ideas_router_structure" in kernel_text
    assert '(list "/api/ideas/router-structure"    route_ideas_router_structure)' in kernel_text
    assert "docs/coherence-substrate/ideas-router.form" in kernel_text
    assert "mutable portfolio data routes still fan out to FastAPI" in kernel_text


def test_ideas_router_form_has_native_source_index_route():
    form_text = _form_text()
    kernel_text = _kernel_routes_text()
    ideas_index_text = _ideas_index_text()

    source_rows = [line for line in ideas_index_text.splitlines() if line.startswith("| [")]
    assert len(source_rows) == 17

    assert 'path: "/api/ideas/source-index"' in form_text
    assert "deploy/kernel-router/production-routes.fk::route_ideas_source_index" in form_text

    assert "defn route_ideas_source_index" in kernel_text
    assert '(list "/api/ideas/source-index"        route_ideas_source_index)' in kernel_text
    assert "super_idea_count" in kernel_text
    assert "source-index route reads repo idea source" in kernel_text
