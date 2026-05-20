"""Probe a single concept's CTOR shape — what categories appear, what
keys are recoverable. Debug aid for `sense.py`'s field-set signature.

Usage: python3 experiments/ctor-shape-signature-v0/probe.py lc-pulse
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate.kernel import NodeID  # noqa: E402
from app.services.substrate.orm import (  # noqa: E402
    SubstrateNamedCellORM,
    SubstrateNodeORM,
)
from app.services.substrate.substrate_strings import (  # noqa: E402
    lookup_string_value,
)
from app.services.unified_db import session as session_scope  # noqa: E402


def _row(session, nid: NodeID):
    return (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=nid.package, level=nid.level,
            type_=nid.type_, instance=nid.instance,
        )
        .one_or_none()
    )


def _parse(serialized: str):
    chunks = serialized.split("+")
    parts = [tuple(int(x) for x in c.split(".")) for c in chunks]
    return NodeID(*parts[0]), [NodeID(*p) for p in parts[1:]]


def walk(session, nid: NodeID, depth: int = 0, max_depth: int = 4):
    indent = "  " * depth
    row = _row(session, nid)
    if row is None:
        s = lookup_string_value(session, nid.instance) if nid.type_ == 6 else None
        suffix = f"  «{s}»" if s else ""
        print(f"{indent}LEAF {nid}{suffix}")
        return
    cat, children = _parse(row.serialized)
    print(f"{indent}NODE {nid}  cat={cat}  children={len(children)}")
    if depth >= max_depth:
        print(f"{indent}  (truncated)")
        return
    for c in children:
        walk(session, c, depth + 1, max_depth)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "lc-pulse"
    with session_scope() as session:
        row = (
            session.query(SubstrateNamedCellORM)
            .filter_by(domain="concept", name=target)
            .one_or_none()
        )
        if row is None:
            print(f"{target!r} not in substrate")
            return 1
        if row.ctor_recipe_node_id is None:
            print(f"{target!r} has no CTOR")
            return 1
        ctor_row = (
            session.query(SubstrateNodeORM)
            .filter_by(node_id=row.ctor_recipe_node_id)
            .one_or_none()
        )
        if ctor_row is None:
            print(f"{target!r} CTOR node missing")
            return 1
        nid = NodeID(
            ctor_row.package, ctor_row.level,
            ctor_row.type_, ctor_row.instance,
        )
        print(f"{target} CTOR root: {nid}")
        walk(session, nid, max_depth=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
