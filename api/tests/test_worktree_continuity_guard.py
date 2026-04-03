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
