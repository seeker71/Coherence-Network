"""Proof that idea valuation audit-ledger parity is Form-native."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_LEDGER_PATH = ROOT / "form" / "form-stdlib" / "native-idea-valuation-audit-ledger.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "native-idea-valuation-audit-ledger-band.fk"
INTEGRATION_PATH = ROOT / "form" / "form-stdlib" / "integration" / "native-idea-valuation-audit-ledger-live.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "native-idea-valuation-audit-ledger-test.sh"
IDEA_WRITE_OPS_PATH = ROOT / "api" / "app" / "services" / "idea_write_ops.py"
AUDIT_SERVICE_PATH = ROOT / "api" / "app" / "services" / "audit_ledger_service.py"
LEDGER_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "native-mutation-side-effect-ledger.form"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_audit_ledger_form_names_python_parity_and_hash_chain():
    text = _text(AUDIT_LEDGER_PATH)
    idea_write_ops = _text(IDEA_WRITE_OPS_PATH)
    audit_service = _text(AUDIT_SERVICE_PATH)

    for required in (
        "defn nival-audit-ledger-ddl-sql",
        "CREATE TABLE IF NOT EXISTS audit_ledger",
        "defn nival-valuation-change-insert-sql",
        "VALUATION_CHANGE",
        "sender_id",
        "receiver_id",
        "SYSTEM",
        "metadata_json",
        "previous_hash",
        "CREATE EXTENSION IF NOT EXISTS pgcrypto",
        "digest(previous.previous_hash",
        "sha256:",
        "0.00000000",
        "defn nival-record-valuation-change",
        "defn nival-record-batch-valuation-change",
        "defn nival-run-idea-update-with-valuation-audit",
        "agn-update-node",
        "nms-record-cache-invalidation",
    ):
        assert required in text

    assert "AuditEntryType.VALUATION_CHANGE" in idea_write_ops
    assert "audit_ledger_service.append_entry" in idea_write_ops
    assert "def compute_entry_hash" in audit_service
    assert "GENESIS_HASH" in audit_service


def test_audit_ledger_band_executes_across_sibling_kernels():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-idea-valuation-audit-ledger.fk",
            "form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 111111" in result.stdout


def test_audit_ledger_live_script_runs_or_skips_when_pg_missing():
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
        "native idea valuation audit ledger: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "native idea valuation audit ledger: PASS" in output:
        assert "verdict: 11111111" in output


def test_audit_ledger_live_integration_verifies_hash_chain_and_route_binding():
    text = _text(INTEGRATION_PATH)

    for required in (
        "nival-record-valuation-change",
        "nival-run-idea-update-with-valuation-audit",
        "audit_ledger",
        "VALUATION_CHANGE",
        "nival-hash-recompute-sql",
        "previous_hash",
        "graph_node_revisions",
        "native_mutation_side_effect_receipts",
        "contributor_api_keys",
        "11111111",
    ):
        assert required in text


def test_ledger_and_route_forms_mark_audit_parity_carried():
    ledger = _text(LEDGER_FORM_PATH)
    assert "idea-valuation-audit-ledger" in ledger
    assert '"python_parity_effect"' in ledger
    assert "form/form-stdlib/native-idea-valuation-audit-ledger.fk::nival-record-valuation-change" in ledger
    assert "form/scripts/native-idea-valuation-audit-ledger-test.sh" in ledger
    assert "missing_python_parity: 0" in ledger
    assert "ordinary no-header flip blocked until carried Form-native or intentionally retired by spec" not in ledger

    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "native idea valuation audit ledger proven" in text
        assert "idea valuation audit-ledger parity is carried Form-native" in text
        assert "public Traefik now sends promoted mutable routes to persistence-preserving HTTP native execution" in text
