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
KERNEL_CANARY_COMPOSE_PATH = ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml"
HOSTINGER_AUTO_DEPLOY_PATH = ROOT / "deploy" / "hostinger" / "auto-deploy.sh"
HOSTINGER_AUTO_DEPLOY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "hostinger-auto-deploy.yml"
PUBLIC_DEPLOY_CONTRACT_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "public-deploy-contract.yml"
PUBLIC_CANARY_VERIFY_PATH = ROOT / "scripts" / "verify_kernel_canary_public_gate.sh"
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
        '\\"ordinary_traffic_flip_performed\\":true',
        "implicit-native-invitation",
        "X-Form-Python-Fallback",
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


def test_production_routes_expose_public_gate_with_native_default_invitation():
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
    for row in (
        '(kh-route "ideas-create-native-default" "POST" "/api/ideas" 0 "route_ideas_create_native_default" "" 0)',
        '(kh-route "ideas-update-native-default" "PATCH" "/api/ideas/*" 0 "route_ideas_update_native_default" "" 25)',
        '(kh-route "specs-create-native-default" "POST" "/api/spec-registry" 0 "route_specs_create_native_default" "" 0)',
        '(kh-route "specs-update-native-default" "PATCH" "/api/spec-registry/*" 0 "route_specs_update_native_default" "" 25)',
        '(kh-route "specs-delete-native-default" "DELETE" "/api/spec-registry/*" 0 "route_specs_delete_native_default" "" 25)',
    ):
        assert row in text

    assert '\\"native_public_gate\\":true' in text
    assert '\\"native_default_invitation\\":true' in text
    assert '\\"route_binding\\":\\"kernel-http-native-default-invitation\\"' in text
    assert '\\"fallback_header\\":\\"X-Form-Python-Fallback\\"' in text
    assert '\\"route_local_gate_executes\\":true' in text
    assert "defn mpg-persistence-result" in text
    assert "config_database_url" in text
    assert "pg_connect" in text
    assert "pg_exec" in text
    assert "performed-by-http-native-persistence" in text
    assert '\\"decision_receipt\\":' in text
    assert "native-mutation-gate-decision-receipt" in text
    assert "can_contradict_intent" in text
    assert '\\"executes\\":' in text
    assert '\\"executes\\":false' in text
    assert "implicit native invitation path" in text
    assert "X-Form-Python-Fallback is the explicit refusal/control signal" in text


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
    if report.get("skipped"):
        pytest.skip(report["skip_reason"])
    assert report["gate"] == "native_mutation_public_gate"
    assert report["gate_pass"] is True
    assert report["confidence"] == 1.0
    assert report["recommendation"] == "verify_deployed_header_canary"
    assert report["native_http_persistence_proven"] is True
    assert report["public_gate_header_allowed"] is True
    assert report["ordinary_traffic_flip_performed"] is True
    assert report["python_fallback_header"] == "X-Form-Python-Fallback"
    assert report["next_evidence_needed"] == [
        "deployed header-gated canary persists through mounted production config",
        "public Traefik default mutation routes to kernel-router",
        "explicit X-Form-Python-Fallback refusal/control signal is counted separately",
    ]
    for case in report["cases"]:
        assert case["checks"]["default_decision_receipt_selected_path"] is True
        assert case["checks"]["default_trust_selected_path"] is True
        assert case["checks"]["default_public_gate_executes_persistence"] is True
        assert (
            case["checks"].get("default_native_persistence_revision_readback") is True
            or case["checks"].get("default_native_persistence_deleted_node") is True
        )
        assert case["checks"]["fallback_fanned_out"] is True
        assert case["checks"]["decision_receipt_state"] is True
        assert case["checks"]["decision_receipt_selected_path"] is True
        assert case["checks"]["decision_receipt_reversible"] is True
        assert case["checks"]["decision_receipt_signature"] is True
        assert case["checks"]["public_gate_executes_persistence"] is True
        assert case["checks"]["public_gate_persistence_closed"] is True
        assert case["checks"]["both_headers_decision_receipt_state"] is True
        assert case["checks"]["both_headers_decision_receipt_selected_path"] is True
        assert case["checks"]["both_headers_public_gate_executes_persistence"] is True


def test_route_forms_name_public_gate_canary_evidence_boundary():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/native-mutation-public-gate-test.sh" in text
        assert "native mutation public gate proven" in text
        assert "X-Form-Native-Public-Gate" in text
        assert "implicit native invitation" in text
        assert "X-Form-Python-Fallback" in text


def test_deploy_exposes_header_gated_public_canary_without_no_header_flip():
    compose = _text(KERNEL_CANARY_COMPOSE_PATH)
    auto_deploy = _text(HOSTINGER_AUTO_DEPLOY_PATH)
    hostinger_workflow = _text(HOSTINGER_AUTO_DEPLOY_WORKFLOW_PATH)
    public_contract_workflow = _text(PUBLIC_DEPLOY_CONTRACT_WORKFLOW_PATH)
    verify_script = _text(PUBLIC_CANARY_VERIFY_PATH)

    assert 'ROUTES_FILE: "/routes/production-routes.fk"' in compose
    assert 'traefik.enable: "true"' in compose
    assert "coherence-api-kernel-public-gate-canary.rule" in compose
    assert "Header(`X-Form-Native-Public-Gate`,`1`)" in compose
    assert "coherence-api-kernel-preview-canary.rule" in compose
    assert "Header(`X-Form-Native-Preview`,`1`)" in compose
    assert "coherence-api-kernel-public-gate-canary.priority" in compose
    assert "loadbalancer.server.port: \"8080\"" in compose
    assert "public ordinary no-header traffic continues to reach api:8000" in compose
    assert "X-Form-Python-Fallback is the explicit" in compose
    assert 'KERNEL_ROUTER_CONFIG_FILE: "/run/coherence-network/config.json"' in compose
    assert "/root/.coherence-network/config.json:/run/coherence-network/config.json:ro" in compose

    assert "ensure_kernel_router_canary" in auto_deploy
    assert "docker-compose.kernel-router.yml" in auto_deploy
    assert "X-Form-Native-Public-Gate: 1" in auto_deploy
    assert '\\"decision_receipt\\"' in auto_deploy
    assert '\\"executes\\":true' in auto_deploy
    assert "performed-by-http-native-persistence" in auto_deploy
    assert '\\"ordinary_traffic_flip_performed\\":true' in auto_deploy

    for workflow in (hostinger_workflow, public_contract_workflow):
        assert "'deploy/kernel-router/**'" in workflow
        assert "'scripts/verify_kernel_canary_public_gate.sh'" in workflow

    assert "Verify kernel public canary" in hostinger_workflow
    assert "./scripts/verify_kernel_canary_public_gate.sh" in hostinger_workflow
    assert "native_public_gate" in verify_script
    assert "executes_true" in verify_script
    assert "performed-by-http-native-persistence" in verify_script
    assert "control_status" in verify_script
    assert "public Traefik no-header control remains outside native default route" in verify_script
