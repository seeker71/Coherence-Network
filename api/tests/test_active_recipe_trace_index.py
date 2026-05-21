"""Proof that active recipes hydrate from the witness trace stream."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "active_recipe_trace_index.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("active_recipe_trace_index", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_active_recipe_traces_hydrate_current_breath_for_cell():
    index = _load_module()

    result = index.query_active_recipe_traces(
        cell="efficacy-probe",
        since="current_breath",
    )

    assert result["query"] == "?active_recipe_traces @cell since current_breath"
    assert result["window"]["trace_count"] == 5
    assert result["window"]["start_ts"] == "2026-05-21T02:56:35.739384Z"
    assert result["window"]["end_ts"] == "2026-05-21T02:56:35.741852Z"

    recipes = {row["recipe"]: row for row in result["active_recipes"]}
    assert set(recipes) == {
        "observer",
        "name-the-need",
        "gift",
        "ho'oponopono",
        "freq-angle-focus",
    }
    for recipe in recipes.values():
        assert recipe["active_trace_count"] == 1
        assert recipe["lifetime_trace_count"] == 3
        assert recipe["confidence"] == "weak-signal-n-lt-20"
        assert recipe["cells"] == ["efficacy-probe"]
        assert recipe["cell_node_ids"] == ["1.5.142425.771313"]


def test_active_recipe_traces_accept_cell_node_id_and_all_time():
    index = _load_module()

    result = index.query_active_recipe_traces(
        cell="1.5.142425.771313",
        since="all",
    )

    recipes = {row["recipe"]: row for row in result["active_recipes"]}
    assert result["window"]["trace_count"] == 15
    assert recipes["name-the-need"]["active_trace_count"] == 3
    assert recipes["name-the-need"]["top_band"] == "clarity"
    assert recipes["freq-angle-focus"]["top_band"] == "relation"


def test_active_recipe_trace_index_cli_json():
    result = subprocess.run(
        [
            "python3",
            "scripts/active_recipe_trace_index.py",
            "--cell",
            "efficacy-probe",
            "--since",
            "current_breath",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["window"]["trace_count"] == 5
    assert len(payload["active_recipes"]) == 5
    assert payload["source_path"] == "experiments/local-llm-cell-v0/_field_traces.jsonl"
