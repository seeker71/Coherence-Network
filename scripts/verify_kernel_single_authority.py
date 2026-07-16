#!/usr/bin/env python3
"""Fail when executable Form/kernel authority leaks outside ``form/``."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = (
    "deploy/front-door/api.bml",
    "docs/coherence-substrate/numeric-formats.canonical.json",
    "kernels/python_bmf",
    "web/lib/form-kernel/vendor/kernel.ts",
    "web/lib/form-kernel/vendor/reader.ts",
    "api/app/services/substrate/form.py",
    "api/app/services/substrate/form_atoms.py",
    "api/app/services/substrate/form_builders.py",
    "api/app/services/substrate/form_check.py",
    "api/app/services/substrate/form_decompile.py",
    "api/app/services/substrate/form_eval.py",
    "api/app/services/substrate/form_lexer.py",
    "api/app/services/substrate/form_operators.py",
    "api/app/services/substrate/form_queries.py",
    "api/app/services/substrate/form_render.py",
    "api/app/services/substrate/form_rules.py",
    "api/app/services/substrate/form_runtime.py",
    "api/app/services/substrate/form_speculation.py",
    "api/app/services/substrate/form_stream.py",
    "api/app/services/substrate/grammar.py",
    "api/app/services/substrate/parallel_eval.py",
    "api/app/services/substrate/recipe_eval.py",
    "api/app/services/substrate/self_host.py",
)

REQUIRED = (
    "form/apps/coherence-network/api.bml",
    "form/contracts/numeric-formats.canonical.json",
    "form/form-stdlib/form-cli-main.fk",
    "form/form-kernel-go",
    "form/form-kernel-rust",
    "form/form-kernel-ts/src/browser.ts",
    "form/python_bmf/CONTRACT.md",
)


def main() -> int:
    errors: list[str] = []
    for relative in FORBIDDEN:
        if (ROOT / relative).exists():
            errors.append(f"duplicate authority exists: {relative}")
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f"canonical submodule authority missing: {relative}")

    mode = subprocess.run(
        ["git", "ls-files", "-s", "form"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    if not mode or mode[0] != "160000":
        errors.append("form is not a gitlink")

    browser_sources = tuple((ROOT / "web/lib/form-kernel").glob("*.ts"))
    for source in browser_sources:
        text = source.read_text(encoding="utf-8")
        if "./vendor/kernel.ts" in text or "./vendor/reader.ts" in text:
            errors.append(f"browser vendor import remains: {source.relative_to(ROOT)}")

    if errors:
        print("\n".join(errors))
        return 1
    print("kernel-single-authority: PASS (execution, stdlib, contracts, and browser kernel are submodule-owned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
