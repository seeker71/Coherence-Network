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

Coverage is every shape the stdlib names at any coordinate — not only type-99.
Beyond the JSON registry it sweeps all non-test .fk files for literal
make_nodeid bindings, so the package-8 source-compiler shapes (8.45.*,
FSC-REPO-* / BMF-*-REF) and the form-side ACCESS/WRITE instances (1.2.15.x /
1.2.16.x) get names too. Paired with sync_substrate_vocabulary.py (the
category.py type alphabet), no Blueprint coordinate the body uses stays a
bare number in the DB.

Usage:
    python scripts/sync_blueprints_to_substrate.py            # project all
    python scripts/sync_blueprints_to_substrate.py --dry-run  # show, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Make `app` importable in both layouts: dev (package at <repo>/api/app) and
# the prod api container (package at /app/app, with this script at /app/scripts).
for _p in (ROOT, ROOT / "api"):
    sys.path.insert(0, str(_p))

STDLIB = ROOT / "form" / "form-stdlib"
ONTOLOGY = STDLIB / "form-ontology.json"
REGISTRY = STDLIB / "blueprint-registry.json"
DOMAIN = "form-blueprint"

# Per-dialect vocabulary prefixes — a local name carrying one is a synonym for
# a shared shape, not the canonical name for it (PY-PLUS/GO-PLUS/… all = add).
DIALECT_PREFIXES = (
    "PY-", "GO-", "RS-", "TS-", "JS-", "SQL-", "CSS-", "HTML-", "XML-",
    "YAML-", "Y-", "AU-", "VID-", "IMG-", "MDL-", "E-JSON-", "JSON-BNF-",
    "CF-", "SE-", "SR-", "TE-", "UE-", "U-", "F-", "MOD-",
)
# Both binding forms: `(let NAME (make_nodeid p l t i))` and the 0-arg getter.
NAMED_NODE_RE = re.compile(
    r"\(\s*(?:let\s+([A-Za-z0-9?_+*<>=/.-]+)|defn\s+"
    r"([A-Za-z0-9?_+*<>=/.-]+)\s+\(\s*\))\s+\(\s*make_nodeid\s+"
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\)"
)


def _canonical(names: set[str]) -> str:
    plain = [n for n in names if not n.startswith(DIALECT_PREFIXES)]
    return sorted(plain or names, key=lambda s: (len(s), s))[0]


def harvest_fk() -> dict[tuple, dict]:
    """Every shape any non-test .fk file names with a literal make_nodeid, at
    ANY coordinate — not only type-99. Groups per NodeID, picks one canonical
    name. This is what reaches the package-8 source-compiler shapes (8.45.*)
    and the form-side ACCESS/WRITE instances (1.2.15.x / 1.2.16.x) that the
    JSON registry and category.py vocabulary don't carry."""
    by_node: dict[tuple, dict] = {}
    for f in sorted(STDLIB.rglob("*.fk")):
        rel = str(f.relative_to(ROOT))
        if "/tests/" in rel or rel.endswith("-band.fk"):
            continue  # test-local sentinels (9.9.9, 1.2.101.*) name nothing real
        text = f.read_text()
        for m in NAMED_NODE_RE.finditer(text):
            name = m.group(1) or m.group(2)
            key = tuple(int(m.group(i)) for i in range(3, 7))
            ent = by_node.setdefault(key, {"names": set(), "src": rel})
            ent["names"].add(name)
    return by_node


def rows() -> list[dict]:
    """Every named Blueprint shape: (name, pkg, level, type, inst, src).

    Three sources, in precedence order so curated names win:
      1. form-ontology.json categories + primitives (kernel-aligned).
      2. blueprint-registry.json type-99 user shapes (curated names/meanings).
      3. a sweep of every other .fk-named shape at any coordinate — the
         package-8 and ACCESS/WRITE-instance shapes neither file carries.
    One row per NodeID coordinate; the substrate holds one name per shape."""
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(name, pkg, level, type_, inst, src):
        key = (pkg, level, type_, inst)
        if key in seen:
            return
        seen.add(key)
        out.append({"name": name, "pkg": pkg, "level": level,
                    "type": type_, "inst": inst, "src": src})

    onto = json.loads(ONTOLOGY.read_text())
    for items in (onto.get("categories", []), onto.get("primitives", [])):
        for r in items:
            add(r["name"], 1, 2, r["type"], r["inst"], ONTOLOGY.name)
    if REGISTRY.exists():
        for r in json.loads(REGISTRY.read_text()).get("blueprints", []):
            d = r.get("defined_in") or []
            add(r["name"], r.get("pkg", 1), r.get("level", 2),
                r.get("type", 99), r["inst"], d[0] if d else REGISTRY.name)
    for key, ent in harvest_fk().items():
        add(_canonical(ent["names"]), *key, ent["src"])
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
