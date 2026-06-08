"""Proof that application graph table mutations have a native Form carrier."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT_PATH = ROOT / "form" / "form-stdlib" / "application-graph-node-port.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "application-graph-node-port-band.fk"
GRAPH_SERVICE_PATH = ROOT / "api" / "app" / "services" / "graph_service.py"
GRAPH_MODEL_PATH = ROOT / "api" / "app" / "models" / "graph.py"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_application_graph_port_names_live_table_contract():
    form_text = _text(PORT_PATH)
    service_text = _text(GRAPH_SERVICE_PATH)
    model_text = _text(GRAPH_MODEL_PATH)

    for required in (
        "defn agn-create-node-sql",
        "defn agn-update-node-sql",
        "defn agn-delete-node-sql",
        "defn agn-create-node",
        "defn agn-update-node",
        "defn agn-delete-node",
        "graph_nodes",
        "graph_node_revisions",
        "graph_edges",
        "jsonb_build_object",
        "properties = properties ||",
        "DELETE FROM graph_edges",
    ):
        assert required in form_text

    for required in ("def create_node", "def update_node", "def delete_node", "def _record_revision"):
        assert required in service_text

    for required in (
        '__tablename__ = "graph_nodes"',
        '__tablename__ = "graph_edges"',
        '__tablename__ = "graph_node_revisions"',
        "revision_number",
        "fields_changed",
        "snapshot",
    ):
        assert required in model_text


def test_application_graph_band_executes():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/tests/application-graph-node-port-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 1111" in result.stdout


def test_application_graph_sql_carries_revision_and_edge_cleanup_semantics():
    text = _text(BAND_PATH)

    assert "agn-create-node-sql" in text
    assert "agn-update-node-sql" in text
    assert "agn-delete-node-sql" in text
    assert "fields_changed" in text
    assert "COALESCE(max(revision_number), 0) + 1" in text
    assert "WITH deleted_edges AS" in text
    assert "DELETE FROM graph_edges" in text
    assert "DELETE FROM graph_nodes" in text


def test_idea_and_spec_forms_name_application_graph_carrier():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/form-stdlib/application-graph-node-port.fk::agn-create-node|agn-update-node|agn-delete-node" in text
        assert "application-graph-node-port-band.fk" in text
        assert "graph_nodes, graph_node_revisions, and graph_edges" in text
        assert "method-specific" in text
