"""Regression coverage for the canonical form-cli ask carriers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_CLI = ROOT / "bin" / "form-cli"
STATS = ROOT / "scripts" / "form_cli_stats.py"


def test_ask_plus_reuses_the_canonical_native_trace() -> None:
    source = FORM_CLI.read_text(encoding="utf-8")

    assert 'ask+)      ask_native_escalating "$@"' in source
    assert 'run_native_ask_with_timeout "$native_timeout" "$q"' in source
    assert 'ask_timeout="$2"; native_timeout="$2"' in source
    assert "fca-ask-plus-traced" not in source
    assert "scripts/form_cli_ask.sh" not in source


def test_ask_plus_retires_duplicate_model_and_judge_controls() -> None:
    result = subprocess.run(
        [str(FORM_CLI), "ask+", "--judge-gate", "question"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "native sufficiency gate owns escalation" in result.stderr


def test_ask_plus_rejects_invalid_timeout_before_querying() -> None:
    result = subprocess.run(
        [str(FORM_CLI), "ask+", "--timeout", "later", "two word question"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--timeout must be numeric seconds" in result.stderr


def test_ask_plus_timeout_bounds_the_native_stage(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            str(FORM_CLI),
            "ask+",
            "--remote",
            "printf should-not-run",
            "--timeout",
            "0.001",
            "two word question",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(tmp_path)},
    )

    assert result.returncode == 124
    assert "native timeout after 0.001s" in result.stderr
    assert "should-not-run" not in result.stdout
    assert not (
        tmp_path / ".coherence-network" / "rag-requests" / "form-cli-asks.jsonl"
    ).exists()


def test_stats_reads_the_canonical_observation_ledger() -> None:
    source = STATS.read_text(encoding="utf-8")

    assert 'ASKS = CN / "rag-requests" / "form-cli-asks.jsonl"' in source
    assert 'row.get("grounded") == "yes"' in source
    assert "form-cli-escalations.jsonl" not in source
    assert "form-cli-trust.json" not in source
