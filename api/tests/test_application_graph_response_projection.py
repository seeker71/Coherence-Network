"""Proof that native graph mutation rows project to response shapes."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTION_PATH = ROOT / "form" / "form-stdlib" / "application-graph-response-projection.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "application-graph-response-projection-band.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "application-graph-response-projection-test.sh"
IDEA_MODEL_PATH = ROOT / "api" / "app" / "models" / "idea.py"
SPEC_MODEL_PATH = ROOT / "api" / "app" / "models" / "spec_registry.py"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_response_projection_names_idea_and_spec_response_shapes():
    text = _text(PROJECTION_PATH)
    idea_model = _text(IDEA_MODEL_PATH)
    spec_model = _text(SPEC_MODEL_PATH)

    assert "class IdeaWithScore(Idea)" in idea_model
    assert "class SpecRegistryEntry(BaseModel)" in spec_model
    for required in (
        "defn agrp-idea-with-score-json",
        "defn agrp-spec-entry-json",
        "defn agrp-project-idea-row",
        "defn agrp-project-spec-row",
        "agrp-free-energy-score",
        "agrp-marginal-cc-score",
        "agrp-safe-ratio",
        '\\"free_energy_score\\"',
        '\\"estimated_roi\\"',
    ):
        assert required in text


def test_response_projection_band_executes_across_sibling_kernels():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/application-graph-response-projection.fk",
            "form-stdlib/tests/application-graph-response-projection-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 111" in result.stdout


def test_response_projection_live_db_script_runs_or_skips_when_pg_missing():
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
        "application graph response projection: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "application graph response projection: PASS" in output:
        assert "verdict: 111111" in output


def test_route_forms_name_response_projection_after_bounded_flip():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/application-graph-response-projection-test.sh" in text
        assert "response projection parity proven" in text
        assert "response projection for the promoted mutable routes" in text
        assert "public/default receipts are now proven before broader traffic moves" in text
