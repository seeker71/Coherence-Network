"""Proof that graph-node Form envelopes project to idea API read shape."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTION_PATH = ROOT / "form" / "form-stdlib" / "ideas-graph-projection.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "ideas-graph-projection-band.fk"
IDEA_MODEL_PATH = ROOT / "api" / "app" / "models" / "idea.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ideas_graph_projection_declares_schema_functions():
    text = _text(PROJECTION_PATH)

    for required in (
        "defn igp-field",
        "defn igp-status-from-phase",
        "defn igp-idea-json",
        "defn igp-portfolio-json-from-nodes",
        "defn igp-portfolio-json",
        "defn igp-test",
    ):
        assert required in text

    assert "gn-list-nodes carrier store \"idea\"" in text
    assert "IdeaPortfolioResponse" in text


def test_ideas_graph_projection_emits_required_idea_with_score_fields():
    text = _text(PROJECTION_PATH)
    model_text = _text(IDEA_MODEL_PATH)

    assert "class IdeaWithScore(Idea)" in model_text
    for required_field in (
        '\\"potential_value\\"',
        '\\"estimated_cost\\"',
        '\\"manifestation_status\\"',
        '\\"free_energy_score\\"',
        '\\"value_gap\\"',
        '\\"marginal_cc_score\\"',
        '\\"selection_weight\\"',
        '\\"remaining_cost_cc\\"',
        '\\"roi_cc\\"',
    ):
        assert required_field in text


def test_ideas_graph_projection_band_proves_memory_file_and_reopen():
    text = _text(BAND_PATH)

    assert "Band verdict: 11111" in text
    assert "igp-test (carrier-memory)" in text
    assert "igp-test (carrier-file)" in text
    assert "storage-open cf dir" in text
    assert "igp-portfolio-json cf reopened" in text
