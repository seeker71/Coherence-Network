from __future__ import annotations

import ast
from pathlib import Path

from app.services.lens_translation_service import build_lens_public_dict


def test_lens_model_does_not_import_services() -> None:
    model_path = Path(__file__).resolve().parents[1] / "app" / "models" / "lens_translation.py"
    tree = ast.parse(model_path.read_text(encoding="utf-8"))

    service_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.services"):
            service_imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            service_imports.extend(alias.name for alias in node.names if alias.name.startswith("app.services"))

    assert service_imports == []


def test_build_lens_public_dict_falls_back_to_belief_vector() -> None:
    payload = build_lens_public_dict(
        "scientific",
        {
            "display_name": "Scientific",
            "description": "Measured evidence.",
            "category": "builtin",
        },
    )

    assert payload["lens_id"] == "scientific"
    assert payload["name"] == "Scientific"
    assert payload["description"] == "Measured evidence."
    assert payload["is_builtin"] is True
    assert payload["archetype_axes"]
