"""Executable kernel conformance harness for Form question effects."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "scripts" / "verify_kernel_conformance.py"


def _run_harness(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_python_kernel_passes_question_effect_vector() -> None:
    result = _run_harness("--kernel", "python", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "pass"
    assert body["surface"] == "form-question-effects"
    assert body["kernels"][0]["kernel"] == "python"
    assert body["kernels"][0]["status"] == "pass"
    assert [case["name"] for case in body["kernels"][0]["cases"]] == [
        "ask_opens_question",
        "await_answer_reads_current_answer",
        "await_answer_open_question_returns_null",
    ]


def test_rust_and_go_targets_are_explicitly_skipped_when_allowed() -> None:
    result = _run_harness("--kernel", "rust", "--kernel", "go", "--allow-targets", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "skipped"),
        ("go", "skipped"),
    ]
    assert all("conformance target" in item["reason"] for item in body["kernels"])


def test_rust_target_fails_without_executable_runner() -> None:
    result = _run_harness("--kernel", "rust", "--json")

    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["status"] == "fail"
    assert "target-only" in body["error"]
