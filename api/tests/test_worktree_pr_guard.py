from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "worktree_pr_guard.py"
    spec = importlib.util.spec_from_file_location("worktree_pr_guard", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_steps_web_build_is_hardened(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "_worktree_has_runtime_changes", lambda _base_ref: True)

    steps = mod._local_steps(
        base_ref="origin/main",
        skip_api_tests=True,
        skip_web_build=False,
        require_gh_auth=False,
        maintainability_output=mod.DEFAULT_MAINTAINABILITY_OUTPUT,
    )
    web_step = next((step for step in steps if step[0] == "web-build"), None)
    assert web_step is not None
    assert "--allow-git=none" in web_step[1]


def test_check_run_hint_build_web_is_hardened() -> None:
    mod = _load_module()
    assert "--allow-git=none" in mod._check_run_hint("build web")


def test_local_steps_uses_non_repo_default_maintainability_output(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "_worktree_has_runtime_changes", lambda _base_ref: True)

    steps = mod._local_steps(
        base_ref="origin/main",
        skip_api_tests=True,
        skip_web_build=True,
        require_gh_auth=False,
        maintainability_output=mod.DEFAULT_MAINTAINABILITY_OUTPUT,
    )
    maintainability_step = next(
        (step for step in steps if step[0] == "maintainability-regression-guard"),
        None,
    )
    assert maintainability_step is not None
    assert mod.DEFAULT_MAINTAINABILITY_OUTPUT in maintainability_step[1]
    assert "maintainability_audit_report.json" not in maintainability_step[1]


def test_auto_heal_generated_artifact_restores_snapshot(monkeypatch, tmp_path) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    target = tmp_path / "maintainability_audit_report.json"
    target.write_text("before\n", encoding="utf-8")
    snapshots = mod._snapshot_files({"maintainability_audit_report.json"})

    target.write_text("after\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_changed_paths_worktree",
        lambda: ["maintainability_audit_report.json"],
    )

    healed = mod._auto_heal_generated_artifacts(
        preexisting_changed_paths=set(),
        snapshots=snapshots,
    )
    assert healed == ["maintainability_audit_report.json"]
    assert target.read_text(encoding="utf-8") == "before\n"
