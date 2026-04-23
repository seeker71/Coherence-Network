from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "worktree_continuity_guard.py"
    spec = importlib.util.spec_from_file_location("worktree_continuity_guard", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_skippable_artifacts_include_db_sidecars() -> None:
    mod = _load_module()
    assert mod._is_skippable_local_artifact("data/coherence.db") is True
    assert mod._is_skippable_local_artifact("api/data/coherence.db-shm") is True
    assert mod._is_skippable_local_artifact("web/tsconfig.tsbuildinfo") is True
    assert mod._is_skippable_local_artifact("api/app/config_loader.py") is False


def test_autonomous_sidecar_worktree_detects_claude_worktree_path() -> None:
    mod = _load_module()
    assert mod._is_autonomous_sidecar_worktree(
        Path("/Users/test/source/Coherence-Network/.claude/worktrees/worker")
    ) is True
    assert mod._is_autonomous_sidecar_worktree(
        Path("/Users/test/.codex/worktrees/abcd/Coherence-Network")
    ) is False


def test_dirty_only_risk_is_guidance_not_blocking() -> None:
    mod = _load_module()
    assert mod._is_blocking_risk(["dirty_integration_candidate"]) is False
    assert mod._is_blocking_risk(["dirty_integration_candidate", "detached_head"]) is True
    assert mod._is_blocking_risk(["ahead_without_upstream"]) is True


def test_collect_risks_skips_autonomous_claude_sidecars(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()
    repo_root = tmp_path / "repo"
    current = repo_root / "current"
    claude_worker = repo_root / ".claude" / "worktrees" / "worker"
    codex_peer = repo_root / ".codex" / "worktrees" / "peer" / "Coherence-Network"
    current.mkdir(parents=True)
    claude_worker.mkdir(parents=True)
    codex_peer.mkdir(parents=True)

    monkeypatch.setattr(
        mod,
        "_parse_worktrees",
        lambda _repo_root: [
            {"worktree": str(current), "branch": "refs/heads/codex/current"},
            {"worktree": str(claude_worker), "branch": "refs/heads/claude/parallel"},
            {"worktree": str(codex_peer), "branch": "refs/heads/codex/peer"},
        ],
    )
    monkeypatch.setattr(
        mod,
        "_branch_name",
        lambda _wt_path, branch_ref: branch_ref.replace("refs/heads/", "", 1),
    )
    monkeypatch.setattr(
        mod,
        "_status_paths",
        lambda wt_path: [] if wt_path == current else ["docs/in-flight.md"],
    )
    monkeypatch.setattr(
        mod,
        "_ahead_behind_vs_main",
        lambda wt_path: (2, 0) if wt_path == codex_peer else (0, 0),
    )
    monkeypatch.setattr(
        mod,
        "_upstream_exists",
        lambda wt_path: wt_path != codex_peer,
    )

    risks = mod.collect_risks(repo_root, current)

    assert len(risks) == 1
    assert risks[0].path == str(codex_peer.resolve())
    assert risks[0].branch == "codex/peer"
    assert risks[0].risks == ["dirty_integration_candidate", "ahead_without_upstream"]
