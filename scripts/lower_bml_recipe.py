#!/usr/bin/env python3
"""Lower one application BML recipe into its deployed .fk artifact on fkwu.

    python3 scripts/lower_bml_recipe.py <recipe>.bml '<main tail>'

The BML domain class is the source authority. The Form source compiler
(``form-source-compile-file`` in the pinned kernel's stdlib) emits the lowered
definitions; this door wraps them into the single ``(do ...)`` recipe shape the
API's kernel bridge binds into — the definitions, then the ``(let ...)`` input
bindings and the result expression given as the main tail — and stamps the
BML's SHA-256 so the grocery test can reject source/artifact drift.

Nothing here reads the environment; the kernel is the checkout's own
``form/fkwu`` (``cc -O2 -o fkwu runtime/fkwu-uni.c`` builds it).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FORM_ROOT = _REPO_ROOT / "form"
_PRELUDES = [
    "form/form-stdlib/core.fk",
    "form/form-stdlib/form-ontology-source-categories.fk",
    "form/form-stdlib/engine.fk",
    "form/form-stdlib/compiler-objects.fk",
    "form/form-stdlib/bmf-grammar.fk",
    "form/form-stdlib/bml-source.fk",
    "form/form-stdlib/bml.fk",
    "form/form-stdlib/form-bml-lower.fk",
    "form/form-stdlib/source-compiler.fk",
]


def lower(bml_path: Path, main_tail: str) -> str:
    fkwu = _FORM_ROOT / "fkwu"
    if not fkwu.is_file():
        raise SystemExit(f"{fkwu} is not built: cd form && cc -O2 -o fkwu runtime/fkwu-uni.c")
    with tempfile.TemporaryDirectory() as scratch:
        out_path = Path(scratch) / "lowered.fk"
        driver = _FORM_ROOT / f".lower-{bml_path.stem}.fk"
        driver.write_text(
            f"; preludes: {' '.join(_PRELUDES)}\n"
            f'(form-source-compile-file "{bml_path.resolve()}" "{out_path}")\n',
            encoding="utf-8",
        )
        try:
            subprocess.run(
                [str(fkwu), driver.name],
                cwd=_FORM_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        finally:
            driver.unlink(missing_ok=True)
        lowered = out_path.read_text(encoding="utf-8")
    definitions = " ".join(
        line.strip() for line in lowered.splitlines() if line.strip()
    )
    digest = hashlib.sha256(bml_path.read_bytes()).hexdigest()
    return (
        f"; GENERATED from {bml_path.name} by form-source-compile-file.\n"
        f"; BML-SHA256: {digest}\n"
        "; Edit the BML authority and regenerate; the grocery ledger test rejects drift.\n"
        f"(do {definitions} {main_tail.strip()})\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    bml_path = Path(argv[1])
    recipe = lower(bml_path, argv[2])
    fk_path = bml_path.with_suffix(".fk")
    fk_path.write_text(recipe, encoding="utf-8")
    print(f"{fk_path} <- {bml_path} ({len(recipe)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
