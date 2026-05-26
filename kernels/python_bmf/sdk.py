"""Substrate primitives the emitted Python compiler needs from Form.

Python lacks five things directly: content-addressed NodeIDs, reversible
cell metadata, structural interning, `.fkb` binary read/write, and
symbol/source lens lookup. This module provides exactly those — nothing
more. No rule logic, no parser logic, no emit logic lives here.

Boundary discipline (enforced by tests/test_sdk_boundary.py once shipped):
- No `eval` / `exec`.
- No imports from `kernels.python_bmf.rules`, `parser`, or `compiler`.
- File stays under 400 lines.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# ──────────────────────────────────────────────────────────────────────
# NodeID — content-addressed structural identity (pkg, level, type, inst)
# ──────────────────────────────────────────────────────────────────────
# Mirrors form/form-stdlib/core.fk's make_nodeid and the four-part shape
# used across kernels (api/app/services/substrate/category.py).


@dataclass(frozen=True, order=True)
class NodeID:
    pkg: int
    level: int
    type: int
    inst: int

    def __str__(self) -> str:
        return f"@{self.pkg}.{self.level}.{self.type}.{self.inst}"

    @classmethod
    def parse(cls, s: str) -> "NodeID":
        body = s.lstrip("@")
        parts = body.split(".")
        if len(parts) != 4:
            raise ValueError(f"NodeID expects 4 parts, got {s!r}")
        return cls(*(int(p) for p in parts))


def make_nodeid(pkg: int, level: int, type_: int, inst: int) -> NodeID:
    return NodeID(pkg, level, type_, inst)


# ──────────────────────────────────────────────────────────────────────
# Source spans — origin of a token / object inside source text
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceSpan:
    path: str
    start_offset: int
    end_offset: int
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @classmethod
    def empty(cls) -> "SourceSpan":
        return cls("", 0, 0, 0, 0, 0, 0)


# ──────────────────────────────────────────────────────────────────────
# BmfObject — base for every captured / emitted structural item
# ──────────────────────────────────────────────────────────────────────
# Mirrors compiler-object in form/form-stdlib/compiler.fk: kind + value
# + source + inverse. The inverse callable is the reversible cell:
# applying it recovers the source object the structure was built from.


@dataclass
class BmfObject:
    kind: str
    value: Any
    source: Any = None
    nodeid: NodeID | None = None
    span: SourceSpan = field(default_factory=SourceSpan.empty)
    inverse: Any = None  # callable: BmfObject -> source

    def undo(self) -> Any:
        if self.inverse is None:
            return self.source
        return self.inverse(self)


def identity_inverse(obj: BmfObject) -> Any:
    return obj.source


# ──────────────────────────────────────────────────────────────────────
# Content-address interning
# ──────────────────────────────────────────────────────────────────────
# Structural identity by content. Two objects with the same (kind, value
# shape, children NodeIDs) get the same NodeID. Matches the kernel's
# intern_node behavior at a small scale.


_INTERN_TABLE: dict[str, NodeID] = {}
_NEXT_LOCAL_INST: dict[tuple[int, int, int], int] = {}
_INTERN_PKG = 1
_INTERN_LEVEL = 2
_INTERN_TYPE_LOCAL = 99  # the "local artifact" type used in python-bmf.fk


def _content_key(kind: str, value: Any, children: Iterable[NodeID]) -> str:
    payload = {
        "kind": kind,
        "value": _canonical(value),
        "children": [str(c) for c in children],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _canonical(v: Any) -> Any:
    if isinstance(v, NodeID):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [_canonical(x) for x in v]
    if isinstance(v, dict):
        return {k: _canonical(x) for k, x in sorted(v.items())}
    if isinstance(v, BmfObject):
        return {"$bmf": v.kind, "value": _canonical(v.value)}
    return v


def intern(kind: str, value: Any, children: Iterable[NodeID] = ()) -> NodeID:
    """Content-address a structural composite. Same content → same NodeID."""
    key = _content_key(kind, value, list(children))
    cached = _INTERN_TABLE.get(key)
    if cached is not None:
        return cached
    bucket = (_INTERN_PKG, _INTERN_LEVEL, _INTERN_TYPE_LOCAL)
    inst = _NEXT_LOCAL_INST.get(bucket, 1)
    _NEXT_LOCAL_INST[bucket] = inst + 1
    nid = NodeID(_INTERN_PKG, _INTERN_LEVEL, _INTERN_TYPE_LOCAL, inst)
    _INTERN_TABLE[key] = nid
    return nid


def intern_trivial_int(n: int) -> NodeID:
    """Trivial Int leaf — level=1, type=1 in the kernel's lattice."""
    return NodeID(1, 1, 1, n)


def intern_trivial_string(s: str) -> NodeID:
    """Trivial String leaf — content-addressed by hash; instance is hash truncation."""
    digest = hashlib.sha256(s.encode()).hexdigest()
    inst = int(digest[:8], 16)
    return NodeID(1, 1, 2, inst)


