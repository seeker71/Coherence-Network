from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SUITE_FILE = ROOT / "tests" / "core_suite.txt"
TEST_BUDGET = 400


def _core_suite_files() -> set[Path]:
    files: set[Path] = set()
    for raw_line in CORE_SUITE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            files.add(ROOT / line)
    return files


def _test_function_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def test_core_suite_manifest_stays_under_budget() -> None:
    core_files = _core_suite_files()
    missing = sorted(str(path.relative_to(ROOT)) for path in core_files if not path.exists())
    assert missing == []

    all_files = {
        path
        for path in (ROOT / "tests").glob("test_*.py")
        if "holdout" not in path.relative_to(ROOT).parts
    }
    assert all_files - core_files

    total_tests = sum(_test_function_count(path) for path in core_files)
    assert total_tests <= TEST_BUDGET
