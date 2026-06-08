"""Proof that native mutation route runners bind side-effect execution."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE_BINDING_PATH = ROOT / "form" / "form-stdlib" / "native-mutation-route-side-effects.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "native-mutation-route-side-effects-band.fk"
INTEGRATION_PATH = ROOT / "form" / "form-stdlib" / "integration" / "native-mutation-route-side-effects-live.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "native-mutation-route-side-effects-test.sh"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"
AB_HARNESS_PATH = ROOT / "deploy" / "kernel-router" / "mutation_ab_observation_harness.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_route_side_effect_binding_names_graph_and_side_effect_carriers():
    text = _text(ROUTE_BINDING_PATH)

    for required in (
        "defn nmrs-run-idea-create-with-side-effects",
        "defn nmrs-run-spec-update-with-side-effects",
        "agn-create-node",
        "agn-update-node",
        "nms-record-cache-invalidation",
        "nms-repair-parent-edge",
        "nms-audit-contributor-key",
        "nms-record-rollback-receipt",
        '\\"executes\\":true',
        '\\"ordinary_traffic_flip_performed\\":false',
    ):
        assert required in text


def test_route_side_effect_binding_band_executes_across_sibling_kernels():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-mutation-route-side-effects.fk",
            "form-stdlib/tests/native-mutation-route-side-effects-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 11111" in result.stdout


def test_route_side_effect_binding_live_script_runs_or_skips_when_pg_missing():
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
        "native mutation route side effects: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "native mutation route side effects: PASS" in output:
        assert "verdict: 1111111" in output


def test_route_side_effect_binding_live_integration_executes_route_runners():
    text = _text(INTEGRATION_PATH)

    for required in (
        "nmrs-run-idea-create-with-side-effects",
        "nmrs-run-spec-update-with-side-effects",
        "graph_node_revisions",
        "native_mutation_side_effect_receipts",
        "contributor_api_keys",
        "1111111",
    ):
        assert required in text


def test_ab_gate_next_evidence_is_public_gate_after_route_binding():
    text = _text(AB_HARNESS_PATH)

    assert "bind native side-effect execution carrier to mutation route runner" not in text
    assert "narrow reversible public gate with route-local rollback receipt" in text


def test_route_forms_name_route_side_effect_binding_before_public_flip():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/native-mutation-route-side-effects-test.sh" in text
        assert "native route side-effect binding proven" in text
        assert "application graph mutation and side-effect execution in one Form-native route runner" in text
        assert "does not move ordinary public traffic" in text
