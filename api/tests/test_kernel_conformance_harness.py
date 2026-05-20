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
CORE_VECTOR = (
    REPO_ROOT
    / "docs"
    / "coherence-substrate"
    / "kernel-conformance"
    / "form-core-builtins.json"
)
INFIX_VECTOR = (
    REPO_ROOT
    / "docs"
    / "coherence-substrate"
    / "kernel-conformance"
    / "form-infix-operators.json"
)
CONTROL_VECTOR = (
    REPO_ROOT
    / "docs"
    / "coherence-substrate"
    / "kernel-conformance"
    / "form-control-flow.json"
)
LOOP_VECTOR = (
    REPO_ROOT
    / "docs"
    / "coherence-substrate"
    / "kernel-conformance"
    / "form-loop-mutation.json"
)


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


def _skip_without_toolchains(*names: str) -> None:
    requested = names or ("cargo", "go", "npx")
    missing = [name for name in requested if shutil.which(name) is None]
    if missing:
        pytest.skip(f"kernel runner toolchain(s) unavailable: {', '.join(missing)}")


def test_rust_go_and_typescript_kernels_pass_question_effect_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness(
        "--kernel",
        "rust",
        "--kernel",
        "go",
        "--kernel",
        "typescript",
        "--json",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
        ("typescript", "pass"),
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
        ("typescript", "pass"),
    ]


def test_python_kernel_passes_core_builtin_vector() -> None:
    result = _run_harness("--vector", str(CORE_VECTOR), "--kernel", "python", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "pass"
    assert body["surface"] == "form-core-builtins"
    assert [case["name"] for case in body["kernels"][0]["cases"]] == [
        "len_counts_list",
        "head_returns_first_item",
        "tail_returns_remaining_items",
        "sum_reduces_integer_list",
        "concat_merges_lists",
        "concat_merges_strings",
        "reverse_flips_list",
    ]


def test_rust_go_and_typescript_kernels_pass_core_builtin_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness(
        "--vector",
        str(CORE_VECTOR),
        "--kernel",
        "rust",
        "--kernel",
        "go",
        "--kernel",
        "typescript",
        "--json",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
        ("typescript", "pass"),
    ]


def test_python_kernel_passes_infix_operator_vector() -> None:
    result = _run_harness("--vector", str(INFIX_VECTOR), "--kernel", "python", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "pass"
    assert body["surface"] == "form-infix-operators"
    assert [case["name"] for case in body["kernels"][0]["cases"]] == [
        "multiplication_precedes_addition",
        "parentheses_override_precedence",
        "integer_division_and_subtraction",
        "modulo_returns_remainder",
        "unary_minus_participates_in_arithmetic",
        "comparison_and_logic_chain",
        "unary_not_and_or_chain",
        "string_equality_compares_values",
    ]


def test_rust_go_and_typescript_kernels_pass_infix_operator_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness(
        "--vector",
        str(INFIX_VECTOR),
        "--kernel",
        "rust",
        "--kernel",
        "go",
        "--kernel",
        "typescript",
        "--json",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
        ("typescript", "pass"),
    ]


def test_python_kernel_passes_control_flow_vector() -> None:
    result = _run_harness("--vector", str(CONTROL_VECTOR), "--kernel", "python", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "pass"
    assert body["surface"] == "form-control-flow"
    assert [case["name"] for case in body["kernels"][0]["cases"]] == [
        "if_then_else_true_branch",
        "if_then_else_false_branch",
        "if_without_else_returns_null",
        "if_evaluates_only_selected_branch",
        "do_block_returns_last_statement",
        "let_bindings_feed_later_expressions",
        "let_binding_feeds_builtin_call",
        "inner_do_let_scope_does_not_leak",
    ]


def test_rust_go_and_typescript_kernels_pass_control_flow_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness(
        "--vector",
        str(CONTROL_VECTOR),
        "--kernel",
        "rust",
        "--kernel",
        "go",
        "--kernel",
        "typescript",
        "--json",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
        ("typescript", "pass"),
    ]


def test_python_kernel_passes_loop_mutation_vector() -> None:
    result = _run_harness("--vector", str(LOOP_VECTOR), "--kernel", "python", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "pass"
    assert body["surface"] == "form-loop-mutation"
    assert [case["name"] for case in body["kernels"][0]["cases"]] == [
        "for_list_returns_body_values",
        "for_accumulates_with_set",
        "for_appends_with_set_and_concat",
        "for_string_iterates_characters",
        "while_counts_with_set",
        "while_returns_last_body_value",
        "while_unentered_returns_null",
        "set_walks_to_outer_frame",
    ]


def test_rust_go_and_typescript_kernels_pass_loop_mutation_vector() -> None:
    _skip_without_toolchains()

    result = _run_harness(
        "--vector",
        str(LOOP_VECTOR),
        "--kernel",
        "rust",
        "--kernel",
        "go",
        "--kernel",
        "typescript",
        "--json",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert [(item["kernel"], item["status"]) for item in body["kernels"]] == [
        ("rust", "pass"),
        ("go", "pass"),
        ("typescript", "pass"),
    ]
