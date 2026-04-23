from __future__ import annotations

import ast
from pathlib import Path

from app.db.base import Base
from app.models.graph import Edge, Node
from app.services import unified_db


def test_graph_model_does_not_import_services() -> None:
    model_path = Path(__file__).resolve().parents[1] / "app" / "models" / "graph.py"
    tree = ast.parse(model_path.read_text(encoding="utf-8"))

    service_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.services"):
            service_imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            service_imports.extend(alias.name for alias in node.names if alias.name.startswith("app.services"))

    assert service_imports == []


def test_unified_db_reexports_lower_db_base_for_compatibility() -> None:
    assert unified_db.Base is Base
    assert Node.metadata is Base.metadata
    assert Edge.metadata is Base.metadata
    assert "graph_nodes" in Base.metadata.tables
    assert "graph_edges" in Base.metadata.tables
