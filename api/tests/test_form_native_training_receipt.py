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
    assert receipt["continuous_cycle_count"] == 3
    assert len(receipt["cycle_receipts"]) == 3
    assert receipt["weights"]["hash"].startswith("sha256:")
    assert receipt["data"]["hash"].startswith("sha256:")
    assert receipt["eval"]["hash"].startswith("sha256:")
    assert receipt["data"]["sample_count"] == 12
    assert receipt["eval"]["heldout_count"] == 12
    assert receipt["eval"]["correct_count"] == 12
    assert receipt["training"]["larger_heldout_window_pass"] is True
    assert receipt["training"]["native_beats_oracle"] is True


def test_native_training_receipt_can_build_from_witness_emission_record(tmp_path: Path) -> None:
    mod = _load_module()
    emission = {
        "status": "pass",
        "cycles": [
            {
                "seq": 2001,
                "export": {"checksum": "sha256:cycle-2001", "sample_count": 70001},
                "labels": [
                    {"feature": "speech-transcribe", "label": "speech-present", "privacy": "summary-only"},
                    {"feature": "vision-describe", "label": "scene-present", "privacy": "summary-only"},
                    {"feature": "multimodal-align", "label": "aligned", "privacy": "summary-only"},
                    {"feature": "gpu-readback-kernel", "label": "readback-ok", "privacy": "summary-only"},
                ],
            },
            {
                "seq": 2002,
                "export": {"checksum": "sha256:cycle-2002", "sample_count": 70005},
                "labels": [
                    {"feature": "speech-transcribe", "label": "speech-present", "privacy": "summary-only"},
                    {"feature": "vision-describe", "label": "scene-present", "privacy": "summary-only"},
                    {"feature": "multimodal-align", "label": "aligned", "privacy": "summary-only"},
                    {"feature": "gpu-readback-kernel", "label": "readback-ok", "privacy": "summary-only"},
                ],
            },
            {
                "seq": 2003,
                "export": {"checksum": "sha256:cycle-2003", "sample_count": 70009},
                "labels": [
                    {"feature": "speech-transcribe", "label": "speech-present", "privacy": "summary-only"},
                    {"feature": "vision-describe", "label": "scene-present", "privacy": "summary-only"},
                    {"feature": "multimodal-align", "label": "aligned", "privacy": "summary-only"},
                    {"feature": "gpu-readback-kernel", "label": "readback-ok", "privacy": "summary-only"},
                ],
            },
        ],
    }
    path = tmp_path / "emission.json"
    path.write_text(json.dumps(emission), encoding="utf-8")

    receipt = mod.build_receipt(
        observed_at="2026-06-14T00:00:00Z",
        emission_record=mod.load_emission_record(path),
    )

    assert receipt["continuous_cycle_count"] == 3
    assert receipt["cycle_receipts"][-1]["seq"] == 2003
    assert receipt["eval"]["heldout_count"] == 12
    assert receipt["weights"]["rows"][0]["label"] == "speech-present"


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
