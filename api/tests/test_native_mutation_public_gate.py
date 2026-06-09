"""Proof that native mutation public gates are reversible and receipt-backed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_GATE_PATH = ROOT / "form" / "form-stdlib" / "native-mutation-public-gate.fk"
AUDIT_LEDGER_PATH = ROOT / "form" / "form-stdlib" / "native-idea-valuation-audit-ledger.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "native-mutation-public-gate-band.fk"
INTEGRATION_PATH = ROOT / "form" / "form-stdlib" / "integration" / "native-mutation-public-gate-live.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "native-mutation-public-gate-test.sh"
PRODUCTION_ROUTES_PATH = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
PUBLIC_GATE_HARNESS_PATH = ROOT / "deploy" / "kernel-router" / "mutation_public_gate_harness.py"
KERNEL_BIN = ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_gate_form_names_header_runner_and_rollback_receipt():
    text = _text(PUBLIC_GATE_PATH)

    for required in (
        "defn nmpg-public-gate-header",
        "X-Form-Native-Public-Gate",
        "defn nmpg-public-gate-rollback-receipt-sql",
        "defn nmpg-decision-receipt-json",
        "public-gate-rollback-receipt",
        "native-mutation-gate-decision-receipt",
        "defn nmpg-run-idea-create-public-gate",
        "defn nmpg-run-idea-update-public-gate",
        "defn nmpg-run-spec-update-public-gate",
        "nmrs-run-idea-create-with-side-effects",
        "nival-run-idea-update-with-valuation-audit",
        "nmrs-run-spec-update-with-side-effects",
        "idea valuation audit ledger",
        '\\"ordinary_traffic_flip_performed\\":false',
    ):
        assert required in text
    assert "defn nival-record-valuation-change" in _text(AUDIT_LEDGER_PATH)


def test_public_gate_band_executes_across_sibling_kernels():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-mutation-route-side-effects.fk",
            "form-stdlib/native-idea-valuation-audit-ledger.fk",
            "form-stdlib/native-mutation-public-gate.fk",
            "form-stdlib/tests/native-mutation-public-gate-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 11111111" in result.stdout


def test_public_gate_live_script_runs_or_skips_when_pg_missing():
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
        "native mutation public gate: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "native mutation public gate: PASS" in output:
        assert "verdict: 111111111" in output


def test_public_gate_live_integration_persists_route_local_receipts():
    text = _text(INTEGRATION_PATH)

    for required in (
        "nmpg-run-idea-create-public-gate",
        "nmpg-run-idea-update-public-gate",
        "nmpg-run-spec-update-public-gate",
        "nival-run-idea-update-with-valuation-audit",
        "audit_ledger",
        "VALUATION_CHANGE",
        "public-gate-rollback-receipt",
        "route-local-rollback-receipt",
        "graph_node_revisions",
        "native_mutation_side_effect_receipts",
        "111111111",
    ):
        assert required in text


def test_production_routes_expose_public_gate_without_no_header_flip():
    text = _text(PRODUCTION_ROUTES_PATH)

    expected_rows = (
        '(kh-route "ideas-create-native-public-gate" "POST" "/api/ideas" 1 "route_ideas_create_native_public_gate" "X-Form-Native-Public-Gate" 0)',
        '(kh-route "ideas-update-native-public-gate" "PATCH" "/api/ideas/*" 1 "route_ideas_update_native_public_gate" "X-Form-Native-Public-Gate" 25)',
        '(kh-route "specs-create-native-public-gate" "POST" "/api/spec-registry" 1 "route_specs_create_native_public_gate" "X-Form-Native-Public-Gate" 0)',
        '(kh-route "specs-update-native-public-gate" "PATCH" "/api/spec-registry/*" 1 "route_specs_update_native_public_gate" "X-Form-Native-Public-Gate" 25)',
        '(kh-route "specs-delete-native-public-gate" "DELETE" "/api/spec-registry/*" 1 "route_specs_delete_native_public_gate" "X-Form-Native-Public-Gate" 25)',
    )
    for row in expected_rows:
        assert row in text

    assert '\\"native_public_gate\\":true' in text
    assert '\\"route_local_gate_executes\\":true' in text
    assert '\\"decision_receipt\\":' in text
    assert "native-mutation-gate-decision-receipt" in text
    assert "can_contradict_intent" in text
    assert '\\"executes\\":false' in text
    assert "Requests without either header" in text
    assert "Ordinary no-header traffic remains fanout-python" in text


def test_public_gate_harness_observes_public_gate_when_kernel_available():
    if not KERNEL_BIN.exists():
        pytest.skip("kernel binary not built for HTTP route harness")

    result = subprocess.run(
        ["python3", str(PUBLIC_GATE_HARNESS_PATH), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report["gate"] == "native_mutation_public_gate"
    assert report["gate_pass"] is True
    assert report["confidence"] == 1.0
    assert report["public_gate_header_allowed"] is True
    assert report["ordinary_traffic_flip_performed"] is False
    assert report["next_evidence_needed"] == [
        "public-gate decision receipts in deployed canary traffic",
        "deployed X-Form-Native-Public-Gate canary before any no-header flip",
    ]
    for case in report["cases"]:
        assert case["checks"]["decision_receipt_state"] is True
        assert case["checks"]["decision_receipt_selected_path"] is True
        assert case["checks"]["decision_receipt_reversible"] is True
        assert case["checks"]["decision_receipt_signature"] is True
        assert case["checks"]["both_headers_decision_receipt_state"] is True
        assert case["checks"]["both_headers_decision_receipt_selected_path"] is True


def test_route_forms_name_public_gate_before_deployed_canary():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/native-mutation-public-gate-test.sh" in text
        assert "native mutation public gate proven" in text
        assert "X-Form-Native-Public-Gate" in text
        assert "deployed header-gated public canary" in text
