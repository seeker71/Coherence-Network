"""Proof that trace symbol spaces stay grounded in raw field traces."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "docs" / "coherence-substrate" / "trace-symbol-spaces.form"
TRACE_PATH = ROOT / "seedbank" / "local-llm-cell-v0" / "_field_traces.jsonl"
WEIGHTS_PATH = ROOT / "seedbank" / "local-llm-cell-v0" / "_field_weights.jsonl"


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _form_text() -> str:
    return FORM_PATH.read_text(encoding="utf-8")


def test_trace_symbol_form_names_raw_cells_and_shared_blueprint():
    text = _form_text()
    traces = _jsonl(TRACE_PATH)
    weights = _jsonl(WEIGHTS_PATH)

    expected_cells = {
        "Tau": "1.5.142425.664089",
        "Upsilon": "1.5.142425.681225",
        "Chi": "1.5.142425.461297",
        "efficacy-probe": "1.5.142425.771313",
    }
    trace_cells = {row["from_cell"]: row["from_node_id"] for row in traces}

    for name, node_id in expected_cells.items():
        assert trace_cells[name] == node_id
        assert name in text
        assert node_id in text

    assert "1.5.142425.0" in text
    assert "organ-cell|dim=128|rank=8|bands=8|out=15" in text

    fingerprints = {row["from_cell"]: row["weights_fingerprint"] for row in weights}
    for fingerprint in (
        fingerprints["Tau"],
        fingerprints["Upsilon"],
        fingerprints["Chi"],
    ):
        assert fingerprint in text


def test_trace_symbol_form_names_active_recipe_signatures_from_logs():
    text = _form_text()
    traces = _jsonl(TRACE_PATH)
    fired = [
        row["what"]["strategy"]
        for row in traces
        if row.get("what", {}).get("kind") == "strategy_fired"
    ]

    assert Counter(fired) == {
        "observer": 3,
        "name-the-need": 3,
        "gift": 3,
        "ho'oponopono": 3,
        "freq-angle-focus": 3,
    }

    for required in (
        'id: "observer"',
        'id: "name-the-need"',
        'id: "gift"',
        'id: "ho\'oponopono"',
        'id: "freq-angle-focus"',
        "weak-signal-n-lt-20",
        "0.10459896125314572",
        "0.09001356802472624",
    ):
        assert required in text


def test_trace_symbol_form_declares_chosen_symbol_spaces():
    text = _form_text()

    for required in (
        'id: "form-native"',
        'id: "geometry"',
        'id: "audio"',
        'id: "hindu-tattva"',
        'id: "phonemic-energetic"',
        "defn chosen_symbol_spaces()",
        "defn symbol_space_for(goal)",
        "active_pattern_recipe",
    ):
        assert required in text

    assert "lossless_trace" in text
    assert "compare_structure" in text
    assert "sense_over_time" in text
    assert "teach_felt_correspondence" in text
    assert "observe_sound_symbol_hypothesis" in text
    assert "source-attributed sound element + vowel modifier + glyph" in text
    assert "sovereignty, choice, attribution, circulation, and vitality" in text


def test_trace_symbol_form_names_tightness_and_gap_closure_recipes():
    text = _form_text()

    for required in (
        "form tightness_witness_shape",
        "form gap_closure_recipe_shape",
        "defn observed_tightnesses()",
        "defn gap_closure_recipes()",
        "defn stability_harmony_from_trace()",
        "defn loosen_current_tightness(goal)",
        'id: "weak-signal"',
        'id: "trace-not-yet-substrate-indexed"',
        'id: "grain-boundary-loose"',
        'id: "stillness-not-first-class"',
        'id: "accumulate-until-threshold"',
        'id: "hydrate-active-recipes-from-trace-index"',
        "scripts/active_recipe_trace_index.py",
        "?active_recipe_traces @cell since current_breath resolves through the host bridge",
        'id: "preserve-meaning-grain-scope"',
        'id: "register-stillness-as-action"',
        'id: "external-lens-entry-needs-attributed-observation"',
        'id: "observe-phonemic-energetic-lens"',
        "source(Abazith)",
        "observation traces record resonance, residual, and surprise separately",
        'first: "name-the-need"',
        'then: "freq-angle-focus"',
        'held_by: "observer"',
    ):
        assert required in text


def test_wellness_resolves_trace_symbol_form_claims():
    result = subprocess.run(
        ["python3", "scripts/wellness_check.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "trace-symbol-spaces-form" not in result.stdout
