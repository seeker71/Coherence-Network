#!/usr/bin/env python3
"""Sync Form Blueprint names -> substrate DB as NamedCells.

The Form runtime (Go/Rust/TS kernels) is a standalone offline engine — it
cannot query the substrate DB at load time, so the authored source of truth
for Blueprint names must be a file the kernel can read:
form-stdlib/form-ontology.json (kernel-aligned categories + primitives) and
form-stdlib/blueprint-registry.json (type-99 user-space shapes). `(bp "name")`
in form-ontology-loader.fk resolves against those files.

But the substrate is the body's query surface, and `substrate_named_cells`
(name, domain, blueprint_node_id) is exactly a Blueprint-registry row. Without
this sync the substrate is blind to the legibility layer — it cannot answer
"what is 1.2.99.10 called", "what shape does JSON-OBJECT carry", or surface a
Blueprint name alongside the cells that share its shape. This is the same
two-layer pattern the KB uses (sync_kb_to_db.py): author in files the offline
tools read, project into the DB for querying. The file stays authoritative;
the DB is the reflection.

Each shape becomes one NamedCell in domain "form-blueprint": its canonical
name, the NodeID it carries, and the file that defines it. make_cell is
idempotent on (domain, name), so re-running reconciles rather than duplicates.

Usage:
    python scripts/sync_blueprints_to_substrate.py            # project all
    python scripts/sync_blueprints_to_substrate.py --dry-run  # show, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Make `app` importable in both layouts: dev (package at <repo>/api/app) and
# the prod api container (package at /app/app, with this script at /app/scripts).
for _p in (ROOT, ROOT / "api"):
    sys.path.insert(0, str(_p))

ONTOLOGY = ROOT / "form" / "form-stdlib" / "form-ontology.json"
REGISTRY = ROOT / "form" / "form-stdlib" / "blueprint-registry.json"
DOMAIN = "form-blueprint"


def rows() -> list[dict]:
    """Every named Blueprint shape: (name, pkg, level, type, inst, meaning, src).

    Kernel-aligned categories/primitives live at pkg=1 level=2; type-99 user
    shapes carry their inst from the registry. One row per canonical name —
    aliases stay in the files and resolve through `(bp ...)`; the substrate
    holds one name per shape, its native individuation."""
    out: list[dict] = []
    onto = json.loads(ONTOLOGY.read_text())
    for fam, items in (("category", onto.get("categories", [])),
                       ("primitive", onto.get("primitives", []))):
        for r in items:
            out.append({"name": r["name"], "pkg": 1, "level": 2,
                        "type": r["type"], "inst": r["inst"],
                        "meaning": r.get("note", ""), "src": ONTOLOGY.name,
                        "family": r.get("family", fam)})
    if REGISTRY.exists():
        for r in json.loads(REGISTRY.read_text()).get("blueprints", []):
            defined = r.get("defined_in") or []
            out.append({"name": r["name"], "pkg": r.get("pkg", 1),
                        "level": r.get("level", 2), "type": r.get("type", 99),
                        "inst": r["inst"], "meaning": r.get("meaning", ""),
                        "src": defined[0] if defined else REGISTRY.name,
                        "family": r.get("family", "user")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be projected without writing")
    args = ap.parse_args()

    blueprints = rows()
    if args.dry_run:
        print(f"would project {len(blueprints)} Blueprint name(s) into "
              f"substrate_named_cells (domain '{DOMAIN}'):")
        for r in blueprints[:12]:
            print(f"  {r['pkg']}.{r['level']}.{r['type']}.{r['inst']:<5} "
                  f"{r['name']:<24} ← {r['src']}")
        if len(blueprints) > 12:
            print(f"  … and {len(blueprints) - 12} more")
        return 0

    from app.services.substrate import NodeID, make_cell, lookup_cell  # noqa: E402
    from app.services.unified_db import session as session_scope  # noqa: E402

    written = 0
    with session_scope() as session:
        for r in blueprints:
            node = NodeID(r["pkg"], r["level"], r["type"], r["inst"])
            make_cell(session, name=r["name"], domain=DOMAIN,
                      blueprint=node, source_path=r["src"])
            written += 1
        session.commit()
        # Attest the round-trip on a known shape.
        probe = lookup_cell(session, DOMAIN, "JSON-OBJECT")
    print(f"projected {written} Blueprint name(s) into substrate_named_cells "
          f"(domain '{DOMAIN}')")
    if probe is not None:
        print(f"  verify: JSON-OBJECT → {probe.blueprint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
