"""Deployment-carrier proof for the GitNexus trial sidecar."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "deploy" / "hostinger" / "install-gitnexus.sh"


def test_gitnexus_index_is_machine_local() -> None:
    assert ".gitnexus/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_docker_carries_gitnexus_when_host_npx_is_absent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (scripts / ".gitnexus-pin").write_text(
        "npm:1.6.3\n"
        "sha:ffa0510f9a698aad40829dd34afd353f1d74c304\n"
        "gateway:4.2.0\n"
        "node-image:node:20-bookworm\n",
        encoding="utf-8",
    )
    compose_root = tmp_path / "compose"
    compose_root.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/bin/sh\n"
        "echo \"$*\" >> \"$FAKE_DOCKER_ARGS\"\n"
        "case \"$1\" in\n"
        "  rm) exit 0 ;;\n"
        "  run) echo fake-container-id; exit 0 ;;\n"
        "  ps) echo coherence-network-gitnexus; exit 0 ;;\n"
        "  logs) exit 0 ;;\n"
        "esac\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    fake_sleep = fake_bin / "sleep"
    fake_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_sleep.chmod(0o755)
    fake_curl = fake_bin / "curl"
    fake_curl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_curl.chmod(0o755)
    docker_args = tmp_path / "docker-args.txt"

    result = subprocess.run(
        ["/bin/bash", str(INSTALLER)],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "REPO_DIR": str(repo),
            "COMPOSE_ROOT": str(compose_root),
            "LOG_FILE": str(compose_root / "deploy.log"),
            "FAKE_DOCKER_ARGS": str(docker_args),
        },
    )

    assert result.returncode == 0, result.stderr
    assert "starting Docker carrier node:20-bookworm" in result.stdout
    assert "Docker MCP gateway healthy on port 8765" in result.stdout
    deploy_log = (compose_root / "deploy.log").read_text(encoding="utf-8")
    assert "fake-container-id" in deploy_log
    invocation = docker_args.read_text(encoding="utf-8")
    assert "gitnexus-index:/repo/.gitnexus" in invocation
    assert "gitnexus-registry:/root/.gitnexus" in invocation
    assert "gitnexus@1.6.3 analyze --skip-agents-md /repo" in invocation
    assert "supergateway@4.2.0" in invocation
    assert "gitnexus@1.6.3 mcp" in invocation
