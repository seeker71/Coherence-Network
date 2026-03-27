from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cli_entrypoint() -> Path:
    return _repo_root() / "cli" / "bin" / "cc.mjs"


def _run_cc(args: list[str], *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(_cli_entrypoint()), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def _read_config(home: Path) -> dict[str, object]:
    config_path = home / ".coherence-network" / "config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _base_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    # Force fast network failure to keep tests quick/deterministic.
    env["COHERENCE_HUB_URL"] = "http://127.0.0.1:9"
    return env


def test_identity_set_writes_contributor_id_to_local_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _base_env(home)

    result = _run_cc(["identity", "set", "qa-bot"], env=env, cwd=_repo_root())

    assert result.returncode == 0, result.stderr
    assert "Identity set to: qa-bot" in result.stdout
    assert _read_config(home)["contributor_id"] == "qa-bot"


def test_identity_set_without_id_prints_usage_and_does_not_create_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _base_env(home)

    result = _run_cc(["identity", "set"], env=env, cwd=_repo_root())

    assert result.returncode == 0, result.stderr
    assert "Usage: cc identity set <contributor_id>" in result.stdout
    assert not (home / ".coherence-network" / "config.json").exists()


def test_identity_setup_noninteractive_prefers_env_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _base_env(home)
    env["COHERENCE_CONTRIBUTOR"] = "env-contributor"

    result = _run_cc(["identity", "setup"], env=env, cwd=_repo_root())

    assert result.returncode == 0, result.stderr
    assert _read_config(home)["contributor_id"] == "env-contributor"
    assert "Registered as: env-contributor (from env)" in result.stderr


def test_identity_setup_noninteractive_uses_git_name_when_env_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _base_env(home)
    env.pop("COHERENCE_CONTRIBUTOR", None)
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig-global")
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True, timeout=10)
    subprocess.run(["git", "config", "user.name", "Git Identity"], cwd=repo, check=True, capture_output=True, text=True, timeout=10)

    result = _run_cc(["identity", "setup"], env=env, cwd=repo)

    assert result.returncode == 0, result.stderr
    assert _read_config(home)["contributor_id"] == "Git Identity"
    assert "Registered as: Git Identity (from git)" in result.stderr


def test_identity_setup_noninteractive_falls_back_to_hostname_hash(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _base_env(home)
    env.pop("COHERENCE_CONTRIBUTOR", None)
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig-global")
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    repo = tmp_path / "repo-no-git-identity"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True, timeout=10)

    host = socket.gethostname()
    expected_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()[:8]
    expected_id = f"node-{host.split('.')[0].lower()}-{expected_hash}"

    result = _run_cc(["identity", "setup"], env=env, cwd=repo)

    assert result.returncode == 0, result.stderr
    assert _read_config(home)["contributor_id"] == expected_id
    assert f"Registered as: {expected_id} (from hostname)" in result.stderr
