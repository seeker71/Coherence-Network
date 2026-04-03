from __future__ import annotations

import importlib.util
import subprocess
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


def test_n8n_security_floor_step_skips_when_not_required() -> None:
    mod = _load_module()
    step = mod._n8n_security_floor_step("", False)
    assert step is None


def test_n8n_security_floor_step_fails_when_required_missing() -> None:
    mod = _load_module()
    step = mod._n8n_security_floor_step("", True)
    assert step is not None
    assert step.ok is False
    assert "no version was provided" in step.output_tail


def test_n8n_security_floor_step_blocks_below_floor() -> None:
    mod = _load_module()
    step = mod._n8n_security_floor_step("1.123.16", False)
    assert step is not None
    assert step.ok is False
    assert "below minimum security floor" in step.output_tail


def test_n8n_security_floor_step_allows_fixed_versions() -> None:
    mod = _load_module()
    v1 = mod._n8n_security_floor_step("1.123.17", False)
    v2 = mod._n8n_security_floor_step("2.5.2", False)
    assert v1 is not None and v1.ok is True
    assert v2 is not None and v2.ok is True


def test_skippable_local_artifacts_include_repo_db_files() -> None:
    mod = _load_module()
    assert mod._is_skippable_local_artifact("data/coherence.db") is True
    assert mod._is_skippable_local_artifact("api/data/coherence.db-wal") is True
    assert mod._is_skippable_local_artifact("web/tsconfig.tsbuildinfo") is True
    assert mod._is_skippable_local_artifact("api/app/main.py") is False


def test_commit_evidence_guard_ignores_skippable_local_artifacts(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "_changed_paths_range", lambda _base_ref, head_ref="HEAD": ([], None))
    monkeypatch.setattr(mod, "_changed_paths_worktree", lambda: ["data/coherence.db", "api/data/coherence.db-wal"])

    step = mod._run_commit_evidence_guard("origin/main")
    assert step.ok is True
    assert "Ignored local artifacts" in step.output_tail


def test_rebase_freshness_guard_blocks_detached_head(monkeypatch) -> None:
    mod = _load_module()

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, "HEAD\n", "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    step = mod._run_rebase_freshness_guard("origin/main")
    assert step.ok is False
    assert "detached HEAD detected" in step.output_tail
    assert "git switch -c codex/" in step.output_tail
