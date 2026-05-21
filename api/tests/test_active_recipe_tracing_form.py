"""Proof that active recipe tracing lives in Form."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "docs" / "coherence-substrate" / "active-recipe-tracing.form"


def _form_text() -> str:
    return FORM_PATH.read_text(encoding="utf-8")


def test_active_recipe_trace_form_declares_state_library_and_choice():
    text = _form_text()

    for required in (
        "form recipe_state_shape",
        "form recipe_cell_shape",
        "form recipe_choice_shape",
        "defn available_recipes()",
        "defn active_recipes(state)",
        "defn active_recipes_from_trace(cell)",
        "defn candidate_recipes(state)",
        "defn preferred_recipe(state)",
        "defn keep_or_choose(state)",
    ):
        assert required in text


def test_active_recipe_trace_form_library_can_keep_or_choose():
    text = _form_text()

    for recipe_id in (
        "stability-harmony",
        "connection-density",
        "attention-flow",
        "external-listening",
    ):
        assert recipe_id in text

    assert "action: \"keep_active_recipe\"" in text
    assert "action: \"choose_recipe\"" in text
    assert "example_keep_stability" in text
    assert "example_choose_connection" in text


def test_active_recipe_trace_form_points_trace_persistence_to_existing_gap():
    text = _form_text()

    assert "?active_recipe_traces @cell since current_breath" in text
    assert "scripts/active_recipe_trace_index.py" in text
    assert "file-backed part of GAP-A1" in text
    assert "field-altitude GAP-W1 from traces-teach-the-recipe.form" in text
    assert "not a Python endpoint" in text