def intern_trivial_bool(b: bool) -> NodeID:
    return NodeID(1, 1, 3, 1 if b else 0)


# ──────────────────────────────────────────────────────────────────────
# .fkb binary read/write
# ──────────────────────────────────────────────────────────────────────
# Minimal portable shape:
#   magic: 4 bytes 'FKB1'
#   version: u32
#   node_count: u32
#   for each node:
#     NodeID: 4 × u32  (pkg, level, type, inst)
#     kind_len: u16
#     kind: utf-8 bytes
#     value_len: u32
#     value: utf-8 JSON
#     child_count: u32
#     for each child: NodeID
# This matches enough of the kernel's serialization shape that the diff
# tool can compare structure; once the Form kernels emit canonical .fkb
# we can swap to that and keep this as the reader.


MAGIC = b"FKB1"
VERSION = 1


def write_fkb(path: str | Path, nodes: list[dict]) -> None:
    """Write a list of {nodeid, kind, value, children} dicts as .fkb."""
    buf = bytearray()
    buf += MAGIC
    buf += struct.pack("<I", VERSION)
    buf += struct.pack("<I", len(nodes))
    for n in nodes:
        nid: NodeID = n["nodeid"]
        buf += struct.pack("<IIII", nid.pkg, nid.level, nid.type, nid.inst)
        kind_bytes = n["kind"].encode("utf-8")
        buf += struct.pack("<H", len(kind_bytes)) + kind_bytes
        value_bytes = json.dumps(_canonical(n.get("value"))).encode("utf-8")
        buf += struct.pack("<I", len(value_bytes)) + value_bytes
        children: list[NodeID] = n.get("children", [])
        buf += struct.pack("<I", len(children))
        for c in children:
            buf += struct.pack("<IIII", c.pkg, c.level, c.type, c.inst)
    Path(path).write_bytes(bytes(buf))


def read_fkb(path: str | Path) -> list[dict]:
    data = Path(path).read_bytes()
    if data[:4] != MAGIC:
        raise ValueError(f"{path!s}: not an FKB1 binary (magic={data[:4]!r})")
    pos = 4
    (_version,) = struct.unpack_from("<I", data, pos)
    pos += 4
    (count,) = struct.unpack_from("<I", data, pos)
    pos += 4
    nodes: list[dict] = []
    for _ in range(count):
        pkg, level, type_, inst = struct.unpack_from("<IIII", data, pos)
        pos += 16
        (kind_len,) = struct.unpack_from("<H", data, pos)
        pos += 2
        kind = data[pos : pos + kind_len].decode("utf-8")
        pos += kind_len
        (value_len,) = struct.unpack_from("<I", data, pos)
        pos += 4
        value_bytes = data[pos : pos + value_len]
        pos += value_len
        value = json.loads(value_bytes) if value_bytes else None
        (child_count,) = struct.unpack_from("<I", data, pos)
        pos += 4
        children = []
        for _c in range(child_count):
            cp, cl, ct, ci = struct.unpack_from("<IIII", data, pos)
            pos += 16
            children.append(NodeID(cp, cl, ct, ci))
        nodes.append(
            {
                "nodeid": NodeID(pkg, level, type_, inst),
                "kind": kind,
                "value": value,
                "children": children,
            }
        )
    return nodes


# ──────────────────────────────────────────────────────────────────────
# Symbol / source lens lookup
# ──────────────────────────────────────────────────────────────────────
# Sibling .fkl JSON file (lens) the Form kernels can write alongside
# .fkb. Maps NodeID → {"symbol": "...", "span": SourceSpan}. The lens is
# the only place readable names attach to structural identity.


@dataclass
class Lens:
    entries: dict[str, dict] = field(default_factory=dict)

    def symbol_for(self, nid: NodeID) -> str | None:
        e = self.entries.get(str(nid))
        return e.get("symbol") if e else None

    def span_for(self, nid: NodeID) -> SourceSpan | None:
        e = self.entries.get(str(nid))
        if not e or "span" not in e:
            return None
        s = e["span"]
        return SourceSpan(**s)

    @classmethod
    def load(cls, path: str | Path) -> "Lens":
        p = Path(path)
        if not p.exists():
            return cls()
        return cls(entries=json.loads(p.read_text()))

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.entries, indent=2, sort_keys=True))


def lens_path_for(fkb_path: str | Path) -> Path:
    p = Path(fkb_path)
    return p.with_suffix(".fkl")


__all__ = [
    "NodeID",
    "make_nodeid",
    "SourceSpan",
    "BmfObject",
    "identity_inverse",
    "intern",
    "intern_trivial_int",
    "intern_trivial_string",
    "intern_trivial_bool",
    "write_fkb",
    "read_fkb",
    "Lens",
    "lens_path_for",
    "MAGIC",
    "VERSION",
]
