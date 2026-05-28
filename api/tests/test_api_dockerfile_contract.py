from __future__ import annotations

import re
from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]


def _dependency_name(value: str) -> str:
    match = re.match(r"([A-Za-z0-9_.-]+)", value.strip())
    assert match is not None
    return match.group(1).lower().replace("_", "-")


def test_api_kernel_builder_rust_toolchain_supports_locked_edition2024_crates() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    lockfile = (REPO_ROOT / "form" / "form-kernel-rust" / "Cargo.lock").read_text(
        encoding="utf-8"
    )

    assert 'name = "idna_adapter"' in lockfile
    assert 'version = "1.2.2"' in lockfile

    match = re.search(
        r"^FROM rust:(?P<major>\d+)\.(?P<minor>\d+)-slim-bookworm AS kernel-builder$",
        dockerfile,
        re.MULTILINE,
    )
    assert match is not None

    toolchain = (int(match.group("major")), int(match.group("minor")))
    assert toolchain >= (1, 86)


def test_api_docker_requirements_cover_pyproject_runtime_dependencies() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "api" / "pyproject.toml").read_text(encoding="utf-8"))
    project_dependencies = {
        _dependency_name(value)
        for value in pyproject["project"]["dependencies"]
    }
    docker_requirements = {
        _dependency_name(line)
        for line in (REPO_ROOT / "api" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert sorted(project_dependencies - docker_requirements) == []
