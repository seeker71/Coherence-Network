"""Python bindings for the Form kernel host primitives the emitted compiler calls.

The emitted Python (in `kernels/python_bmf/emitted/`) is a faithful native-Python
translation of the Form BMF compiler. The Form code references kernel host calls
(cell, bmf_object, str_concat, make_nodeid, intern_node, file I/O, list head/
tail/cons, ...). This module provides the smallest honest Python implementations
of those primitives so the emitted compiler can actually execute.

Discipline:
- These are PRIMITIVES, not the BMF rules or the parser. No language-specific
  logic lives here.
- Implementations stay short and direct. Where Python has a native equivalent,
  we use it. Where it doesn't (NodeID, content-address intern, reversible
  cells), we provide the smallest faithful surface.
- The SDK boundary stays: `sdk.py` for the data types (NodeID, BmfObject),
  `host_primitives.py` for the function bindings the emitted code calls.

Usage:
    from kernels.python_bmf.host_primitives import install_into
    from kernels.python_bmf.emitted import engine  # symbols still unbound
    install_into(engine)                            # binds the primitives
    # now engine.bmf_object(...), engine.str_concat(...), etc. work
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .sdk import NodeID, intern as sdk_intern, intern_trivial_int as _intern_int, \
    intern_trivial_string as _intern_str


# ──────────────────────────────────────────────────────────────────────
# Cell — the reversible BMF object base.
# Matches form/form-stdlib/core.fk's cell shape: (kind value origin inverse).
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Cell:
    kind: str
    value: Any
    origin: Any = None
    inverse: Callable[["Cell"], Any] | None = None

    def __repr__(self) -> str:
        v = repr(self.value)
        return f"Cell({self.kind!r}, {v if len(v) < 60 else v[:57] + '...'})"


def cell(kind, value, origin=None, inverse=None) -> Cell:
    return Cell(kind, value, origin, inverse)


def is_cell(x) -> bool:
    return isinstance(x, Cell)


def cell_kind(c: Cell) -> str: return c.kind
def cell_value(c: Cell) -> Any: return c.value
def cell_origin(c: Cell) -> Any: return c.origin
def cell_inverse(c: Cell) -> Any: return c.inverse
def cell_undo(c: Cell) -> Any:
    return c.inverse(c) if c.inverse is not None else c.origin


# ──────────────────────────────────────────────────────────────────────
# Strings
# ──────────────────────────────────────────────────────────────────────


def str_concat(a, b) -> str:
    return f"{a}{b}"


def str_eq(a, b) -> bool:
    return a == b


def str_len(s) -> int:
    return len(s)


def substring(s: str, a: int, b: int) -> str:
    return s[a:b]


def char_at(s: str, i: int) -> str:
    if 0 <= i < len(s):
        return s[i]
    return ""


def str_to_int(s: str) -> int:
    return int(s)


def int_to_str(n: int) -> str:
    return str(n)


# ──────────────────────────────────────────────────────────────────────
# Lists — Form lists are linked-cons-style but we represent as Python lists.
# Conversion is identity at the boundary; head/tail/cons behave naturally.
# ──────────────────────────────────────────────────────────────────────


def empty():
    return []


def is_nil(x) -> bool:
    return x is None or (isinstance(x, (list, tuple)) and len(x) == 0)


def head(xs):
    return xs[0] if xs else None


def tail(xs):
    return xs[1:] if xs else []


def cons(x, xs):
    return [x] + (list(xs) if xs else [])


def append(xs, ys):
    return list(xs or []) + list(ys or [])


def reverse_list(xs):
    return list(reversed(xs or []))


def reverse(xs):
    return list(reversed(xs or []))


def foldl(fn, init, xs):
    acc = init
    for x in xs or []:
        acc = fn(acc, x)
    return acc


def take(xs, n):
    return list(xs)[:n] if xs else []


# ──────────────────────────────────────────────────────────────────────
# NodeIDs and intern
# ──────────────────────────────────────────────────────────────────────


def make_nodeid(pkg, level, type_, inst):
    return NodeID(pkg, level, type_, inst)


def intern_node(kind, value, *children):
    """Generic interning: kind + value composite, children as Recipe NodeIDs."""
    return sdk_intern(str(kind), value, children)


def intern_trivial_int(n):
    return _intern_int(int(n))


def intern_trivial_string(s):
    return _intern_str(str(s))


def node_eq(a, b) -> bool:
    return a == b


def node_value(n):
    return n.inst if isinstance(n, NodeID) else n


def node_children(n):
    # In a richer integration this would consult the Form substrate; for now
    # NodeIDs we make here carry no child list at this surface — emitted
    # compiler code that needs children would route through the substrate.
    return []


# ──────────────────────────────────────────────────────────────────────
# File IO
# ──────────────────────────────────────────────────────────────────────


def read_file(path) -> str:
    return Path(path).read_text()


def read_file_slice(path, start, length) -> str:
    return Path(path).read_text()[start : start + length]


def file_byte_at(path, i) -> int:
    data = Path(path).read_bytes()
    return data[i] if 0 <= i < len(data) else 0


def file_size(path) -> int:
    p = Path(path)
    return p.stat().st_size if p.exists() else 0


def write_file_text(path, text) -> int:
    Path(path).write_text(text)
    return len(text)


def write_file_bytes(path, data) -> int:
    Path(path).write_bytes(data)
    return len(data)


# ──────────────────────────────────────────────────────────────────────
# BMF objects — the structural envelopes the engine builds and consumes.
# Same shape as Cell with a `bmf-*` kind convention.
# ──────────────────────────────────────────────────────────────────────


def bmf_object(kind, value, origin=None, inverse=None) -> Cell:
    return Cell(kind, value, origin, inverse)


def is_bmf_object(x) -> bool:
    return isinstance(x, Cell)


def bmf_object_kind(c: Cell) -> str: return c.kind
def bmf_object_value(c: Cell) -> Any: return c.value


def bmf_collection(items) -> Cell:
    return Cell("bmf-collection", list(items) if items else [])


def bmf_collection_items(c: Cell):
    return c.value if isinstance(c, Cell) else (list(c) if c else [])


def bmf_identity_inverse(obj):
    return obj.origin if isinstance(obj, Cell) else obj


def bmf_empty(n):
    return Cell("bmf-empty", n)


# ──────────────────────────────────────────────────────────────────────
# Stubs for advanced primitives the emitted compiler may name.
# These raise NotImplementedError so missing functionality is visible
# rather than silently absent.
# ──────────────────────────────────────────────────────────────────────


def _unimpl(name):
    def stub(*args, **kwargs):
        raise NotImplementedError(f"host primitive '{name}' not yet implemented in Python")
    return stub


# Pattern matching / object rules (large surface; deferred to host_primitives_advanced)
action = _unimpl("action")
parse = _unimpl("parse")
emit = _unimpl("emit")


# ──────────────────────────────────────────────────────────────────────
# Installation: bind primitives as module-level names in an emitted module.
# ──────────────────────────────────────────────────────────────────────


_PRIMITIVES: dict[str, Any] = {}


def _gather() -> None:
    """Collect every public name in this module that looks like a primitive."""
    here = sys.modules[__name__]
    for name in dir(here):
        if name.startswith("_") or name in ("annotations", "Path", "NodeID", "Cell"):
            continue
        obj = getattr(here, name)
        if callable(obj) or isinstance(obj, type):
            _PRIMITIVES[name] = obj


_gather()


def install_into(module) -> int:
    """Bind every host primitive into `module` for any name not already defined.
    Returns the count of primitives bound."""
    count = 0
    for name, obj in _PRIMITIVES.items():
        if not hasattr(module, name):
            setattr(module, name, obj)
            count += 1
    # ord/print/len/etc. — Python builtins the emitted code may call without
    # a from-import — are already resolved at call site via __builtins__.
    return count


def primitive_names() -> list[str]:
    return sorted(_PRIMITIVES.keys())
