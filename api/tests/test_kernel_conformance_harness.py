"""Executable kernel conformance harness for Form question effects."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


def _skip_without_toolchains() -> None:
    missing = [name for name in ("cargo", "go") if shutil.which(name) is None]
    if missing:
        pytest.skip(f"kernel runner toolchain(s) unavailable: {', '.join(missing)}")


def test_rust_and_go_kernels_pass_question_effect_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness("--kernel", "rust", "--kernel", "go", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
    ]
    for kernel in body["kernels"]:
        assert [case["name"] for case in kernel["cases"]] == [
            "ask_opens_question",
            "await_answer_reads_current_answer",
            "await_answer_open_question_returns_null",
        ]


def test_default_runs_all_implemented_kernels() -> None:
    _skip_without_toolchains()

    result = _run_harness("--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("python", "pass"),
        ("rust", "pass"),
        ("go", "pass"),
    ]
