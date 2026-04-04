from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "start_gate.py"
    spec = importlib.util.spec_from_file_location("start_gate", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_validate_thread_context_blocks_detached_head() -> None:
    mod = _load_module()
    with pytest.raises(SystemExit, match="detached HEAD"):
        mod._validate_thread_context("HEAD", linked_worktree=True)


def test_validate_thread_context_blocks_main_branch() -> None:
    mod = _load_module()
    with pytest.raises(SystemExit, match="direct work on main/master is blocked"):
        mod._validate_thread_context("main", linked_worktree=True)


def test_validate_thread_context_allows_linked_worktree_branch() -> None:
    mod = _load_module()
    mod._validate_thread_context("feature/my-branch", linked_worktree=True)


def test_validate_thread_context_allows_codex_branch_without_worktree() -> None:
    mod = _load_module()
    mod._validate_thread_context("codex/thread-123", linked_worktree=False)


def test_validate_thread_context_blocks_non_codex_branch_without_worktree() -> None:
    mod = _load_module()
    with pytest.raises(SystemExit, match="not in a linked worktree"):
        mod._validate_thread_context("feature/my-branch", linked_worktree=False)
