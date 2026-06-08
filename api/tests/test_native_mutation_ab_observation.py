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


def test_ab_observation_case_passes_only_when_a_fanout_and_b_native_preview():
    mod = _load_harness()
    case = mod.CASES[2]
    control = mod.HTTPObservation(
        status=200,
        router="fanout-python",
        body="",
        parsed={
            "method": "POST",
            "path": "/api/spec-registry",
            "body": case.body,
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
                "silence": "fanout-default",
                "protocol": "X-Form-Native-Preview",
                "fail": "rollback-to-fanout",
                "stop": "ordinary-traffic-unflipped",
                "bma": "native-mutation-trust-envelope",
                "prediction_error": "carried_as_residual",
                "side_effect_intents": [
                    {"name": "cache-invalidation"},
                    {"name": "parent-edge-repair"},
                    {"name": "contributor-key-audit"},
                ],
                "reversible_gate": {
                    "default_route": "fanout-python",
                    "native_route": "X-Form-Native-Preview",
                    "ordinary_traffic_flip_allowed": False,
                    "ordinary_traffic_flip_performed": False,
                },
            },
        },
    )

    observation = mod.evaluate_case(case, control, treatment)

    assert observation.passed is True
    assert all(observation.checks.values())


def test_ab_gate_blocks_flip_when_any_observation_fails():
    mod = _load_harness()
    passing = mod.CaseObservation(
        name="ok",
        passed=True,
        checks={"ok": True},
        control_status=200,
        control_router="fanout-python",
        treatment_status=202,
        treatment_router="native-kernel",
        operation="create-spec",
        node_id="spec-ok",
    )
    failing = mod.CaseObservation(
        name="bad",
        passed=False,
        checks={"treatment_native": False},
        control_status=200,
        control_router="fanout-python",
        treatment_status=200,
        treatment_router="fanout-python",
        operation="",
        node_id="",
    )

    report = mod.build_gate_report([passing, failing], min_confidence=1.0)

    assert report["confidence"] == 0.5
    assert report["gate_pass"] is False
    assert report["ordinary_traffic_flip_performed"] is False
    assert report["ordinary_traffic_flip_allowed"] is False
    assert report["recommendation"] == "hold_flip_collect_more_observations"


def test_ab_gate_recommends_live_db_trial_after_full_confidence():
    mod = _load_harness()
    passing = [
        mod.CaseObservation(
            name=case.name,
            passed=True,
            checks={"ok": True},
            control_status=200,
            control_router="fanout-python",
            treatment_status=202,
            treatment_router="native-kernel",
            operation=case.operation,
            node_id=case.node_id,
        )
        for case in mod.CASES
    ]

    report = mod.build_gate_report(passing, min_confidence=1.0)

    assert report["confidence"] == 1.0
    assert report["gate_pass"] is True
    assert report["recommendation"] == "preview_confidence_complete"
    assert report["ordinary_traffic_flip_performed"] is False
    assert report["next_evidence_needed"] == [
        "deployed X-Form-Native-Public-Gate canary before any no-header flip",
    ]


def test_route_forms_name_the_ab_observation_gate_before_flip():
    for path in (IDEAS_FORM_PATH, SPECS_FORM_PATH):
        text = path.read_text(encoding="utf-8")
        assert "front-door flip -> A/B observation gate before movement" in text
        assert "deploy/kernel-router/mutation_ab_observation_harness.py" in text
        assert "preview confidence is complete" in text
        assert "deployed public-gate canary" in text
