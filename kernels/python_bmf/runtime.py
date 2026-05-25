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
# CPython's default recursion limit (1000) trips on engine.fk-class workloads
# where the Form kernel's iterative Recipe walker continues. Raising it lets
# the emitted compiler match the kernel's reach. The cost is stack memory, not
# correctness — Python's per-frame overhead is modest at these depths.
sys.setrecursionlimit(200_000)


# Load order matches Form kernel's prepare_sources for the BMF compiler:
# Loaded in dependency order. The two we can fully load today are engine and
# source_compiler. compiler.py and python_bmf.py reference symbols from
# section [...] grammar blocks that the source-compiler expands at .fk-load
# time — those expansions don't yet land via the emit_python path, so those
# two modules' module-level execution fails on undefined symbols. We load
# what works; the loader is honest about which surfaces are live.
LOAD_ORDER = ["engine", "source_compiler"]
DEFERRED = ["python_bmf", "compiler"]  # need section-grammar expansion first

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
