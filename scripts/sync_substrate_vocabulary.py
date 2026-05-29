#!/usr/bin/env python3
"""Sync the substrate's own numeric vocabulary -> DB as NamedCells.

`api/app/services/substrate/category.py` is the authoritative registry for
every magic number the substrate uses: Level (compositional depth), the
Blueprint type axes (BType / BNumeric / BAtomic / BBasic / BContainer /
BReference / BRecipe / BDomain) and the Recipe type axes (RType / RBasic and
the per-category instance enums RMath / RCompare / RBlock / RJump / …). They
are named constants in Python — but nothing in the DB knows that `type 12`
is MATH or `domain 6` is MEMORY. So every node's coordinate reads as a bare
number unless you grep the enums.

This projects each enum member into substrate_named_cells (domain
"substrate-vocabulary") at its real NodeID(1, level, type, instance), under a
fully-qualified name (RBasic.MATH, RMath.PLUS, BDomain.MEMORY). After it runs
the substrate is self-describing: lookup_cell("substrate-vocabulary",
"RBasic.MATH") → 1.2.12.0, and a Blueprint number resolves to its meaning.

Coordinate convention (faithful to category.py docstrings + how the substrate
builds NodeIDs — see form_builders.py / kernel.py):
  - A TYPE-axis enum (BType/BBasic level-1/2 blueprint, RType/RBasic recipe)
    names the type field; its cell sits at instance 0 (the UNDEFINED slot at
    level 2 — never a real shape — so the marker collides with nothing).
  - An INSTANCE-axis enum (RMath, RBlock, BAtomic, …) names the instance field
    under a fixed parent type, so RMath.PLUS → (1, 2, RBasic.MATH=12, 1) — a
    real recipe shape.
  - Level names the level field: (1, level, 0, 0).
UNDEFINED=0 members are skipped (the null marker names nothing).

Code-sourced — needs no external files — so it runs unchanged in the prod api
container. Idempotent on (domain, name) via make_cell; re-running reconciles.

Usage:
    python scripts/sync_substrate_vocabulary.py            # project all
    python scripts/sync_substrate_vocabulary.py --dry-run  # show, write nothing
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Make `app` importable in both layouts: dev (package at <repo>/api/app) and
# the prod api container (package at /app/app, with this script at /app/scripts).
for _p in (ROOT, ROOT / "api"):
    sys.path.insert(0, str(_p))

DOMAIN = "substrate-vocabulary"


def axis_spec():
    """Per-enum placement: (enum, axis, level, parent_type).

    axis "type"     → member value fills the TYPE field, instance = 0.
    axis "instance" → member value fills the INSTANCE field under parent_type.
    axis "level"    → member value fills the LEVEL field, type = instance = 0.
    Parent types are read straight from category.py's structure (each R*
    instance enum lives under the RBasic category of the same name; the B*
    instance enums under their BType/BBasic parent)."""
    from app.services.substrate import category as C

    L1, L2 = C.Level.TRIVIAL, C.Level.BASIC
    return [
        # level axis
        (C.Level, "level", None, None),
        # blueprint type axes
        (C.BType, "type", L1, None),
        (C.BBasic, "type", L2, None),
        # blueprint instance axes (under their parent type)
        (C.BNumeric, "instance", L1, C.BType.NUMERIC),
        (C.BAtomic, "instance", L1, C.BType.ATOMIC),
        (C.BContainer, "instance", L2, C.BBasic.CONTAINER),
        (C.BReference, "instance", L2, C.BBasic.REFERENCE),
        (C.BRecipe, "instance", L2, C.BBasic.RECIPE),
        (C.BDomain, "instance", L2, C.BBasic.DOMAIN),
        # recipe type axes
        (C.RType, "type", L1, None),
        (C.RBasic, "type", L2, None),
        (C.Triv, "type", L1, None),
        # recipe instance axes (under their RBasic category)
        (C.RTend, "instance", L2, C.RBasic.TEND),
        (C.RCompose, "instance", L2, C.RBasic.COMPOSE),
        (C.RTransmit, "instance", L2, C.RBasic.TRANSMIT),
        (C.RRealize, "instance", L2, C.RBasic.REALIZE),
        (C.RMath, "instance", L2, C.RBasic.MATH),
        (C.RCompare, "instance", L2, C.RBasic.COMPARE),
        (C.RLogic, "instance", L2, C.RBasic.LOGIC),
        (C.RCond, "instance", L2, C.RBasic.COND),
        (C.RMatch, "instance", L2, C.RBasic.MATCH),
        (C.RBlock, "instance", L2, C.RBasic.BLOCK),
        (C.RJump, "instance", L2, C.RBasic.JUMP),
        (C.RResonance, "instance", L2, C.RBasic.RESONANCE),
        (C.RChoice, "instance", L2, C.RBasic.CHOICE),
        (C.RState, "instance", L2, C.RBasic.STATE),
        (C.RException, "instance", L2, C.RBasic.EXCEPTION),
        (C.RTry, "instance", L2, C.RBasic.TRY),
        (C.RDelegate, "instance", L2, C.RBasic.DELEGATE),
        (C.RReverse, "instance", L2, C.RBasic.REVERSE),
        (C.RCommon, "instance", L2, C.RBasic.COMMON),
        (C.RMethod, "instance", L2, C.RBasic.METHOD),
        (C.RReactive, "instance", L2, C.RBasic.REACTIVE),
        (C.RProjection, "instance", L2, C.RBasic.PROJECTION),
    ]


def rows():
    """One (name, NodeID-tuple) per non-UNDEFINED enum member."""
    from app.services.substrate import NodeID  # noqa: E402

    out = []
    for enum, axis, level, parent in axis_spec():
        for member in enum:
            if member.value == 0:  # UNDEFINED — names nothing
                continue
            if axis == "level":
                node = NodeID(1, int(member.value), 0, 0)
            elif axis == "type":
                node = NodeID(1, int(level), int(member.value), 0)
            else:  # instance
                node = NodeID(1, int(level), int(parent), int(member.value))
            out.append((f"{enum.__name__}.{member.name}", node))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be projected without writing")
    args = ap.parse_args()

    items = rows()
    if args.dry_run:
        print(f"would project {len(items)} substrate-vocabulary name(s) into "
              f"substrate_named_cells (domain '{DOMAIN}'):")
        for name, node in items[:16]:
            print(f"  {node}  {name}")
        if len(items) > 16:
            print(f"  … and {len(items) - 16} more")
        return 0

    from app.services.substrate import make_cell, lookup_cell  # noqa: E402
    from app.services.unified_db import session as session_scope  # noqa: E402

    with session_scope() as session:
        for name, node in items:
            make_cell(session, name=name, domain=DOMAIN, blueprint=node,
                      source_path="api/app/services/substrate/category.py")
        session.commit()
        probe = lookup_cell(session, DOMAIN, "RBasic.MATH")
        probe2 = lookup_cell(session, DOMAIN, "BDomain.MEMORY")
    print(f"projected {len(items)} substrate-vocabulary name(s) into "
          f"substrate_named_cells (domain '{DOMAIN}')")
    if probe:
        print(f"  verify: RBasic.MATH → {probe.blueprint}")
    if probe2:
        print(f"  verify: BDomain.MEMORY → {probe2.blueprint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
