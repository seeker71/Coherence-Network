"""Tests for witness oracle emission ledger carrier records."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "witness_oracle_emission_ledger.py"
    spec = importlib.util.spec_from_file_location("witness_oracle_emission_ledger", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _state(frames: int, sample_count: int, *, present: bool = True) -> dict:
    return {
        "present": present,
        "frames": frames,
        "latest": {
            "tick": frames - 1,
            "mic_rms": 0.0061,
            "camera_luma": 0.049,
            "camera_samples": 26000 + frames,
            "gpu_samples": 1000 + frames,
            "gpu_latency_ms": 1.25,
            "body_state": {"sample_count": sample_count},
            "organs_active": [
                "accelerometer",
                "camera",
                "gpu",
                "gyroscope",
                "light",
                "magnetometer",
                "mic",
                "network",
                "screen",
            ],
        },
    }


def test_active_witness_states_produce_increasing_emission_cycles() -> None:
    mod = _load_module()
    record = mod.build_record(
        [_state(1523, 55620), _state(1524, 55625)],
        state_source="unit",
        tools={"whisper-cli": True, "ffmpeg": True, "ollama": True, "adb": True},
    )

    assert record["status"] == "pass"
    assert [cycle["seq"] for cycle in record["cycles"]] == [1523, 1524]
    assert record["cycles"][0]["export"]["source"] == "native-witness-export"
    assert all(process["status"] == "running" for process in record["cycles"][0]["processes"])
    assert {label["protocol"] for label in record["cycles"][0]["labels"]} == {
        "oracle:gpu",
        "oracle:multimodal",
        "oracle:stt",
        "oracle:vision",
    }


def test_stale_witness_state_is_blocked_by_default() -> None:
    mod = _load_module()
    record = mod.build_record([_state(1523, 55620, present=False)], state_source="unit")

    assert record["status"] == "blocked"
    assert any("not live" in reason for reason in record["block_reasons"])


def test_record_writes_native_receipt_ledger_files(tmp_path: Path) -> None:
    mod = _load_module()
    record = mod.build_record(
        [_state(1523, 55620)],
        state_source="unit",
        tools={"whisper-cli": True, "ffmpeg": True, "ollama": True, "adb": True},
    )

    path = mod.write_record(record, tmp_path)

    assert path.exists()
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8").count("\n") == 1
