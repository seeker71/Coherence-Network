from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "view_recipe_library.py"


def run_viewer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_view_recipe_library_choice_receipt_stdout_shape() -> None:
    result = run_viewer("--recipe", "cosine", "--tongue", "form", "--choice-receipt")

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)

    assert payload["kind"] == "form-recipe-route-choice-runtime"
    assert payload["runtime"] == "recipe-choice-runtime"
    assert payload["recipe"]["name"] == "cosine"
    assert payload["tongue"] == "form"
    assert payload["selected_path"] == "recipe-cache:form"
    assert payload["recipe_choice_signature"][:2] == [
        "form-recipe-choice-signature",
        "recipe-library-view",
    ]
    assert payload["route_choice_signature"][:3] == [
        "bml-route-choice-runtime-signature",
        "recipe-library-view",
        "recipe-cache:form",
    ]
    assert payload["rcr_realization_signature"][0] == (
        "form-recipe-route-choice-runtime-signature"
    )
    assert any(
        candidate["path"] == "tree-render:form" and not candidate["eligible"]
        for candidate in payload["candidates"]
    )


def test_view_recipe_library_choice_receipt_requires_recipe_and_tongue() -> None:
    result = run_viewer("--choice-receipt", "--recipe", "cosine")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "--choice-receipt requires --recipe and --tongue" in result.stderr

