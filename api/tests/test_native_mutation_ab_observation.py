"""Proof for the native mutation A/B observation gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT / "deploy" / "kernel-router" / "mutation_ab_observation_harness.py"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _load_harness():
    spec = importlib.util.spec_from_file_location("mutation_ab_observation_harness", HARNESS_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ab_observation_cases_cover_all_native_mutation_preview_routes():
    mod = _load_harness()

    route_shapes = {(case.method, case.path) for case in mod.CASES}

    assert route_shapes == {
        ("POST", "/api/ideas"),
        ("PATCH", "/api/ideas/idea-ab-native"),
        ("POST", "/api/spec-registry"),
        ("PATCH", "/api/spec-registry/ab-native-spec"),
        ("DELETE", "/api/spec-registry/ab-native-spec"),
    }
    assert all(case.sql_contains for case in mod.CASES)


def test_ab_observation_case_passes_with_native_default_preview_and_fallback():
    mod = _load_harness()
    case = mod.CASES[2]
    default = mod.HTTPObservation(
        status=202,
        router="native-kernel",
        body="",
        parsed={
            "native_default_invitation": True,
            "required_header": None,
            "fallback_header": "X-Form-Python-Fallback",
            "request_body": case.body,
            "executes": True,
            "db_execution": "performed-by-http-native-persistence",
            "sql": " ".join(case.sql_contains),
            "decision_receipt": {
                "selected_path": "implicit-native-invitation",
            },
            "native_invitation": {
                "state": "native-invitation-contract",
                "offer_to_know": True,
                "refusal_is_signal": True,
                "translated": {
                    "language": "Form-native mutation recipe",
                    "operation": "create-spec",
                },
                "execution": {
                    "selected_path": "implicit-native-invitation",
                },
                "speak_next_time": {
                    "fallback_header": "X-Form-Python-Fallback",
                },
                "decline_signal": "native_invitation_declined",
            },
        },
    )
    treatment = mod.HTTPObservation(
        status=202,
        router="native-kernel",
        body="",
        parsed={
            "native_preview": True,
            "operation": "create-spec",
            "node_id": "spec-ab-native-spec",
            "executes": False,
            "request_body": case.body,
            "sql": " ".join(case.sql_contains),
            "trust_envelope": {
                "choice_success": 1,
                "silence": "not-knowing-is-native-invitation",
                "protocol": "X-Form-Native-Preview",
                "fail": "explicit-python-fallback",
                "stop": "native-default-observed",
                "bma": "native-mutation-trust-envelope",
                "prediction_error": "carried_as_residual",
                "side_effect_intents": [
                    {"name": "cache-invalidation"},
                    {"name": "parent-edge-repair"},
                    {"name": "contributor-key-audit"},
                    {"name": "idea-valuation-audit-ledger"},
                ],
                "reversible_gate": {
                    "default_route": "native-kernel",
                    "default_protocol": "implicit-native-invitation",
                    "native_route": "X-Form-Native-Preview",
                    "fallback_route": "X-Form-Python-Fallback",
                    "ordinary_traffic_flip_allowed": True,
                    "ordinary_traffic_flip_performed": True,
                },
            },
        },
    )
    fallback = mod.HTTPObservation(
        status=200,
        router="fanout-python",
        body="",
        parsed={
            "method": "POST",
            "path": "/api/spec-registry",
            "body": case.body,
        },
    )

    observation = mod.evaluate_case(
        case,
        default,
        treatment,
        fallback,
        default_db_checks={
            "native_persistence_node_readback": True,
            "native_persistence_revision_readback": True,
        },
    )

    assert observation.passed is True
    assert all(observation.checks.values())


def test_ab_gate_blocks_flip_when_any_observation_fails():
    mod = _load_harness()
    passing = mod.CaseObservation(
        name="ok",
        passed=True,
        checks={"ok": True},
        default_status=202,
        default_router="native-kernel",
        treatment_status=202,
        treatment_router="native-kernel",
        fallback_status=200,
        fallback_router="fanout-python",
        operation="create-spec",
        node_id="spec-ok",
    )
    failing = mod.CaseObservation(
        name="bad",
        passed=False,
        checks={"treatment_native": False},
        default_status=202,
        default_router="native-kernel",
        treatment_status=200,
        treatment_router="fanout-python",
        fallback_status=200,
        fallback_router="fanout-python",
        operation="",
        node_id="",
    )

    report = mod.build_gate_report([passing, failing], min_confidence=1.0)

    assert report["confidence"] == 0.5
    assert report["gate_pass"] is False
    assert report["ordinary_traffic_flip_performed"] is False
    assert report["ordinary_traffic_flip_allowed"] is True
    assert report["recommendation"] == "hold_flip_collect_more_observations"


def test_ab_gate_recommends_live_db_trial_after_full_confidence():
    mod = _load_harness()
    passing = [
        mod.CaseObservation(
            name=case.name,
            passed=True,
            checks={"ok": True},
            default_status=202,
            default_router="native-kernel",
            treatment_status=202,
            treatment_router="native-kernel",
            fallback_status=200,
            fallback_router="fanout-python",
            operation=case.operation,
            node_id=case.node_id,
        )
        for case in mod.CASES
    ]

    report = mod.build_gate_report(passing, min_confidence=1.0)

    assert report["confidence"] == 1.0
    assert report["gate_pass"] is True
    assert report["recommendation"] == "preview_confidence_complete"
    assert report["ordinary_traffic_flip_performed"] is True
    assert report["python_fallback_header"] == "X-Form-Python-Fallback"
    assert report["next_evidence_needed"] == [
        "deployed bounded native default persists through mounted production config",
        "bounded public Traefik mutable method/path routes to kernel-router",
        "explicit X-Form-Python-Fallback refusal/control signal is counted separately",
    ]


def test_route_forms_name_the_ab_observation_gate_after_bounded_flip():
    for path in (IDEAS_FORM_PATH, SPECS_FORM_PATH):
        text = path.read_text(encoding="utf-8")
        assert "front-door flip -> A/B observation gate before movement" in text
        assert "deploy/kernel-router/mutation_ab_observation_harness.py" in text
        assert "observation gate promoted only the bounded mutable public routes" in text
        assert "implicit native invitation" in text
