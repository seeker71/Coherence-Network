"""Proof that graph_nodes have a Form-native storage-port surface."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT_PATH = ROOT / "form" / "form-stdlib" / "graph-node-port.fk"
BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "graph-node-port-band.fk"
GRAPH_SERVICE_PATH = ROOT / "api" / "app" / "services" / "graph_service.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_graph_node_form_port_exposes_read_functions():
    text = _text(PORT_PATH)

    for required in (
        "defn gn-put-node",
        "defn gn-get-node",
        "defn gn-node-exists?",
        "defn gn-count-nodes",
        "defn gn-list-node-ids",
        "defn gn-list-nodes",
    ):
        assert required in text

    assert "storage-port.fk" in text
    assert "api/app/services/graph_service.py::get_node" in text
    assert "api/app/services/graph_service.py::list_nodes(type=...)" in text
    assert "api/app/services/graph_service.py::count_nodes(type=...)" in text


def test_graph_node_form_port_tracks_type_indexes_and_counts():
    text = _text(PORT_PATH)

    for required in (
        "defn gn-node-type-key",
        "defn gn-type-count-key",
        "defn gn-type-index-key",
        "defn gn-adjust-type-indexes",
        "defn gn-index-add-id",
        "defn gn-index-remove-id",
    ):
        assert required in text

    assert "gn-bump-count carrier store (gn-total-count-key) 1" in text
    assert "gn-bump-count carrier store (gn-type-count-key old-type) (sub 0 1)" in text


def test_graph_node_form_band_proves_memory_and_durable_file_carriers():
    text = _text(BAND_PATH)

    assert "Band verdict: 11111" in text
    assert "gn-test (carrier-memory)" in text
    assert "gn-test (carrier-file)" in text
    assert "storage-open cf dir" in text
    assert "gn-count-nodes cf reopened \"idea\"" in text
    assert "gn-list-nodes cf reopened \"idea\"" in text


def test_python_graph_service_contract_still_names_same_functions():
    text = _text(GRAPH_SERVICE_PATH)

    for required in (
        "def get_node(node_id: str)",
        "def list_nodes(",
        "def count_nodes(type: str | None = None)",
    ):
        assert required in text
