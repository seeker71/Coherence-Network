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
# A by-name Blueprint reference: (bp "NAME"). The kernel resolves NAME against
# the generated bp table; an unregistered NAME used to fall back silently to a
# shared {1,2,0,0} NodeID, so distinct names collided invisibly. The kernels now
# fail loud; this scanner finds such names BEFORE they ship.
BP_REF_RE = re.compile(r'\(\s*bp\s+"([^"]+)"\s*\)')
Key = tuple  # (pkg, level, type, inst)


def registered_names(reg: dict) -> set:
    """Every name the kernel's bp table will resolve — canonical + aliases of
    each registered shape (categories, primitives, user blueprints)."""
    names: set = set()
    for entry in reg.values():
        names.add(entry["canonical"])
        names.update(entry.get("aliases", []))
    return names


def scan_bp_refs(reg: dict) -> dict[str, list[str]]:
    """Map each (bp "NAME") whose NAME is NOT registered → the files using it.
    Form comments start with ';'; strip them so prose like `(bp "name")` in a
    doc-comment is not mistaken for a real reference."""
    known = registered_names(reg)
    unreg: dict[str, list[str]] = collections.defaultdict(list)
    for f in sorted(FORM_ROOT.rglob("*.fk")):
        rel = str(f.relative_to(ROOT))
        for line in f.read_text(errors="ignore").splitlines():
            code = line.split(";", 1)[0]
            for m in BP_REF_RE.finditer(code):
                if m.group(1) not in known:
                    unreg[m.group(1)].append(rel)
    return {n: sorted(set(fs)) for n, fs in unreg.items()}


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

    # (bp "NAME") references whose NAME is not registered — the silent-collision
    # class the kernels now reject at runtime, caught here before they ship.
    unregistered_bp_names = scan_bp_refs(reg)

    return {
        "reg": reg,
        "sites": sites,
        "num_to_names": num_to_names,
        "name_to_nums": name_to_nums,
        "collisions": collisions,
        "synonyms": synonyms,
        "unregistered_99": unregistered_99,
        "unregistered_bp_names": unregistered_bp_names,
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

    if s.get("unregistered_bp_names"):
        print(f'⚠  (bp "NAME") references with NO registry row '
              f"({len(s['unregistered_bp_names'])}) — the kernels fail loud on "
              f"these; register each before shipping:")
        for name, files in sorted(s["unregistered_bp_names"].items()):
            print(f"   {name}: {files}")
            print(f"     → python3 scripts/scan_form_blueprints.py register {name}")
        print()


def _regen_bp_tables() -> None:
    """Regenerate the three kernel bp tables from the registry. The registry is
    the source of truth; without this the kernels would not see a new/removed
    name. Best-effort — prints a clear note if the generator is unavailable."""
    import subprocess
    gen = ROOT / "scripts" / "gen_bp_table.py"
    if not gen.exists():
        print(f"  (note: {gen.relative_to(ROOT)} not found — regenerate bp "
              f"tables manually before running the kernels)")
        return
    subprocess.run([sys.executable, str(gen)], check=True)


def _next_free_inst(blueprints: list[dict], type_: int) -> int:
    """First free instance number across the whole type-N NodeID space — the
    body treats type-99 insts as one sequence regardless of level/pkg, so a
    new shape must not collide with ANY existing type-N inst."""
    used = {b["inst"] for b in blueprints if b.get("type", 99) == type_}
    i = 1
    while i in used:
        i += 1
    return i


def register_name(name: str, *, level: int = 2, type_: int = 99, pkg: int = 1,
                  meaning: str = "", defined_in: str | None = None,
                  inst: int | None = None) -> int:
    """Add a blueprint row for NAME and regenerate the kernel bp tables.
    Allocates the next free inst, OR honors an explicit `inst` (used to migrate
    an existing make_nodeid literal to a name at its current coordinate, so the
    NodeID is preserved). Idempotent: an already-registered name is untouched."""
    data = json.loads(REGISTRY.read_text())
    bps = data["blueprints"]
    for b in bps:
        if b["name"] == name or name in b.get("aliases", []):
            print(f"already registered: {name} → "
                  f"{b.get('pkg',1)}.{b.get('level',2)}.{b.get('type',99)}.{b['inst']}")
            return 0
    if inst is None:
        inst = _next_free_inst(bps, type_)
    elif any(b.get("pkg", 1) == pkg and b.get("level", 2) == level
             and b.get("type", 99) == type_ and b["inst"] == inst for b in bps):
        print(f"coordinate {pkg}.{level}.{type_}.{inst} already taken — "
              f"omit --inst to auto-allocate", file=sys.stderr)
        return 1
    row = {
        "pkg": pkg, "level": level, "type": type_, "inst": inst,
        "name": name, "meaning": meaning, "aliases": [], "reuse": 1,
        "defined_in": [defined_in] if defined_in else [],
        "curated": True,
    }
    bps.append(row)
    bps.sort(key=lambda b: (b.get("pkg", 1), b.get("level", 2),
                            b.get("type", 99), b["inst"]))
    REGISTRY.write_text(json.dumps(data, indent=2) + "\n")
    print(f"registered: {name} → {pkg}.{level}.{type_}.{inst}")
    _regen_bp_tables()
    return 0


def unregister_name(name: str) -> int:
    """Remove the blueprint row whose canonical name is NAME and regenerate the
    kernel bp tables. (Aliases are not removable on their own — edit the row.)"""
    data = json.loads(REGISTRY.read_text())
    bps = data["blueprints"]
    kept = [b for b in bps if b["name"] != name]
    if len(kept) == len(bps):
        print(f"not registered (nothing to remove): {name}", file=sys.stderr)
        return 1
    removed = [b for b in bps if b["name"] == name]
    data["blueprints"] = kept
    REGISTRY.write_text(json.dumps(data, indent=2) + "\n")
    for b in removed:
        print(f"unregistered: {name} (was "
              f"{b.get('pkg',1)}.{b.get('level',2)}.{b.get('type',99)}.{b['inst']})")
    _regen_bp_tables()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit nonzero if name drift OR an unregistered "
                         "(bp \"name\") reference exists (CI/wellness)")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable scan result")
    ap.add_argument("--emit-registry", action="store_true",
                    help="(re)generate form-stdlib/blueprint-registry.json "
                         "from code, preserving curated meanings")
    # register / unregister a single name (the mechanism the kernels point at).
    ap.add_argument("register", nargs="?", choices=["register", "unregister"],
                    help=argparse.SUPPRESS)
    ap.add_argument("name", nargs="?", help=argparse.SUPPRESS)
    ap.add_argument("--level", type=int, default=2,
                    help="compositional level for register (default 2)")
    ap.add_argument("--type", type=int, default=99, dest="type_",
                    help="NodeID type for register (default 99, user-space)")
    ap.add_argument("--meaning", default="",
                    help="human-readable meaning for the registered shape")
    ap.add_argument("--defined-in", default=None,
                    help="path of the .fk file that uses this name")
    ap.add_argument("--inst", type=int, default=None,
                    help="explicit instance number (migrate an existing literal "
                         "at its current coordinate); default auto-allocates")
    args = ap.parse_args()

    if args.register == "register":
        if not args.name:
            ap.error("register requires a NAME")
        return register_name(args.name, level=args.level, type_=args.type_,
                             meaning=args.meaning, defined_in=args.defined_in,
                             inst=args.inst)
    if args.register == "unregister":
        if not args.name:
            ap.error("unregister requires a NAME")
        return unregister_name(args.name)

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
        failed = False
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
            failed = True
        # The silent-collision gate: every (bp "name") must resolve. The kernels
        # now fail loud at runtime; this fails the build first, with the fix.
        if s.get("unregistered_bp_names"):
            names = sorted(s["unregistered_bp_names"])
            print(f'FAIL: {len(names)} (bp "name") reference(s) with no registry '
                  f"row — the kernels will fail loud on these: {names}\n"
                  f"      Register each: "
                  f"python3 scripts/scan_form_blueprints.py register <NAME>",
                  file=sys.stderr)
            failed = True
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
