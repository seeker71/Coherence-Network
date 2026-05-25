#!/usr/bin/env python3
"""Regenerate kernels/python_bmf/emitted/*.py from Form sources.

The bootstrap flow (the goal's "use generated code as compiler input" loop):

  Stage 1 — bare s-expr sources translate directly:
    form/form-stdlib/engine.fk            → engine.py
    form/form-stdlib/source-compiler.fk   → source_compiler.py

  Stage 2 — sources with `section [...]` blocks need pre-expansion by
  the emitted source-compiler before they translate cleanly:
    form/form-stdlib/compiler.fk          → expanded → compiler.py
    form/form-stdlib/grammars/python-bmf.fk → expanded → python_bmf.py

The Stage 2 expansion uses the Stage 1 output (the emitted Python source-
compiler) to expand its own siblings' sections — bootstrap. This is the
loop the universal-translator goal names: the emitted code is the
compiler input for the next emission round.

Run: python3 scripts/regen_emitted_python.py
"""

from __future__ import annotations

import resource
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Stack + recursion to match the Form kernel's iterative walker reach.
try:
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    resource.setrlimit(resource.RLIMIT_STACK, (max(soft, 64 * 1024 * 1024), hard))
except (ValueError, OSError):
    pass
sys.setrecursionlimit(300_000)

from kernels.python_bmf.emit_python import emit_python

STAGE_1 = [
    ("engine",          "form/form-stdlib/engine.fk"),
    ("source_compiler", "form/form-stdlib/source-compiler.fk"),
]
STAGE_2 = [
    ("compiler",        "form/form-stdlib/compiler.fk"),
    ("python_bmf",      "form/form-stdlib/grammars/python-bmf.fk"),
]

EMITTED_DIR = REPO / "kernels/python_bmf/emitted"
EXPANDED_DIR = REPO / "form/.cache/bmf_compiler_expanded"
EMITTED_DIR.mkdir(parents=True, exist_ok=True)
EXPANDED_DIR.mkdir(parents=True, exist_ok=True)


def stage1() -> None:
    print("Stage 1 — translate bare s-expr Form sources directly:")
    for stem, src in STAGE_1:
        fk_text = (REPO / src).read_text()
        py_text = emit_python(fk_text)
        out = EMITTED_DIR / f"{stem}.py"
        out.write_text(py_text)
        compile(py_text, str(out), "exec")
        print(f"  {src} → {out.relative_to(REPO)}  ({out.stat().st_size}b)")


def stage2() -> None:
    """Load the just-emitted source-compiler; use it to expand the section-
    bearing sources; translate the expanded output to Python."""
    print("Stage 2 — expand section-bearing sources, then translate:")
    # Force-reload runtime so it picks up the freshly-emitted Stage-1 modules.
    for mod in list(sys.modules):
        if mod.startswith("kernels.python_bmf"):
            del sys.modules[mod]
    from kernels.python_bmf import runtime as rt_mod
    rt_mod.LOAD_ORDER = ["engine", "source_compiler"]
    rt_mod.DEFERRED = []
    rt = rt_mod.load_bmf_compiler()

    for stem, src in STAGE_2:
        expanded = EXPANDED_DIR / f"{stem}.expanded.fk"
        rt.form_source_compile_file(str(REPO / src), str(expanded))
        py_text = emit_python(expanded.read_text())
        out = EMITTED_DIR / f"{stem}.py"
        out.write_text(py_text)
        compile(py_text, str(out), "exec")
        print(f"  {src} → {expanded.name} → {out.relative_to(REPO)}  ({out.stat().st_size}b)")


def verify() -> None:
    """Force-reload and confirm all four modules load together."""
    print("Verify — load all four into shared namespace:")
    for mod in list(sys.modules):
        if mod.startswith("kernels.python_bmf"):
            del sys.modules[mod]
    from kernels.python_bmf import runtime as rt_mod
    rt_mod.LOAD_ORDER = ["engine", "source_compiler", "compiler", "python_bmf"]
    rt_mod.DEFERRED = []
    rt = rt_mod.load_bmf_compiler()
    n_syms = sum(1 for s in dir(rt) if not s.startswith("_"))
    print(f"  {n_syms} symbols available in the runtime")
    # Spot-check key surfaces
    for sym in ("bmf_object", "form_source_compile_file", "compiler_object",
                "python_source_scan_text", "apply_python_bmf_rule"):
        assert hasattr(rt, sym), f"missing key symbol: {sym}"
        print(f"    ✓ rt.{sym}")


if __name__ == "__main__":
    stage1()
    stage2()
    verify()
    print("\nRegeneration complete.")
