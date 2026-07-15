#!/usr/bin/env python3
"""Preserve a legacy ``form/`` tree before initializing its replacement gitlink.

The tree-to-submodule migration can leave ignored build/cache files in ``form/``
after Git removes the formerly tracked sources.  Git will not clone a submodule
over that non-empty directory.  This bridge moves the complete residual tree to
``.cache/form-pre-submodule-*``; it never deletes local material.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


_DISPOSABLE_PATH_PREFIXES = (
    ".cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "form-kernel-rust/target/",
    "form-kernel-ts/dist/",
    "form-kernel-ts/node_modules/",
)


def _index_entry(repo_root: Path, path: str) -> tuple[str, str]:
    proc = subprocess.run(
        ["git", "ls-files", "--stage", "--", path],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return "", ""
    fields = proc.stdout.split()
    return (fields[0], fields[1]) if len(fields) >= 2 else ("", "")


def preserve_legacy_form(repo_root: Path) -> Path | None:
    """Move a non-empty pre-gitlink ``form/`` aside and return its new path."""
    repo_root = repo_root.resolve()
    form_path = repo_root / "form"
    mode, _sha = _index_entry(repo_root, "form")
    if mode != "160000" or (form_path / ".git").exists():
        return None
    if not form_path.exists():
        return None
    if not form_path.is_dir() or form_path.is_symlink():
        raise RuntimeError(f"refusing to replace non-directory form path: {form_path}")
    if not any(form_path.iterdir()):
        return None

    cache_root = repo_root / ".cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = cache_root / f"form-pre-submodule-{stamp}-{os.getpid()}"
    suffix = 0
    while backup.exists():
        suffix += 1
        backup = cache_root / f"form-pre-submodule-{stamp}-{os.getpid()}-{suffix}"
    form_path.rename(backup)
    return backup


def verify_reviewed_form(repo_root: Path) -> None:
    """Reject a missing, mismatched, or materially dirty Form checkout."""
    repo_root = repo_root.resolve()
    form_path = repo_root / "form"
    mode, expected_sha = _index_entry(repo_root, "form")
    if mode != "160000":
        return
    if not (form_path / ".git").exists():
        raise RuntimeError("form submodule is not initialized")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=form_path,
        check=False,
        capture_output=True,
        text=True,
    )
    observed_sha = head.stdout.strip()
    if head.returncode != 0 or observed_sha != expected_sha:
        raise RuntimeError(
            f"form checkout does not match reviewed pin "
            f"(expected {expected_sha}, observed {observed_sha or 'missing'})"
        )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=form_path,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "unable to inspect form checkout")
    material: list[str] = []
    for entry in status.stdout.split("\0"):
        if not entry:
            continue
        code = entry[:2]
        path = entry[3:] if len(entry) > 3 else ""
        disposable = code == "??" and any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in _DISPOSABLE_PATH_PREFIXES
        )
        if not disposable:
            material.append(entry)
    if material:
        raise RuntimeError(
            "form has material work outside the reviewed pin; "
            "land it in coherence-kernel first: " + " | ".join(material)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--verify-clean", action="store_true")
    args = parser.parse_args()
    try:
        backup = preserve_legacy_form(Path(args.repo_root))
        if args.verify_clean:
            verify_reviewed_form(Path(args.repo_root))
    except (OSError, RuntimeError) as exc:
        print(f"prepare-form-submodule: {exc}", file=sys.stderr)
        return 1
    if backup is not None:
        print(f"prepare-form-submodule: preserved legacy form tree at {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
