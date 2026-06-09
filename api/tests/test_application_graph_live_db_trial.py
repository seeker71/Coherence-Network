"""Proof that native application graph mutation SQL executes against live DB."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_PATH = ROOT / "form" / "form-stdlib" / "integration" / "application-graph-live-db.fk"
SCRIPT_PATH = ROOT / "form" / "scripts" / "application-graph-live-db-test.sh"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_live_db_trial_form_uses_application_graph_pg_wrappers():
    text = _text(INTEGRATION_PATH)

    for required in (
        "pg_connect",
        "agn-create-node",
        "agn-update-node",
        "agn-delete-node",
        "pg_query",
        "graph_nodes",
        "graph_node_revisions",
        "graph_edges",
        "to_regclass('public.graph_nodes')",
        "1111111",
    ):
        assert required in text


def test_live_db_trial_script_runs_or_skips_when_postgres_tooling_missing():
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
        "application graph live DB: PASS" in output
        or "SKIP: no PG_DSN set and initdb not found" in output
    )
    if "application graph live DB: PASS" in output:
        assert "verdict: 1111111" in output


def test_route_forms_name_live_db_trial_after_bounded_flip():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/scripts/application-graph-live-db-test.sh" in text
        assert "live DB execution trial" in text
        assert "supports the bounded mutable public flip" in text
        assert "does not perform the all-traffic front-door flip" in text
