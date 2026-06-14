from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "form_native_training_receipt.py"
    spec = importlib.util.spec_from_file_location("form_native_training_receipt", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_native_training_receipt_names_weights_data_and_eval() -> None:
    mod = _load_module()
    receipt = mod.build_receipt(observed_at="2026-06-14T00:00:00Z")

    assert receipt["artifact_id"] == "form-native-nearest-shape-v0"
    assert receipt["weights"]["hash"].startswith("sha256:")
    assert receipt["data"]["hash"].startswith("sha256:")
    assert receipt["eval"]["hash"].startswith("sha256:")
    assert receipt["data"]["sample_count"] == 6
    assert receipt["eval"]["heldout_count"] == 4
    assert receipt["eval"]["correct_count"] == 4
    assert receipt["training"]["native_beats_oracle"] is True


def test_native_training_receipt_check_detects_drift(tmp_path: Path, capsys) -> None:
    mod = _load_module()
    out = tmp_path / "receipt.json"
    receipt = mod.build_receipt(observed_at="2026-06-14T00:00:00Z")
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    prior_argv = sys.argv
    try:
        sys.argv = ["form_native_training_receipt.py", "--check", "--output", str(out), "--observed-at", "2026-06-14T00:00:00Z"]
        assert mod.main() == 0
    finally:
        sys.argv = prior_argv
    assert "ok" in capsys.readouterr().out
