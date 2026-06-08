"""Proof that graph-node mutations have a native Form carrier."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_NODE_PORT_PATH = ROOT / "form" / "form-stdlib" / "graph-node-port.fk"
MUTATION_BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "graph-node-mutation-carrier-band.fk"
IDEAS_ROUTER_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPEC_ROUTER_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_graph_node_port_exposes_create_replace_delete_mutations():
    text = _text(GRAPH_NODE_PORT_PATH)

    for required in (
        "defn gn-create-node",
        "defn gn-replace-node",
        "defn gn-delete-node",
        "defn gn-node-active?",
        "defn gn-mutation-test",
        "gn-deleted-type",
    ):
        assert required in text

    assert "Create refuses an already-active node" in text
    assert "Replace refuses a missing/tombstoned node" in text
    assert "Logical delete" in text
    assert "recreate restores counts" in text


def test_graph_node_mutation_band_proves_memory_file_and_reopen():
    text = _text(MUTATION_BAND_PATH)

    assert "Band verdict: 11111" in text
    assert "gn-mutation-test (carrier-memory)" in text
    assert "gn-mutation-test (carrier-file)" in text
    assert "storage-open cf dir" in text
    assert "spec:restore" in _text(GRAPH_NODE_PORT_PATH)
    assert 'gn-node-exists? cf reopened "idea:mutable"' in text
    assert 'gn-node-exists? cf reopened "spec:mutable"' in text


def test_ideas_and_specs_name_the_native_mutation_carrier():
    ideas_text = _text(IDEAS_ROUTER_FORM_PATH)
    specs_text = _text(SPEC_ROUTER_FORM_PATH)

    for text in (ideas_text, specs_text):
        assert "Form-native graph-node mutation carrier" in text
        assert "gn-create-node" in text
        assert "gn-replace-node" in text
        assert "gn-delete-node" in text
        assert "auth" in text
        assert "graph_nodes" in text
