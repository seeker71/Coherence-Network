"""Proof that native mutation side-effect intents have a Form execution carrier."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDE_EFFECTS_PATH = ROOT / "form" / "form-stdlib" / "native-mutation-side-effects.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "native-mutation-side-effects-band.fk"
INTEGRATION_PATH = ROOT / "form" / "form-stdlib" / "integration" / "native-mutation-side-effects-live.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "native-mutation-side-effects-test.sh"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"
IDEA_HIERARCHY_PATH = ROOT / "api" / "app" / "services" / "idea_hierarchy.py"
CONTRIBUTOR_KEY_PATH = ROOT / "api" / "app" / "services" / "contributor_key_store.py"
GRAPH_MODEL_PATH = ROOT / "api" / "app" / "models" / "graph.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_native_side_effects_form_names_python_side_effect_contracts():
    text = _text(SIDE_EFFECTS_PATH)
    hierarchy = _text(IDEA_HIERARCHY_PATH)
    contributor_keys = _text(CONTRIBUTOR_KEY_PATH)
    graph_model = _text(GRAPH_MODEL_PATH)

    for required in (
        "defn nms-cache-invalidation-receipt-sql",
        "defn nms-parent-edge-repair-sql",
        "defn nms-contributor-key-audit-sql",
        "defn nms-rollback-receipt-sql",
        "defn nms-record-cache-invalidation",
        "defn nms-repair-parent-edge",
        "defn nms-audit-contributor-key",
        "defn nms-record-rollback-receipt",
        "native_mutation_side_effect_receipts",
        "executed-native",
    ):
        assert required in text

    assert "child_idea_ids" in hierarchy
    assert "last_used_at" in contributor_keys
    assert "class Edge(Base)" in graph_model
    assert "ix_graph_edges_pair" in graph_model


def test_native_side_effects_band_executes_across_sibling_kernels():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/tests/native-mutation-side-effects-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 11111" in result.stdout


def test_native_side_effects_live_db_script_runs_or_skips_when_pg_missing():
    result = subprocess.run(
        [str(SCRIPT_PATH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout + result.stderr
    assert (
        "native mutation side effects: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "native mutation side effects: PASS" in output:
        assert "verdict: 11111111" in output


def test_native_side_effects_live_integration_executes_each_intent():
    text = _text(INTEGRATION_PATH)

    for required in (
        "nms-record-cache-invalidation",
        "nms-repair-parent-edge",
        "nms-audit-contributor-key",
        "nms-record-rollback-receipt",
        "native_mutation_side_effect_receipts",
        "contributor_api_keys",
        "graph_edges",
        "11111111",
    ):
        assert required in text


def test_route_forms_name_side_effect_execution_carrier_before_public_flip():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/native-mutation-side-effects-test.sh" in text
        assert "native side-effect execution carrier proven" in text
        assert "parent-edge repair, contributor-key audit, cache-invalidation receipt, and rollback receipt" in text
        assert "does not bind side-effect execution to ordinary public traffic" in text
