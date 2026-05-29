#!/usr/bin/env python3
"""Scan Form (.fk) sources for `make_nodeid` Blueprint literals and measure
their legibility against the central registry.

The registry doc (form/user-blueprint-registry.md) named the problem:
hundreds of opaque `(make_nodeid 1 2 99 NNNN)` numbers, each often
re-declared under a different local name in a different file. This scanner
is the proprioception tool that doc calls for. It reads the single source
of truth — form/form-stdlib/form-ontology.json (categories + primitives +
user_blueprints) — and tells the body where Form code still names a shape
by raw number when a registered name exists, where one number wears many
names (synonyms), and where one name points at different numbers (drift).

Usage:
    python3 scripts/scan_form_blueprints.py            # full report
    python3 scripts/scan_form_blueprints.py --check    # CI: nonzero on drift
    python3 scripts/scan_form_blueprints.py --json      # machine-readable

A NodeID is the 4-tuple (pkg, level, type, inst). Registered shapes live at
pkg=1, level=2 (Basic). The registry names them so `.fk` code can reference
a binding from form-ontology-loader.fk instead of writing the number.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORM_ROOT = ROOT / "form" / "form-stdlib"
ONTOLOGY = FORM_ROOT / "form-ontology.json"
# User-space (type-99) registry — the single source of truth for shapes the
# kernel does not dispatch on. Code-derived, curated, scanner-verified. It
# replaces the hand-maintained markdown table in form/user-blueprint-registry.md
# (which drifted: that doc said 1870=ARRIVAL while code says 1870=UUID).
REGISTRY = FORM_ROOT / "blueprint-registry.json"

# Dialect-vocabulary prefixes — a local name carrying one of these is a
# per-dialect synonym for a shared shape, not the canonical name for it.
DIALECT_PREFIXES = (
    "PY-", "GO-", "RS-", "TS-", "JS-", "SQL-", "CSS-", "HTML-", "XML-",
    "YAML-", "Y-", "AU-", "VID-", "IMG-", "MDL-", "E-JSON-", "JSON-BNF-",
    "CF-", "SE-", "SR-", "TE-", "UE-", "U-", "F-", "MOD-",
)

# `(make_nodeid 1 2 12 1)` and `(make_nodeid (1 2 12 1))`-free 4-int form.
NODEID_RE = re.compile(
    r"make_nodeid\s*\(?\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\)?"
)
# A local symbolic binding to a number, in either form:
#   (let NAME (make_nodeid 1 2 12 1))
#   (defn NAME () (make_nodeid 1 2 12 1))
LET_RE = re.compile(
    r"\(\s*(?:let\s+([A-Za-z0-9?_+*<>=/.-]+)|defn\s+"
    r"([A-Za-z0-9?_+*<>=/.-]+)\s+\(\s*\))\s+\(\s*make_nodeid\s+"
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\)"
)
Key = tuple  # (pkg, level, type, inst)


def load_registry() -> dict[Key, dict]:
    """name-by-NodeID, drawn from the ontology's categories, primitives, and
    user_blueprints. Each entry: {canonical, family, meaning, aliases}."""
    data = json.loads(ONTOLOGY.read_text())
    reg: dict[Key, dict] = {}

    def add(key: Key, canonical: str, family: str, meaning: str, aliases=None):
        reg[key] = {
            "canonical": canonical,
            "family": family,
            "meaning": meaning,
            "aliases": list(aliases or []),
        }

    for row in data.get("categories", []):
        key = (1, 2, row["type"], row["inst"])
        add(key, row["name"], "category", row.get("note", ""))
    for row in data.get("primitives", []):
        key = (1, 2, row["type"], row["inst"])
        add(key, row["name"], row.get("family", "primitive"), row.get("note", ""))
    for row in load_user_blueprints():
        # user_blueprints are pkg=1, level=2, type=99 by convention; a row may
        # override pkg/level/type for the rare non-99 shared shape.
        key = (
            row.get("pkg", 1),
            row.get("level", 2),
            row.get("type", 99),
            row["inst"],
        )
        add(key, row["name"], row.get("family", "user"),
            row.get("meaning", ""), row.get("aliases"))
    return reg


def load_user_blueprints() -> list[dict]:
    if not REGISTRY.exists():
        return []
    return json.loads(REGISTRY.read_text()).get("blueprints", [])


def scan() -> dict:
    reg = load_registry()
    sites: list[dict] = []          # every make_nodeid literal
    num_to_names: dict[Key, set] = collections.defaultdict(set)
    name_to_nums: dict[str, set] = collections.defaultdict(set)

    for f in sorted(FORM_ROOT.rglob("*.fk")):
        rel = f.relative_to(ROOT)
        is_test = "/tests/" in str(rel) or str(rel).endswith("-band.fk")
        text = f.read_text()
        for m in LET_RE.finditer(text):
            name = m.group(1) or m.group(2)
            key = tuple(int(m.group(i)) for i in range(3, 7))
            num_to_names[key].add(name)
            name_to_nums[name].add(key)
        for m in NODEID_RE.finditer(text):
            key = tuple(int(m.group(i)) for i in range(1, 5))
            line = text.count("\n", 0, m.start()) + 1
            sites.append({
                "file": str(rel),
                "line": line,
                "key": key,
                "test": is_test,
                "registered": key in reg,
            })

    # drift: a name bound to more than one distinct number.
    collisions = {n: sorted(v) for n, v in name_to_nums.items() if len(v) > 1}
    # synonyms: a number wearing more than one local name.
    synonyms = {k: sorted(v) for k, v in num_to_names.items() if len(v) > 1}
    # type-99 numbers used in PRODUCTION but absent from the registry. Test
    # files carry local sentinels (7700, 8888, …) that name nothing real and
    # are deliberately excluded from the registry, so they don't count here.
    type99 = {s["key"] for s in sites if s["key"][2] == 99 and not s["test"]}
    unregistered_99 = sorted(k for k in type99 if k not in reg)

    return {
        "reg": reg,
        "sites": sites,
        "num_to_names": num_to_names,
        "name_to_nums": name_to_nums,
        "collisions": collisions,
        "synonyms": synonyms,
        "unregistered_99": unregistered_99,
    }


def fmt_key(k: Key) -> str:
    return ".".join(map(str, k))


def best_name(names) -> str:
    """The canonical name for a number: prefer one with no dialect prefix,
    then the shortest, then alphabetical."""
    plain = [n for n in names if not n.startswith(DIALECT_PREFIXES)]
    pool = plain or list(names)
    return sorted(pool, key=lambda s: (len(s), s))[0]


def _ontology_coords() -> set:
    """Coordinates the kernel owns (form-ontology.json categories/primitives).
    These resolve through bp already; the registry covers everything else."""
    data = json.loads(ONTOLOGY.read_text())
    out = set()
    for items in (data.get("categories", []), data.get("primitives", [])):
        for r in items:
            out.add((1, 2, r["type"], r["inst"]))
    return out


def emit_registry() -> dict:
    """Generate the Blueprint registry from what the code actually declares —
    every coordinate family the stdlib names, not just type-99. Code-derived
    so it cannot drift from a hand-edited table. Captures, per NodeID: full
    (pkg, level, type, inst), canonical name, harvested meaning (densest
    trailing comment), aliases, and defining files. Excludes test-local
    sentinels and the kernel-owned categories/primitives (those live in
    form-ontology.json)."""
    # Both binding forms, at ANY coordinate:
    #   (let NAME (make_nodeid P L T I))   /   (defn NAME () (make_nodeid P L T I))
    let_re = re.compile(
        r"\(\s*(?:let\s+([A-Za-z0-9?_+*<>=/.-]+)|defn\s+"
        r"([A-Za-z0-9?_+*<>=/.-]+)\s+\(\s*\))\s+\(\s*make_nodeid\s+"
        r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\)[^\n;]*(?:;+\s*(.*))?"
    )
    owned = _ontology_coords()
    by_key: dict[tuple, dict] = collections.defaultdict(
        lambda: {"names": collections.Counter(),
                 "comments": collections.Counter(),
                 "files": set()})
    for f in sorted(FORM_ROOT.rglob("*.fk")):
        rel = str(f.relative_to(ROOT))
        if "/tests/" in rel or rel.endswith("-band.fk"):
            continue  # test-local sentinels name nothing real
        for m in let_re.finditer(f.read_text()):
            name = m.group(1) or m.group(2)
            key = tuple(int(m.group(i)) for i in range(3, 7))
            comment = (m.group(7) or "").strip()
            if key in owned:
                continue
            by_key[key]["names"][name] += 1
            by_key[key]["files"].add(rel)
            if comment:
                by_key[key]["comments"][comment] += 1
    rows = []
    for key in sorted(by_key):
        pkg, level, type_, inst = key
        info = by_key[key]
        canon = best_name(info["names"])
        meaning = (info["comments"].most_common(1)[0][0]
                   if info["comments"] else "")
        aliases = sorted(a for a in info["names"] if a != canon)
        rows.append({
            "pkg": pkg, "level": level, "type": type_, "inst": inst,
            "name": canon,
            "meaning": meaning,
            "aliases": aliases,
            "reuse": sum(info["names"].values()),
            "defined_in": sorted(info["files"]),
        })
    return {
        "_note": ("Blueprint registry — the single source of truth for every "
                  "shape the kernel does not dispatch on (kernel-owned "
                  "categories/primitives live in form-ontology.json). Generated "
                  "from code by scripts/scan_form_blueprints.py --emit-registry, "
                  "then curated. Each row carries the full NodeID "
                  "(pkg, level, type, inst). form-ontology-loader.fk binds these "
                  "names so .fk code references a name via (bp \"name\"), never "
                  "the raw number. To add a shape: add a row here, then "
                  "(bp \"name\") in code."),
        "blueprints": rows,
    }


def report(s: dict) -> None:
    sites = s["sites"]
    prod = [x for x in sites if not x["test"]]
    print(f"Form Blueprint scan — {len(sites)} make_nodeid literals "
          f"({len(prod)} in production, {len(sites) - len(prod)} in tests)")
    distinct = {x["key"] for x in sites}
    print(f"  distinct NodeIDs: {len(distinct)}   "
          f"registered: {len(s['reg'])}   "
          f"unregistered type-99: {len(s['unregistered_99'])}")
    print()

    if s["collisions"]:
        print(f"⚠  name drift — {len(s['collisions'])} name(s) bound to >1 NodeID:")
        for n, keys in sorted(s["collisions"].items()):
            print(f"   {n}: {[fmt_key(k) for k in keys]}")
        print()

    # production synonyms for registered shapes: each is a redundant local
    # redefinition that could reference the loader binding instead.
    prod_keys = {x["key"] for x in prod}
    redundant = {k: v for k, v in s["synonyms"].items()
                 if k in s["reg"] and k in prod_keys}
    if redundant:
        print(f"○  registered shapes re-named locally in production "
              f"({len(redundant)} NodeIDs) — reference the registry instead:")
        for k in sorted(redundant, key=lambda k: -len(redundant[k]))[:20]:
            canon = s["reg"][k]["canonical"]
            print(f"   {fmt_key(k)} [{canon}]: {len(redundant[k])} aliases "
                  f"{redundant[k]}")
        print()

    if s["unregistered_99"]:
        print(f"○  type-99 numbers in source but absent from registry "
              f"({len(s['unregistered_99'])}):")
        for k in s["unregistered_99"]:
            names = sorted(s["num_to_names"].get(k, []))
            hint = f"  named locally: {names}" if names else "  (unnamed)"
            print(f"   {fmt_key(k)}{hint}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit nonzero if name drift exists (CI/wellness)")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable scan result")
    ap.add_argument("--emit-registry", action="store_true",
                    help="(re)generate form-stdlib/blueprint-registry.json "
                         "from code, preserving curated meanings")
    args = ap.parse_args()

    if args.emit_registry:
        generated = emit_registry()
        def coord(r):
            return (r.get("pkg", 1), r.get("level", 2), r.get("type", 99), r["inst"])
        # Union with the existing registry: once a file migrates its definition
        # to (bp "name"), the harvest no longer finds a make_nodeid literal for
        # that coordinate — but bp still has to resolve it, so the entry must
        # NOT be dropped. Existing entries are durable; the harvest only adds
        # new shapes and refreshes aliases/files for shapes still written as
        # literals. Curated names/meanings always win.
        merged: dict = {}
        if REGISTRY.exists():
            for r in load_user_blueprints():
                merged[coord(r)] = r
        for row in generated["blueprints"]:
            k = coord(row)
            prior = merged.get(k)
            if prior:
                if prior.get("curated"):
                    row["name"] = prior.get("name", row["name"])
                    row["meaning"] = prior.get("meaning", row["meaning"])
                    row["curated"] = True
                # union aliases across harvest + prior so migrated names persist
                row["aliases"] = sorted(set(row.get("aliases", []))
                                        | set(prior.get("aliases", []))
                                        | ({prior["name"]} if prior["name"] != row["name"] else set()))
            merged[k] = row
        out = dict(generated)
        out["blueprints"] = [merged[k] for k in sorted(merged)]
        REGISTRY.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {REGISTRY.relative_to(ROOT)} "
              f"({len(out['blueprints'])} blueprints, all coordinates; union-preserving)")
        return 0

    s = scan()
    if args.json:
        out = {
            "literals": len(s["sites"]),
            "distinct": len({x["key"] for x in s["sites"]}),
            "registered": len(s["reg"]),
            "collisions": {n: [fmt_key(k) for k in v]
                           for n, v in s["collisions"].items()},
            "unregistered_99": [fmt_key(k) for k in s["unregistered_99"]],
        }
        print(json.dumps(out, indent=2))
    else:
        report(s)

    if args.check:
        # Forward-looking gate: no new type-99 number may ship without a
        # registry row. This is what keeps the magic-number sprawl from
        # growing — the ongoing hygiene the registry doc commits to. Run
        # `--emit-registry` to register a genuinely-new shape first.
        if s["unregistered_99"]:
            print(f"FAIL: {len(s['unregistered_99'])} type-99 NodeID(s) used "
                  f"in source but absent from blueprint-registry.json: "
                  f"{[fmt_key(k) for k in s['unregistered_99']]}\n"
                  f"      Add a row (run --emit-registry) before shipping a "
                  f"new Blueprint number.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
