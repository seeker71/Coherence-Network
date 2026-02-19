from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "pr_check_failure_triage.py"
    spec = importlib.util.spec_from_file_location("pr_check_failure_triage", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hint_mapping_known_checks() -> None:
    mod = _load_module()

    assert "pytest -q" in mod._hint_for_check("Test")
    assert "validate_spec_quality.py" in mod._hint_for_check("Validate spec quality contract")
    assert "worktree_pr_guard.py" in mod._hint_for_check("Thread Gates")
    assert "--allow-git=none" in mod._hint_for_check("Build web")


def test_blocking_failures_detection() -> None:
    mod = _load_module()

    assert mod._has_blocking_failures([]) is False
    assert (
        mod._has_blocking_failures(
            [
                {
                    "failing_check_runs": [],
                    "failing_status_contexts": [],
                    "missing_required_contexts": [],
                    "failing_required_contexts": [],
                }
            ]
        )
        is False
    )
    assert (
        mod._has_blocking_failures(
            [
                {
                    "failing_check_runs": [{"name": "Thread Gates"}],
                    "failing_status_contexts": [],
                    "missing_required_contexts": [],
                    "failing_required_contexts": [],
                }
            ]
        )
        is True
    )
