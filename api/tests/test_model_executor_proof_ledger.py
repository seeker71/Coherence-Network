from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "model_executor_proof_ledger.py"
    spec = importlib.util.spec_from_file_location("model_executor_proof_ledger", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _record(run_id: str = "unit-proof") -> dict:
    return {
        "ledger_schema": "model_executor_proof_run/v1",
        "run_id": run_id,
        "thread_branch": "codex/unit-proof",
        "model_used": "gpt-5-codex",
        "input_tokens": 0,
        "output_tokens": 0,
        "attempts": 1,
        "commands_run": ["pytest"],
        "pass_fail": "pass",
        "failure_reason": "unit proof",
        "source": {"kind": "test", "path": "memory"},
        "validation": {"status": "pass", "commands": ["pytest"]},
    }


def test_native_ledger_validates_and_exports_legacy_jsonl(tmp_path: Path) -> None:
    mod = _load_module()
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "unit-proof.json").write_text(json.dumps(_record()), encoding="utf-8")

    assert mod.validate_ledger(ledger_dir) == []

    exported = mod.export_jsonl(ledger_dir)
    rows = [json.loads(line) for line in exported.splitlines()]

    assert rows == [
        {
            "attempts": 1,
            "commands_run": ["pytest"],
            "failure_reason": "unit proof",
            "input_tokens": 0,
            "model_used": "gpt-5-codex",
            "output_tokens": 0,
            "pass_fail": "pass",
        }
    ]


def test_native_ledger_rejects_duplicate_run_ids(tmp_path: Path) -> None:
    mod = _load_module()
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "a.json").write_text(json.dumps(_record("same-run")), encoding="utf-8")
    (ledger_dir / "b.json").write_text(json.dumps(_record("same-run")), encoding="utf-8")

    errors = mod.validate_ledger(ledger_dir)

    assert any("duplicate run_id" in error for error in errors)
