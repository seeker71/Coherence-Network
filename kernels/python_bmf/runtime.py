"""Runtime loader for the emitted BMF compiler.

The Form kernel loads core.fk + engine.fk + compiler.fk + source-compiler.fk
+ python-bmf.fk into ONE namespace and walks them. The Python translator
emitted one .py per source — but the symbols still cross-reference (e.g.
compiler.py uses `object_lit` defined in engine.py). This loader executes
the emitted modules in dependency order, all in a shared namespace, then
exposes that namespace as the `bmf_compiler` runtime.

Usage:
    from kernels.python_bmf.runtime import load_bmf_compiler
    rt = load_bmf_compiler()
    atoms = rt.python_source_scan_text("def add(a, b):\\n    return a + b")
    # atoms is a list of bmf_object cells with kind ∈ {py-keyword, py-name, ...}
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from . import host_primitives

# Form source code is heavily recursive (head/tail walks, deep AST traversals).
# The emitter lifts tail-recursive Form functions to native Python `while True:`
# loops with parameter rebinding (see emit_python.py `_is_tail_recursive`), so
# the deep head/tail walks no longer consume Python stack frames. The remaining
# non-tail recursion (e.g. tree walkers, `append(self(...), ...)` shapes) sits
# well under 5,000 frames on every workload exercised by the cross-runtime
# harness — a modest cushion above CPython's default 1,000.
sys.setrecursionlimit(5_000)


# Load order matches Form kernel's prepare_sources for the BMF compiler:
# Loaded in dependency order. All four emitted modules load when the
# section [...] grammar blocks in compiler.fk and python-bmf.fk have been
# pre-expanded through the source-compiler. The regeneration flow
# (scripts/regen_emitted_python.py) handles the expansion bootstrap:
#   form/form-stdlib/{compiler,python-bmf}.fk
#     → emitted Python source-compiler.form_source_compile_file()
#     → /tmp/bmf_compiler_expanded/*.expanded.fk
#     → emit_python.py
#     → kernels/python_bmf/emitted/{compiler,python_bmf}.py
#
# compiler.py defines form-bmf-second; python-bmf.py references it. Order:
LOAD_ORDER = ["engine", "source_compiler", "compiler", "python_bmf"]
DEFERRED: list[str] = []

EMITTED_DIR = Path(__file__).parent / "emitted"


def load_bmf_compiler() -> types.ModuleType:
    """Build a single in-memory module containing the entire emitted compiler.
    Returns a `types.ModuleType` whose attributes are every defined name.
    """
    rt = types.ModuleType("bmf_compiler")

    # 1. Seed namespace with host primitives.
    for name in host_primitives.primitive_names():
        setattr(rt, name, getattr(host_primitives, name))
    # Python builtins the emitted code may use without import
    import builtins
    for name in ("range", "len", "min", "max", "abs", "sum", "list", "int",
                 "str", "True", "False", "None", "isinstance", "print", "ord"):
        if hasattr(builtins, name):
            setattr(rt, name, getattr(builtins, name))

    # 2. Execute each emitted module's source in the shared namespace.
    # `from kernels.python_bmf.host_primitives import *` at the top is a no-op
    # here because the primitives are already in rt; subsequent module-level
    # let-bindings can now reference functions defined in earlier modules.
    rt_dict = rt.__dict__
    for stem in LOAD_ORDER:
        src_path = EMITTED_DIR / f"{stem}.py"
        code = compile(src_path.read_text(), str(src_path), "exec")
        exec(code, rt_dict)

    return rt


_cached_rt: types.ModuleType | None = None


def get() -> types.ModuleType:
    """Cached accessor — load once per process."""
    global _cached_rt
    if _cached_rt is None:
        _cached_rt = load_bmf_compiler()
    return _cached_rt
