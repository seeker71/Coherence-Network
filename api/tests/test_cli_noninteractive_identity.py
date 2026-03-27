"""Tests for CLI non-interactive identity behavior (cli-noninteractive-identity).

Acceptance criteria validated by this suite:
- `cc identity set <id>` supports script-friendly non-interactive identity setup.
- Missing `identity set` argument prints usage guidance without writing config.
- Non-interactive `identity setup` auto-detects contributor identity from env.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


_API_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_DIR.parent
_CC_BIN = _REPO_ROOT / "cli" / "bin" / "cc.mjs"


def _config_path(home_dir: Path) -> Path:
    return home_dir / ".coherence-network" / "config.json"


def _run_cc(args: list[str], home_dir: Path, *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    # Use an unreachable local URL to avoid network dependency in tests.
    env["COHERENCE_API_URL"] = "http://127.0.0.1:9"
    return subprocess.run(
        ["node", str(_CC_BIN), *args],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_identity_set_requires_contributor_id(tmp_path: Path):
    result = _run_cc(["identity", "set"], tmp_path)

    assert result.returncode == 0
    assert "Usage: cc identity set <contributor_id>" in result.stdout
    assert "non-interactively" in result.stdout
    assert not _config_path(tmp_path).exists()


def test_identity_set_writes_config_noninteractive(tmp_path: Path):
    result = _run_cc(["identity", "set", "qa-bot"], tmp_path)

    assert result.returncode == 0
    assert "Identity set to: qa-bot" in result.stdout
    config = json.loads(_config_path(tmp_path).read_text())
    assert config["contributor_id"] == "qa-bot"


def test_identity_set_preserves_other_config_fields(tmp_path: Path):
    config_file = _config_path(tmp_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"hub_url": "https://example.test", "contributor_id": "old-id"}))

    result = _run_cc(["identity", "set", "new-id"], tmp_path)

    assert result.returncode == 0
    config = json.loads(config_file.read_text())
    assert config["contributor_id"] == "new-id"
    assert config["hub_url"] == "https://example.test"


def test_identity_setup_noninteractive_uses_env_identity(tmp_path: Path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["COHERENCE_API_URL"] = "http://127.0.0.1:9"
    env["COHERENCE_CONTRIBUTOR"] = "env-contributor"
    result = subprocess.run(
        ["node", str(_CC_BIN), "identity", "setup"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Registered as: env-contributor (from env)" in result.stderr
    config = json.loads(_config_path(tmp_path).read_text())
    assert config["contributor_id"] == "env-contributor"
