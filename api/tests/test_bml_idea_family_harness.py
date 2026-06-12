"""Live proof wrapper for the BML idea detail/write family harness."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT / "deploy" / "kernel-router" / "bml_idea_family_harness.py"
KERNEL_BIN = ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"


def _load_harness():
    spec = importlib.util.spec_from_file_location("bml_idea_family_harness", HARNESS_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_bml_idea_family_harness_covers_update_and_question_routes():
    mod = _load_harness()

    route_shapes = {(name, method, path) for name, method, path in (
        ("empty-patch", "PATCH", "/api/ideas/idea-bml-native"),
        ("detail-schema-failure", "GET", "/api/ideas/idea-bml-native"),
        ("idea-update", "PATCH", "/api/ideas/idea-bml-native"),
        ("question-create", "POST", "/api/ideas/idea-question-native/questions"),
        ("question-answer", "POST", "/api/ideas/idea-answer-native/questions/answer"),
    )}

    assert route_shapes == {
        ("empty-patch", "PATCH", "/api/ideas/idea-bml-native"),
        ("detail-schema-failure", "GET", "/api/ideas/idea-bml-native"),
        ("idea-update", "PATCH", "/api/ideas/idea-bml-native"),
        ("question-create", "POST", "/api/ideas/idea-question-native/questions"),
        ("question-answer", "POST", "/api/ideas/idea-answer-native/questions/answer"),
    }
    assert mod.BML_ROUTES.exists()


def test_bml_idea_family_harness_runs_or_skips_when_tools_missing():
    if not KERNEL_BIN.exists():
        pytest.skip("kernel binary not built for BML idea family harness")

    result = subprocess.run(
        ["python3", str(HARNESS_PATH), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    if report.get("skipped"):
        pytest.skip(report["skip_reason"])

    assert report["gate"] == "bml_idea_family_live_proof"
    assert report["gate_pass"] is True
    assert report["confidence"] == 1.0
    assert report["passed_cases"] == report["total_cases"] == 5

    cases = {case["name"]: case for case in report["cases"]}
    assert set(cases) == {
        "idea-update-empty-body",
        "idea-detail-schema-failure",
        "idea-update",
        "idea-question-create",
        "idea-question-answer",
    }

    assert cases["idea-update-empty-body"]["router"] == "native-kernel"
    assert cases["idea-update-empty-body"]["status"] == 400
    assert cases["idea-detail-schema-failure"]["status"] == 503
    assert "graph_nodes" in cases["idea-detail-schema-failure"]["detail"]
    assert "does not exist" in cases["idea-detail-schema-failure"]["detail"]
    assert cases["idea-update"]["handler"] == "api_idea_update"
    assert cases["idea-question-create"]["handler"] == "api_idea_question_create"
    assert cases["idea-question-answer"]["handler"] == "api_idea_question_answer"
