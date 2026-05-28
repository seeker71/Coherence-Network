from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


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
