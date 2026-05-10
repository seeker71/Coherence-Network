#!/usr/bin/env python3
"""coh substrate — unified CLI for the coherence-substrate.

A single entry-point for every substrate operation: ingestion, stats,
equivalence queries, path annotation, and Form expression evaluation.

Usage:
    coh_substrate.py ingest <path>...                  # ingest specific files
    coh_substrate.py ingest --memories                  # backfill memories
    coh_substrate.py ingest --all                       # backfill all 5 domains
    coh_substrate.py stats                              # lattice statistics
    coh_substrate.py equivalent <domain> <name>         # structural equivalents
    coh_substrate.py annotate <path>                    # substrate context for a file
    coh_substrate.py form "<expression>"                # evaluate a Form expression

For detail on Form syntax see docs/coherence-substrate/form-language.md.
For agent grounding patterns see docs/coherence-substrate/agents-using-substrate.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate import (  # noqa: E402
    annotate_path,
    find_equivalent_cells,
    form_evaluate_text,
    form_serialize_cell,
    form_serialize_node_id,
    ingest_concept_file,
    ingest_idea_file,
    ingest_memory_file,
    ingest_presence_file,
    ingest_spec_file,
    lattice_stats,
    lookup_cell,
)
from app.services.unified_db import session as session_scope  # noqa: E402


MEMORY_DIR = Path.home() / ".claude/projects/-Users-ursmuff-source-Coherence-Network/memory"
SPEC_DIR = REPO_ROOT / "specs"
IDEA_DIR = REPO_ROOT / "ideas"
CONCEPT_DIR = REPO_ROOT / "docs/vision-kb/concepts"
PRESENCE_DIR = REPO_ROOT / "docs/presences"

_INGESTERS = {
    "memory": (MEMORY_DIR, ingest_memory_file, lambda p: p.name.upper() != "MEMORY.MD"),
    "spec": (SPEC_DIR, ingest_spec_file, lambda p: p.name not in ("INDEX.md", "TEMPLATE.md", "MANIFEST.md")),
    "idea": (IDEA_DIR, ingest_idea_file, lambda p: p.name not in ("INDEX.md", "TEMPLATE.md")),
    "concept": (CONCEPT_DIR, ingest_concept_file, lambda p: p.name not in ("INDEX.md", "SCHEMA.md", "LOG.md")),
    "presence": (PRESENCE_DIR, ingest_presence_file, lambda p: p.name not in ("INDEX.md", "README.md")),
}


def cmd_ingest(args: argparse.Namespace) -> int:
    if args.all:
        rc = 0
        for domain in ("memory", "spec", "idea", "concept", "presence"):
            rc |= _ingest_domain(domain)
        return rc
    if args.memories:
        return _ingest_domain("memory")
    if args.specs:
        return _ingest_domain("spec")
    if args.ideas:
        return _ingest_domain("idea")
    if args.concepts:
        return _ingest_domain("concept")
    if args.presences:
        return _ingest_domain("presence")
    if args.paths:
        return _ingest_files([Path(p) for p in args.paths])
    print("ingest: no target specified (try --memories, --all, or paths)", file=sys.stderr)
    return 1


def _ingest_files(paths: list[Path]) -> int:
    with session_scope() as session:
        for path in paths:
            if not path.exists() or path.is_dir():
                print(f"  skip (not a file): {path}", file=sys.stderr)
                continue
            if path.suffix != ".md":
                print(f"  skip (not .md): {path}", file=sys.stderr)
                continue
            cell, bp_id, ctor_id = ingest_memory_file(session, path)
            print(f"  ingested {path.name}: cell_id={cell.cell_id} blueprint={bp_id}")
        session.commit()
    return 0


def _ingest_domain(domain: str) -> int:
    if domain not in _INGESTERS:
        print(f"unknown domain: {domain}", file=sys.stderr)
        return 1
    base, ingester, filter_fn = _INGESTERS[domain]
    if not base.exists():
        # Some domains live outside the repo (memory) and are absent in
        # production / CI / fresh checkouts. Skipping is the right shape:
        # `--all` should populate what it can find, not refuse the run.
        print(f"{domain}: dir not found ({base}) — skipped", file=sys.stderr)
        return 0
    md_files = sorted([p for p in base.glob("*.md") if filter_fn(p)])
    print(f"Ingesting {len(md_files)} {domain} files from {base}")
    success = fail = 0
    with session_scope() as session:
        for path in md_files:
            try:
                cell, bp_id, ctor_id = ingester(session, path)
                success += 1
                if success <= 3 or success % 25 == 0:
                    print(f"  [{success}] {path.name}: bp={bp_id}")
            except Exception as exc:
                fail += 1
                print(f"  ! failed {path.name}: {exc}", file=sys.stderr)
        session.commit()
    print(f"{domain}: {success} ingested, {fail} failed")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with session_scope() as session:
        s = lattice_stats(session)
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print("Coherence-substrate lattice stats:")
        for key, value in s.items():
            print(f"  {key}: {value}")
    return 0


def cmd_equivalent(args: argparse.Namespace) -> int:
    with session_scope() as session:
        cell = lookup_cell(session, args.domain, args.name)
        if cell is None:
            print(f"No cell found for ({args.domain}, {args.name})", file=sys.stderr)
            return 1
        eq = find_equivalent_cells(session, cell.blueprint, exclude_name=cell.name)
        if args.json:
            print(json.dumps({
                "cell": {"domain": cell.domain, "name": cell.name},
                "blueprint": form_serialize_node_id(cell.blueprint),
                "equivalents": [{"domain": c.domain, "name": c.name} for c in eq],
                "count": len(eq),
            }, indent=2))
        else:
            print(f"Cell: {form_serialize_cell(cell)}")
            print(f"  blueprint={form_serialize_node_id(cell.blueprint)}")
            print(f"  source_path={cell.source_path}")
            if not eq:
                print(f"  no structurally equivalent cells")
            else:
                print(f"  structurally equivalent cells ({len(eq)}):")
                for c in eq[:50]:
                    print(f"    - {form_serialize_cell(c)}")
                if len(eq) > 50:
                    print(f"    ... and {len(eq) - 50} more")
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    abs_path = str(Path(args.path).resolve())
    with session_scope() as session:
        ann = annotate_path(session, abs_path)
    if args.json:
        out = {
            "path": ann.path,
            "in_substrate": ann.cell is not None,
            "domain": ann.domain,
        }
        if ann.cell:
            out["cell"] = {"domain": ann.cell.domain, "name": ann.cell.name}
            out["blueprint"] = form_serialize_node_id(ann.blueprint) if ann.blueprint else None
            out["equivalents"] = [{"domain": c.domain, "name": c.name} for c in ann.equivalents]
            out["equivalents_count"] = len(ann.equivalents)
        print(json.dumps(out, indent=2))
    else:
        if ann.cell is None:
            print(f"Path: {ann.path}")
            print(f"  not in substrate (this file hasn't been ingested)")
        else:
            print(f"Path: {ann.path}")
            print(f"  cell: {form_serialize_cell(ann.cell)}")
            print(f"  blueprint: {form_serialize_node_id(ann.blueprint)}")
            print(f"  domain: {ann.domain}")
            if ann.equivalents:
                print(f"  structurally equivalent cells ({len(ann.equivalents)}):")
                for c in ann.equivalents[:20]:
                    print(f"    - {form_serialize_cell(c)}")
                if len(ann.equivalents) > 20:
                    print(f"    ... and {len(ann.equivalents) - 20} more")
            else:
                print(f"  no structurally equivalent cells")
    return 0


def cmd_form(args: argparse.Namespace) -> int:
    try:
        with session_scope() as session:
            result = form_evaluate_text(session, args.expression)
    except (SyntaxError, NameError, LookupError, TypeError) as exc:
        print(f"Form: {exc}", file=sys.stderr)
        return 1

    from app.services.substrate.kernel import CellView, NamedCell

    def to_dict(v):
        from app.services.substrate.kernel import NodeID
        if isinstance(v, NodeID):
            return {"form": form_serialize_node_id(v)}
        if isinstance(v, NamedCell):
            return {
                "domain": v.domain, "name": v.name,
                "blueprint": form_serialize_node_id(v.blueprint) if v.blueprint else None,
                "form": form_serialize_cell(v),
            }
        if isinstance(v, CellView):
            return {
                "cell": to_dict(v.cell),
                "view_blueprint": form_serialize_node_id(v.view_blueprint),
                "compatible": v.compatible,
                "reason": v.reason,
            }
        if isinstance(v, list):
            return [to_dict(x) for x in v]
        return repr(v)

    if args.json:
        print(json.dumps(to_dict(result.value), indent=2))
    else:
        from app.services.substrate.kernel import NodeID
        v = result.value
        if isinstance(v, NodeID):
            print(form_serialize_node_id(v))
        elif isinstance(v, NamedCell):
            bp = form_serialize_node_id(v.blueprint) if v.blueprint else "?"
            print(f"{form_serialize_cell(v)}  blueprint={bp}")
        elif isinstance(v, CellView):
            bp = form_serialize_node_id(v.view_blueprint)
            cell = form_serialize_cell(v.cell)
            mark = "✓ compatible" if v.compatible else f"✗ incompatible: {v.reason}"
            print(f"{cell} |> {bp}  {mark}")
        elif isinstance(v, list):
            if not v:
                print("(empty)")
            else:
                print(f"({len(v)} results)")
                for x in v[:50]:
                    if isinstance(x, NamedCell):
                        bp = form_serialize_node_id(x.blueprint) if x.blueprint else "?"
                        print(f"  {form_serialize_cell(x)}  blueprint={bp}")
                    elif isinstance(x, CellView):
                        bp = form_serialize_node_id(x.view_blueprint)
                        mark = "✓" if x.compatible else "✗"
                        print(f"  {form_serialize_cell(x.cell)} |> {bp}  {mark}")
                    else:
                        print(f"  {x!r}")
                if len(v) > 50:
                    print(f"  ... and {len(v) - 50} more")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest markdown file(s) into the substrate")
    p_ingest.add_argument("paths", nargs="*")
    p_ingest.add_argument("--memories", action="store_true")
    p_ingest.add_argument("--specs", action="store_true")
    p_ingest.add_argument("--ideas", action="store_true")
    p_ingest.add_argument("--concepts", action="store_true")
    p_ingest.add_argument("--presences", action="store_true")
    p_ingest.add_argument("--all", action="store_true", help="Backfill all five domains")

    sub.add_parser("stats", help="Print lattice statistics")

    p_eq = sub.add_parser("equivalent", help="Find structurally-equivalent cells")
    p_eq.add_argument("domain")
    p_eq.add_argument("name")

    p_ann = sub.add_parser("annotate", help="Substrate context for a file path")
    p_ann.add_argument("path")

    p_form = sub.add_parser("form", help="Evaluate a Form expression")
    p_form.add_argument("expression")

    p_disc = sub.add_parser(
        "discover",
        help="Surface clusters, outliers, and cross-domain shape collisions",
    )
    p_disc.add_argument("--domain", default=None, help="Restrict to one domain")
    p_disc.add_argument(
        "--min-cluster",
        type=int,
        default=2,
        help="Minimum cluster size to report (default 2)",
    )

    p_sense = sub.add_parser(
        "sense",
        help="Sense the body's vitality — flow, friction, suppleness, stiffness, dead tissue",
    )
    p_sense.add_argument(
        "--top",
        type=int,
        default=5,
        help="How many entries per section (default 5)",
    )
    p_sense.add_argument(
        "--complex-singleton-min",
        type=int,
        default=80,
        help="Min ctor-recipe serialized length to count as 'complex' singleton",
    )

    p_sense_repo = sub.add_parser(
        "sense-repo",
        help="Sense ALL tracked files (not just substrate cells) — orphans, dead tissue, build-output that snuck in",
    )
    p_sense_repo.add_argument(
        "--orphan-dir-threshold",
        type=float,
        default=0.8,
        help="Fraction of files in a dir that must be orphans to flag the dir (default 0.8)",
    )
    p_sense_repo.add_argument(
        "--min-dir-files",
        type=int,
        default=3,
        help="Minimum file count for a dir to be flagged as orphan (default 3)",
    )
    p_sense_repo.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many entries per section",
    )

    p_chain = sub.add_parser(
        "chain",
        help="Sense the idea→spec→code→test chain: where each idea reaches and where it breaks",
    )
    p_chain.add_argument(
        "--top",
        type=int,
        default=12,
        help="How many entries per section (default 12)",
    )
    p_chain.add_argument(
        "--idea",
        default=None,
        help="Restrict to a single idea_id (drilldown view)",
    )
    p_chain.add_argument(
        "--spec",
        default=None,
        help="Restrict to a single spec slug (drilldown view)",
    )

    p_check = sub.add_parser(
        "shape-check",
        help="For a draft .md file: report cells with the same structural shape",
    )
    p_check.add_argument("path", help="Path to a .md file (need not be ingested yet)")
    p_check.add_argument(
        "--domain",
        default=None,
        help="Domain to compare against (default: inferred from path)",
    )

    p_ingest_paths = sub.add_parser(
        "ingest-paths",
        help="Auto-ingest a list of changed paths (e.g. from a git hook)",
    )
    p_ingest_paths.add_argument("paths", nargs="*", help="Paths to ingest")
    p_ingest_paths.add_argument(
        "--from-stdin",
        action="store_true",
        help="Read paths from stdin (one per line)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "ingest":
        return cmd_ingest(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    if args.cmd == "equivalent":
        return cmd_equivalent(args)
    if args.cmd == "annotate":
        return cmd_annotate(args)
    if args.cmd == "form":
        return cmd_form(args)
    if args.cmd == "discover":
        return cmd_discover(args)
    if args.cmd == "sense":
        return cmd_sense(args)
    if args.cmd == "sense-repo":
        return cmd_sense_repo(args)
    if args.cmd == "chain":
        return cmd_chain(args)
    if args.cmd == "shape-check":
        return cmd_shape_check(args)
    if args.cmd == "ingest-paths":
        return cmd_ingest_paths(args)
    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# discover — surface clusters + outliers + cross-domain collisions
# ---------------------------------------------------------------------------


def cmd_discover(args: argparse.Namespace) -> int:
    """Walk the substrate and surface what shapes exist.

    Reports per-domain:
      - The largest blueprint clusters (potential merge candidates)
      - Singleton blueprints (unique shapes — most distinctive cells)
      - Cross-domain collisions (same blueprint NodeID across domains)
    """
    from app.services.substrate.orm import SubstrateNamedCellORM
    from collections import defaultdict

    with session_scope() as session:
        rows = session.query(SubstrateNamedCellORM)
        if args.domain:
            rows = rows.filter_by(domain=args.domain)
        rows = rows.all()

        # Group by (domain, blueprint_node_id)
        by_domain_bp: dict = defaultdict(list)
        bp_to_domains: dict = defaultdict(set)
        for r in rows:
            bp_id = r.blueprint_node_id
            by_domain_bp[(r.domain, bp_id)].append(r.name)
            bp_to_domains[bp_id].add(r.domain)

        if args.json:
            out = {"clusters": [], "singletons": [], "cross_domain": []}
            for (domain, bp_id), names in sorted(
                by_domain_bp.items(), key=lambda x: -len(x[1])
            ):
                if len(names) >= args.min_cluster:
                    out["clusters"].append({
                        "domain": domain, "blueprint_node_id": bp_id,
                        "count": len(names), "names": names[:10],
                    })
                elif len(names) == 1:
                    out["singletons"].append({
                        "domain": domain, "blueprint_node_id": bp_id,
                        "name": names[0],
                    })
            for bp_id, domains in bp_to_domains.items():
                if len(domains) > 1:
                    out["cross_domain"].append({
                        "blueprint_node_id": bp_id,
                        "domains": sorted(domains),
                    })
            print(json.dumps(out, indent=2))
            return 0

        # Human-readable
        print(f"Substrate analysis ({len(rows)} cells)\n")

        # Clusters
        clusters = sorted(
            [(d, b, ns) for (d, b), ns in by_domain_bp.items()
             if len(ns) >= args.min_cluster],
            key=lambda x: -len(x[2]),
        )
        if clusters:
            print(f"=== Largest clusters (potential merge candidates) ===")
            for domain, bp_id, names in clusters[:15]:
                print(f"  [{domain}] blueprint={bp_id}: {len(names)} cells")
                for n in names[:3]:
                    print(f"      - {n}")
                if len(names) > 3:
                    print(f"      ... and {len(names) - 3} more")
            print()

        # Singletons (most distinctive)
        singletons = [
            (d, b, ns[0]) for (d, b), ns in by_domain_bp.items() if len(ns) == 1
        ]
        if singletons:
            print(f"=== Singletons ({len(singletons)} unique shapes) ===")
            print(f"  These cells have shapes that exist nowhere else in the body.")
            for domain, bp_id, name in singletons[:10]:
                print(f"  [{domain}] {name}  blueprint={bp_id}")
            if len(singletons) > 10:
                print(f"  ... and {len(singletons) - 10} more")
            print()

        # Cross-domain
        cross = [
            (bp_id, sorted(domains))
            for bp_id, domains in bp_to_domains.items()
            if len(domains) > 1
        ]
        if cross:
            print(f"=== Cross-domain shape collisions ({len(cross)}) ===")
            print(f"  Same Blueprint NodeID exists across multiple domains.")
            print(f"  Worth investigating: are these cells genuinely structurally")
            print(f"  the same, or is the Blueprint shape too coarse?")
            for bp_id, domains in cross[:10]:
                print(f"  blueprint={bp_id}: {', '.join(domains)}")
        else:
            print("=== No cross-domain shape collisions ===")
            print("  Each domain's shapes are distinct from other domains.")

        return 0


# ---------------------------------------------------------------------------
# sense — substrate as sensing organ: flow, friction, suppleness,
# stiffness, dead tissue. Heuristic, not verdict — the lens proposes
# questions; the human reads them.
# ---------------------------------------------------------------------------


def cmd_sense(args: argparse.Namespace) -> int:
    """Sense the body's vitality through substrate signatures.

    flow        — blueprints carrying cells across multiple domains
    suppleness  — generalizable forms (cells × domains)
    friction    — near-cousin blueprints (same family, varying instance)
    stiffness   — singleton blueprints with complex ctors
    dead tissue — cells whose source_path no longer exists on disk
    """
    from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
    from collections import defaultdict
    from pathlib import Path as _Path

    with session_scope() as session:
        cells = session.query(SubstrateNamedCellORM).all()

        bp_ids = {c.blueprint_node_id for c in cells}
        ctor_ids = {c.ctor_recipe_node_id for c in cells if c.ctor_recipe_node_id}
        bp_nodes = {
            n.node_id: n
            for n in session.query(SubstrateNodeORM).filter(
                SubstrateNodeORM.node_id.in_(bp_ids)
            ).all()
        }
        ctor_nodes = {
            n.node_id: n
            for n in session.query(SubstrateNodeORM).filter(
                SubstrateNodeORM.node_id.in_(ctor_ids)
            ).all()
        }

        bp_cells: dict[int, list] = defaultdict(list)
        bp_domains: dict[int, set[str]] = defaultdict(set)
        for c in cells:
            bp_cells[c.blueprint_node_id].append(c)
            bp_domains[c.blueprint_node_id].add(c.domain)

        def _bp_form(bp_id: int) -> str:
            n = bp_nodes.get(bp_id)
            return f"@{n.package}.{n.level}.{n.type_}.{n.instance}" if n else f"#{bp_id}"

        # ---- FLOW: blueprints crossing domain boundaries ---------------------
        flow = sorted(
            (
                (bp, len(bp_domains[bp]), len(bp_cells[bp]))
                for bp in bp_cells
                if len(bp_domains[bp]) > 1
            ),
            key=lambda x: (-x[1], -x[2]),
        )

        # ---- SUPPLENESS: cells × domains (highest = most generalizable) ------
        suppleness = sorted(
            (
                (bp, len(bp_cells[bp]), len(bp_domains[bp]))
                for bp in bp_cells
            ),
            key=lambda x: -(x[1] * x[2]),
        )

        # ---- FRICTION: near-cousins (share package+level+type, differ in instance)
        family: dict[tuple, set[int]] = defaultdict(set)
        for bp_id, n in bp_nodes.items():
            family[(n.package, n.level, n.type_)].add(bp_id)
        friction_families = sorted(
            ((fam, bps) for fam, bps in family.items() if len(bps) > 1),
            key=lambda x: -len(x[1]),
        )

        # ---- STIFFNESS: singletons with complex ctors -----------------------
        stiff: list[tuple] = []
        for bp_id, cs in bp_cells.items():
            if len(cs) != 1:
                continue
            cell = cs[0]
            if not cell.ctor_recipe_node_id:
                continue
            ctor = ctor_nodes.get(cell.ctor_recipe_node_id)
            if not ctor:
                continue
            cx = len(ctor.serialized or "")
            if cx >= args.complex_singleton_min:
                stiff.append((cell, cx, bp_id))
        stiff.sort(key=lambda x: -x[1])

        # ---- DEAD TISSUE: missing source_path on disk -----------------------
        dead = [
            c for c in cells
            if c.source_path and not _Path(c.source_path).exists()
        ]
        dead.sort(key=lambda c: (c.domain, c.name))

        if args.json:
            out = {
                "flow": [
                    {
                        "blueprint": _bp_form(bp), "domains": sorted(bp_domains[bp]),
                        "cell_count": cells_n,
                    }
                    for bp, _doms_n, cells_n in flow[: args.top]
                ],
                "suppleness": [
                    {
                        "blueprint": _bp_form(bp), "cells": cells_n,
                        "domains": sorted(bp_domains[bp]),
                    }
                    for bp, cells_n, _doms_n in suppleness[: args.top]
                ],
                "friction": [
                    {
                        "family": f"@{p}.{lv}.{t}.*",
                        "variants": [_bp_form(b) for b in sorted(bps)],
                    }
                    for (p, lv, t), bps in friction_families[: args.top]
                ],
                "stiffness": [
                    {
                        "cell": f"{c.domain}/{c.name}",
                        "blueprint": _bp_form(bp),
                        "ctor_complexity": cx,
                    }
                    for c, cx, bp in stiff[: args.top]
                ],
                "dead_tissue": [
                    {"cell": f"{c.domain}/{c.name}", "missing_path": c.source_path}
                    for c in dead[: args.top * 4]
                ],
                "totals": {
                    "cells": len(cells),
                    "blueprints": len(bp_cells),
                    "flow_count": len(flow),
                    "friction_families": len(friction_families),
                    "stiff_singletons": len(stiff),
                    "dead": len(dead),
                },
            }
            print(json.dumps(out, indent=2))
            return 0

        print(f"Substrate sense ({len(cells)} cells, {len(bp_cells)} blueprints)\n")

        print(f"=== FLOW — blueprints carrying cells across domains ({len(flow)}) ===")
        if not flow:
            print("  (no cross-domain blueprints — each domain's shapes are isolated)")
        for bp, doms_n, cells_n in flow[: args.top]:
            doms = ", ".join(sorted(bp_domains[bp]))
            print(f"  {_bp_form(bp)}  {doms_n} domains × {cells_n} cells   [{doms}]")
        print()

        print(f"=== SUPPLENESS — generalizable forms (top {args.top}) ===")
        for bp, cells_n, doms_n in suppleness[: args.top]:
            doms = ", ".join(sorted(bp_domains[bp]))
            sample = bp_cells[bp][0]
            print(
                f"  {_bp_form(bp)}  {cells_n} cells × {doms_n} domains   "
                f"[{doms}]  e.g. {sample.domain}/{sample.name}"
            )
        print()

        print(f"=== FRICTION — near-cousin blueprints (same family, varying instance) ({len(friction_families)}) ===")
        if not friction_families:
            print("  (no near-cousins — every (package,level,type) tuple has a single instance)")
        for (p, lv, t), bps in friction_families[: args.top]:
            variants = ", ".join(_bp_form(b) for b in sorted(bps)[:6])
            extra = "" if len(bps) <= 6 else f" + {len(bps) - 6} more"
            print(f"  family @{p}.{lv}.{t}.*  {len(bps)} variants:  {variants}{extra}")
        print()

        print(f"=== STIFFNESS — singletons with complex ctors ({len(stiff)}) ===")
        if not stiff:
            print(f"  (no singletons with ctor complexity ≥ {args.complex_singleton_min})")
        for c, cx, bp in stiff[: args.top]:
            print(f"  {c.domain}/{c.name}  {_bp_form(bp)}  ctor_len={cx}")
        print()

        print(f"=== DEAD TISSUE — cells whose source_path no longer resolves ({len(dead)}) ===")
        if not dead:
            print("  (every ingested cell still points at a file that exists)")
            print("  Note: source_path is recorded at ingest time. If you're running")
            print("  this in a different environment than the ingest, paths may be ghosts.")
        for c in dead[: args.top * 4]:
            print(f"  {c.domain}/{c.name}  →  {c.source_path}")
        if len(dead) > args.top * 4:
            print(f"  ... and {len(dead) - args.top * 4} more")
        print()

        print("Lens caveat: these are *questions* the substrate proposes, not verdicts.")
        print("A singleton may be a unique work; a near-cousin family may be intentional.")
        print("Read with the body, not against it.")
        return 0


# ---------------------------------------------------------------------------
# sense-repo — extend the lens beyond named cells: walk every tracked
# file, build a reference graph, surface orphans, orphan dirs, and
# build-output signatures (playwright reports, coverage dumps, screenshot
# avalanches that snuck in via merge).
#
# Pure walk-and-analyze — no DB writes. The substrate's named-cell layer
# already knows about markdown frontmatter shapes; this lens looks at
# everything else the body is carrying.
# ---------------------------------------------------------------------------


# Text extensions we'll open and scan for path references. Anything else
# is treated as opaque (binary blob, image, etc.) — its presence may be
# referenced by something else, but it doesn't itself reference others.
_TEXT_EXTS = {
    ".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".txt", ".sh", ".bash",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".go", ".rs", ".sql", ".proto", ".graphql", ".gql",
    ".cfg", ".ini", ".env", ".conf", ".dockerfile",
    ".tf", ".lua", ".rb", ".swift", ".kt", ".java",
    ".c", ".cpp", ".cc", ".h", ".hpp",
    ".xml", ".svg",
}
_TEXT_NAMES = {
    "Dockerfile", "Makefile", "README", "LICENSE", "Procfile",
    ".gitignore", ".dockerignore", ".gitattributes", ".eslintrc",
    ".prettierrc", "CHANGELOG", "NOTICE",
}

# Directory-shape signatures. Each is (label, predicate(ext_counter, names)).
# Predicates return a confidence score (0..1) — first to score >= 0.6 wins.
def _classify_dir_shape(name: str, ext_counts: "Counter[str]", file_names: list[str]) -> "tuple[str, float] | None":  # noqa
    total = sum(ext_counts.values())
    if total < 3:
        return None
    has_md = ext_counts.get(".md", 0) > 0
    has_html = ext_counts.get(".html", 0) > 0
    has_png = ext_counts.get(".png", 0) > 0
    has_webm = ext_counts.get(".webm", 0) > 0
    has_zip = ext_counts.get(".zip", 0) > 0
    has_jsmap = ext_counts.get(".js.map", 0) > 0 or any(n.endswith(".js.map") for n in file_names)
    has_css = ext_counts.get(".css", 0) > 0
    has_js = ext_counts.get(".js", 0) > 0
    has_index_html = "index.html" in file_names
    img_ratio = (ext_counts.get(".png", 0) + ext_counts.get(".jpg", 0) + ext_counts.get(".jpeg", 0)) / total

    if (has_html and has_webm) or (has_html and has_png and has_zip) or "playwright-report" in name.lower():
        return ("playwright-report", 0.95)
    if has_index_html and has_css and has_js and not has_md and total > 5:
        return ("static-site / coverage / docs-build", 0.75)
    if name.lower() in {"node_modules", ".next", "dist", "build", "out", ".turbo", ".cache", "coverage"}:
        return (f"build-output ({name})", 0.95)
    if name.lower() in {"output", ".output"} and total > 3:
        return ("output dir", 0.7)
    if has_jsmap and has_js:
        return ("bundler dump (.js + .js.map)", 0.7)
    if img_ratio > 0.8 and total >= 5 and not has_md:
        return ("image dump (likely screenshot run)", 0.7)
    return None


def cmd_sense_repo(args: argparse.Namespace) -> int:  # noqa: C901 — single-pass lens
    """Walk all tracked files; surface dead tissue beyond the substrate's
    named-cell layer."""
    import re
    import subprocess
    from collections import Counter, defaultdict

    repo_root = REPO_ROOT
    git = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = sorted(p for p in git.stdout.splitlines() if p)
    tracked_set = set(tracked)

    # Basename → paths sharing it (so we can resolve unique-basename references)
    basename_paths: dict[str, list[str]] = defaultdict(list)
    for p in tracked:
        basename_paths[Path(p).name].append(p)

    # --- Build the reference graph -------------------------------------------
    # For each text file, scan its content for path-like tokens; for each
    # token that resolves to a tracked path (full or unique-basename), record
    # an incoming reference.
    references_in: dict[str, set[str]] = defaultdict(set)
    # Path-like tokens: chunks of [\w./\-_] that contain a '/' or a '.'.
    token_re = re.compile(r"[\w./\-_]{4,}")

    def is_text(p: str) -> bool:
        suffix = Path(p).suffix.lower()
        if suffix in _TEXT_EXTS:
            return True
        return Path(p).name in _TEXT_NAMES

    text_files = [p for p in tracked if is_text(p)]
    for src in text_files:
        full = repo_root / src
        try:
            content = full.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        seen_targets_for_src: set[str] = set()
        for m in token_re.finditer(content):
            tok = m.group(0)
            if "/" not in tok and "." not in tok:
                continue
            # Strip leading './'
            while tok.startswith("./"):
                tok = tok[2:]
            tok = tok.rstrip(".,;:)\"'")
            if not tok:
                continue
            target: str | None = None
            if tok in tracked_set:
                target = tok
            elif "/" not in tok:
                # Bare basename — only resolve if uniquely tracked
                hits = basename_paths.get(tok)
                if hits and len(hits) == 1:
                    target = hits[0]
            if target and target != src and target not in seen_targets_for_src:
                references_in[target].add(src)
                seen_targets_for_src.add(target)

    # --- Lens 1: orphan files ------------------------------------------------
    # A file no other tracked file mentions. We exclude anything in
    # commonly-orphan-but-fine directories (.github/, root .gitignore-style).
    def is_excused_orphan(path: str) -> bool:
        # Top-level config files, GitHub workflows, etc. are orphan by design.
        excused_prefixes = (
            ".github/",
            ".gitignore", ".dockerignore", ".gitattributes",
            "LICENSE", "README", "CHANGELOG", "NOTICE",
            "package.json", "package-lock.json", "tsconfig.json",
            "Makefile", "requirements.txt",
            ".env.example",
        )
        for px in excused_prefixes:
            if path == px or path.startswith(px):
                return True
        return False

    orphans = [p for p in tracked if not references_in.get(p) and not is_excused_orphan(p)]

    # --- Lens 2: orphan directories -----------------------------------------
    # A dir where >threshold of its files are orphans AND it has >= min files.
    files_by_dir: dict[str, list[str]] = defaultdict(list)
    orphan_set = set(orphans)
    for p in tracked:
        files_by_dir[str(Path(p).parent)].append(p)

    orphan_dirs: list[tuple[str, int, int]] = []  # (dir, orphan_count, total)
    for d, files in files_by_dir.items():
        if d == "." or d == "":
            continue
        if len(files) < args.min_dir_files:
            continue
        oc = sum(1 for f in files if f in orphan_set)
        ratio = oc / len(files) if files else 0
        if ratio >= args.orphan_dir_threshold:
            orphan_dirs.append((d, oc, len(files)))
    orphan_dirs.sort(key=lambda t: -t[2])  # largest first

    # --- Lens 3: build-output / dead-tissue directory shapes ---------------
    classified: list[tuple[str, str, float, int]] = []  # (dir, label, conf, file_count)
    for d, files in files_by_dir.items():
        if d == "." or d == "":
            continue
        ext_counts: Counter[str] = Counter()
        names: list[str] = []
        for f in files:
            ext_counts[Path(f).suffix.lower()] += 1
            names.append(Path(f).name)
        result = _classify_dir_shape(Path(d).name, ext_counts, names)
        if result:
            label, conf = result
            classified.append((d, label, conf, len(files)))
    classified.sort(key=lambda t: (-t[2], -t[3]))

    # --- Lens 4: large binary blobs with no readers -------------------------
    LARGE_BIN_BYTES = 500_000  # 500KB
    large_dead: list[tuple[str, int]] = []
    for p in tracked:
        if is_text(p):
            continue
        if references_in.get(p):
            continue
        full = repo_root / p
        try:
            sz = full.stat().st_size
        except Exception:
            continue
        if sz >= LARGE_BIN_BYTES:
            large_dead.append((p, sz))
    large_dead.sort(key=lambda t: -t[1])

    if args.json:
        out = {
            "totals": {
                "tracked_files": len(tracked),
                "text_files_scanned": len(text_files),
                "orphans": len(orphans),
                "orphan_dirs": len(orphan_dirs),
                "classified_dirs": len(classified),
                "large_dead": len(large_dead),
            },
            "orphan_files": orphans[: args.top],
            "orphan_dirs": [
                {"dir": d, "orphans": oc, "total": tot}
                for d, oc, tot in orphan_dirs[: args.top]
            ],
            "build_output_signatures": [
                {"dir": d, "label": lbl, "confidence": conf, "files": n}
                for d, lbl, conf, n in classified[: args.top]
            ],
            "large_dead_binaries": [
                {"path": p, "bytes": sz} for p, sz in large_dead[: args.top]
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"Repo sense — {len(tracked)} tracked files, {len(text_files)} scanned for refs\n")

    print(f"=== BUILD-OUTPUT SIGNATURES ({len(classified)}) ===")
    if not classified:
        print("  no directories matched known build-output patterns")
    for d, lbl, conf, n in classified[: args.top]:
        print(f"  {d}  →  {lbl}  (conf={conf:.2f}, {n} files)")
    print()

    print(f"=== ORPHAN DIRECTORIES — high-orphan-ratio, ≥{args.min_dir_files} files ({len(orphan_dirs)}) ===")
    if not orphan_dirs:
        print("  no directories cross the orphan-ratio threshold")
    for d, oc, tot in orphan_dirs[: args.top]:
        print(f"  {d}  →  {oc}/{tot} orphans ({oc/tot*100:.0f}%)")
    print()

    print(f"=== LARGE DEAD BINARIES — >500KB, no readers ({len(large_dead)}) ===")
    if not large_dead:
        print("  no large binary blobs without readers")
    for p, sz in large_dead[: args.top]:
        print(f"  {sz/1024/1024:5.2f} MB  {p}")
    print()

    print(f"=== ORPHAN FILES — no in-repo references ({len(orphans)}) ===")
    print(f"  Showing top {args.top}; many of these may be intentional (config,")
    print(f"  docs, scripts run by external triggers). Worth a slow read.")
    for p in orphans[: args.top]:
        print(f"  {p}")
    print()

    print("Lens caveat: reference graph is path-string scanning, not import")
    print("resolution. False-orphans are recoverable; surfaced dead tissue is")
    print("the win. Read with the body.")
    return 0


# ---------------------------------------------------------------------------
# chain — sense the idea → spec → code → test artery
#
# This is the body's main circulatory question: every idea should land
# in code that runs and is tested. Today the body has separate sensors
# for each segment (specs/INDEX drift, missing source paths). This
# walks the chain end-to-end and surfaces where it breaks.
#
# v1: walks specs/ and ideas/ filesystem (frontmatter), checks file
# existence + test-file resolution. Witness segment (correlation with
# live deploys) is a future extension.
# ---------------------------------------------------------------------------


def _parse_spec_frontmatter(path: Path) -> "dict | None":
    """Lift the YAML frontmatter from a markdown file. Returns None on
    parse failure or no frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fm_text = text[3:end].strip()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(fm_text) or {}
    except Exception:
        # Fallback to a tolerant key-value parser
        out: dict = {}
        for line in fm_text.splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out


def _extract_test_paths(test_command) -> list[str]:
    """Extract pytest test-file paths from a spec.test command. Accepts
    a string or a list of strings (some specs use YAML list form)."""
    if not test_command:
        return []
    if isinstance(test_command, list):
        text = " \n ".join(str(x) for x in test_command)
    else:
        text = str(test_command)
    import re
    paths = set()
    for m in re.finditer(r"\b(?:api/)?tests/[\w/]+\.py", text):
        path = m.group(0)
        if not path.startswith("api/"):
            path = f"api/{path}"
        paths.add(path)
    return sorted(paths)


def _spec_source_paths(fm: dict) -> list[str]:
    """source: in spec frontmatter is a list of {file, symbols}. Return
    just the file paths."""
    src = fm.get("source", [])
    if not isinstance(src, list):
        return []
    out = []
    for entry in src:
        if isinstance(entry, dict) and "file" in entry:
            out.append(str(entry["file"]))
        elif isinstance(entry, str):
            out.append(entry)
    return out


def cmd_chain(args: argparse.Namespace) -> int:  # noqa: C901 — chain walk
    """Walk the idea→spec→code→test artery for every spec; surface where
    each chain breaks."""
    from collections import defaultdict

    repo_root = REPO_ROOT
    spec_dir = repo_root / "specs"
    idea_dir = repo_root / "ideas"
    skip_specs = {"INDEX.md", "TEMPLATE.md", "MANIFEST.md"}
    skip_ideas = {"INDEX.md", "TEMPLATE.md"}

    spec_files = sorted(p for p in spec_dir.glob("*.md") if p.name not in skip_specs)
    idea_files = sorted(p for p in idea_dir.glob("*.md") if p.name not in skip_ideas)

    # ---- Spec rows: parse each spec, walk its references --------------------
    spec_rows: list[dict] = []
    for sp in spec_files:
        fm = _parse_spec_frontmatter(sp) or {}
        slug = sp.stem
        idea_id = fm.get("idea_id") or fm.get("idea")
        sources = _spec_source_paths(fm)
        test_cmd = fm.get("test", "") or ""
        test_paths = _extract_test_paths(test_cmd)

        sources_present = []
        sources_missing = []
        for s in sources:
            full = repo_root / s
            (sources_present if full.exists() else sources_missing).append(s)

        tests_present = []
        tests_missing = []
        for t in test_paths:
            full = repo_root / t
            (tests_present if full.exists() else tests_missing).append(t)

        spec_rows.append({
            "slug": slug,
            "path": str(sp.relative_to(repo_root)),
            "idea_id": idea_id,
            "sources": sources,
            "sources_present": sources_present,
            "sources_missing": sources_missing,
            "tests_declared": test_paths,
            "tests_present": tests_present,
            "tests_missing": tests_missing,
            "test_cmd": test_cmd,
            "status": fm.get("status", "?"),
        })

    # Index by idea
    specs_by_idea: dict[str, list[dict]] = defaultdict(list)
    for r in spec_rows:
        if r["idea_id"]:
            specs_by_idea[r["idea_id"]].append(r)

    # ---- Idea rows: which ideas have specs? --------------------------------
    idea_rows: list[dict] = []
    for ip in idea_files:
        fm = _parse_spec_frontmatter(ip) or {}
        slug = ip.stem
        # Ideas reference specs by listing names; index via specs_by_idea
        linked = specs_by_idea.get(slug, [])
        idea_rows.append({
            "slug": slug,
            "path": str(ip.relative_to(repo_root)),
            "spec_count": len(linked),
            "specs": [s["slug"] for s in linked],
        })

    # Drilldown modes
    if args.spec:
        target = next((r for r in spec_rows if r["slug"] == args.spec), None)
        if not target:
            print(f"No spec found for slug: {args.spec}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(target, indent=2))
            return 0
        print(f"Spec: {target['slug']}  status={target['status']}")
        print(f"  idea_id: {target['idea_id'] or '(none — orphan spec)'}")
        print(f"  sources ({len(target['sources'])}):")
        for s in target["sources_present"]:
            print(f"    ✓ {s}")
        for s in target["sources_missing"]:
            print(f"    ✗ {s}  (missing on disk)")
        print(f"  test cmd: {target['test_cmd'] or '(none)'}")
        for t in target["tests_present"]:
            print(f"    ✓ {t}")
        for t in target["tests_missing"]:
            print(f"    ✗ {t}  (missing on disk)")
        return 0

    if args.idea:
        target = next((r for r in idea_rows if r["slug"] == args.idea), None)
        if not target:
            print(f"No idea found for slug: {args.idea}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(target, indent=2))
            return 0
        print(f"Idea: {target['slug']}")
        if not target["specs"]:
            print("  no specs link to this idea (broken at spec segment)")
        else:
            print(f"  {target['spec_count']} specs:")
            for sname in target["specs"]:
                row = next(r for r in spec_rows if r["slug"] == sname)
                src_ok = len(row["sources_present"])
                src_miss = len(row["sources_missing"])
                test_ok = len(row["tests_present"])
                test_miss = len(row["tests_missing"])
                src_mark = "✓" if src_miss == 0 and row["sources"] else ("·" if not row["sources"] else "✗")
                test_mark = "✓" if test_miss == 0 and row["tests_declared"] else ("·" if not row["tests_declared"] else "✗")
                print(f"    {src_mark}{test_mark}  {sname}  source={src_ok}/{src_ok+src_miss}  test={test_ok}/{test_ok+test_miss}")
        return 0

    # ---- Aggregate signatures ---------------------------------------------
    orphan_specs = [r for r in spec_rows if not r["idea_id"]]
    specs_no_source = [r for r in spec_rows if not r["sources"]]
    specs_with_missing_source = [r for r in spec_rows if r["sources_missing"]]
    specs_no_test = [r for r in spec_rows if not r["tests_declared"]]
    specs_with_missing_test = [r for r in spec_rows if r["tests_missing"]]
    specs_full_chain = [
        r for r in spec_rows
        if r["idea_id"]
        and r["sources"] and not r["sources_missing"]
        and r["tests_declared"] and not r["tests_missing"]
    ]
    ideas_no_spec = [r for r in idea_rows if r["spec_count"] == 0]

    if args.json:
        out = {
            "totals": {
                "ideas": len(idea_rows),
                "specs": len(spec_rows),
                "specs_full_chain": len(specs_full_chain),
                "orphan_specs": len(orphan_specs),
                "specs_with_missing_source": len(specs_with_missing_source),
                "specs_with_missing_test": len(specs_with_missing_test),
                "ideas_no_spec": len(ideas_no_spec),
            },
            "specs_with_missing_source": [
                {
                    "slug": r["slug"], "missing": r["sources_missing"],
                    "present": len(r["sources_present"]),
                }
                for r in specs_with_missing_source[: args.top]
            ],
            "specs_with_missing_test": [
                {"slug": r["slug"], "missing": r["tests_missing"]}
                for r in specs_with_missing_test[: args.top]
            ],
            "specs_no_test_declared": [r["slug"] for r in specs_no_test[: args.top]],
            "orphan_specs": [r["slug"] for r in orphan_specs[: args.top]],
            "ideas_no_spec": [r["slug"] for r in ideas_no_spec[: args.top]],
            "full_chain_specs": [r["slug"] for r in specs_full_chain[: args.top]],
        }
        print(json.dumps(out, indent=2))
        return 0

    # Human-readable output
    print(f"Chain sense — {len(idea_rows)} ideas → {len(spec_rows)} specs → code → tests\n")

    print(f"=== HEALTHY ARTERIES — full chain reachable ({len(specs_full_chain)}/{len(spec_rows)}) ===")
    for r in specs_full_chain[: args.top]:
        srcs = len(r["sources_present"])
        tsts = len(r["tests_present"])
        print(f"  ✓✓ {r['slug']}  idea={r['idea_id']}  src={srcs}  test={tsts}")
    if len(specs_full_chain) > args.top:
        print(f"  ... and {len(specs_full_chain) - args.top} more")
    print()

    print(f"=== BROKEN AT CODE — spec exists, source files missing ({len(specs_with_missing_source)}) ===")
    for r in specs_with_missing_source[: args.top]:
        miss = ", ".join(r["sources_missing"][:3])
        extra = "" if len(r["sources_missing"]) <= 3 else f" + {len(r['sources_missing']) - 3} more"
        print(f"  ✗  {r['slug']}: missing {miss}{extra}")
    print()

    print(f"=== BROKEN AT TEST — spec exists, test file missing ({len(specs_with_missing_test)}) ===")
    for r in specs_with_missing_test[: args.top]:
        miss = ", ".join(r["tests_missing"])
        print(f"  ✗  {r['slug']}: missing {miss}")
    print()

    print(f"=== NO TEST DECLARED — spec has no test: frontmatter ({len(specs_no_test)}) ===")
    for r in specs_no_test[: args.top]:
        print(f"  ·  {r['slug']}  status={r['status']}")
    if len(specs_no_test) > args.top:
        print(f"  ... and {len(specs_no_test) - args.top} more")
    print()

    print(f"=== NO SOURCE DECLARED — spec has no source: frontmatter ({len(specs_no_source)}) ===")
    for r in specs_no_source[: args.top]:
        print(f"  ·  {r['slug']}  status={r['status']}")
    if len(specs_no_source) > args.top:
        print(f"  ... and {len(specs_no_source) - args.top} more")
    print()

    print(f"=== ORPHAN SPECS — no idea_id ({len(orphan_specs)}) ===")
    for r in orphan_specs[: args.top]:
        print(f"  ?  {r['slug']}")
    if len(orphan_specs) > args.top:
        print(f"  ... and {len(orphan_specs) - args.top} more")
    print()

    print(f"=== IDEAS WITHOUT SPECS — thinking that hasn't been planned ({len(ideas_no_spec)}) ===")
    for r in ideas_no_spec[: args.top]:
        print(f"  ?  {r['slug']}")
    print()

    print("Drill into one with `coh substrate chain --idea <slug>` or `--spec <slug>`.")
    print("Lens caveat: 'no source: declared' may be intentional for non-code specs")
    print("(governance, lineage, contracts). Read with the body.")
    return 0


# ---------------------------------------------------------------------------
# shape-check — given a draft .md, surface cells with the same shape
# ---------------------------------------------------------------------------


def cmd_shape_check(args: argparse.Namespace) -> int:
    """Compute the Blueprint shape for a draft .md file and report cells
    that already have the same shape.

    Useful when authoring a new spec/idea/concept: catches the case where
    you're instantiating an existing structural pattern. Surfaces five
    cells with matching shape so you can decide whether to align with
    them, refactor them, or genuinely introduce a new pattern.
    """
    from app.services.substrate import (
        find_equivalent_cells,
        ingest_concept_file,
        ingest_idea_file,
        ingest_memory_file,
        ingest_presence_file,
        ingest_spec_file,
        parse_markdown_file,
    )
    from app.services.substrate.markdown_frontend import (
        BID_concept,
        BID_idea,
        BID_memory,
        BID_presence,
        BID_spec,
        frontmatter_to_blueprint,
    )

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path not found: {path}", file=sys.stderr)
        return 1

    # Infer domain from path or use --domain
    domain = args.domain
    if not domain:
        if "specs/" in str(path):
            domain = "spec"
        elif "ideas/" in str(path):
            domain = "idea"
        elif "vision-kb/concepts/" in str(path):
            domain = "concept"
        elif "presences/" in str(path):
            domain = "presence"
        else:
            domain = "memory"

    domain_bp = {
        "spec": BID_spec, "idea": BID_idea, "concept": BID_concept,
        "presence": BID_presence, "memory": BID_memory,
    }.get(domain, BID_memory)()

    parsed = parse_markdown_file(path)

    with session_scope() as session:
        # Compute the shape this draft would have
        shape = frontmatter_to_blueprint(session, parsed.frontmatter, domain_bp)
        # Find cells with this exact shape
        equivalents = find_equivalent_cells(session, shape)

        if args.json:
            print(json.dumps({
                "path": str(path),
                "domain": domain,
                "blueprint": str(shape),
                "equivalent_count": len(equivalents),
                "equivalents": [
                    {"domain": c.domain, "name": c.name, "source_path": c.source_path}
                    for c in equivalents[:10]
                ],
            }, indent=2))
            return 0

        print(f"Shape-check: {path.name}")
        print(f"  domain: {domain}")
        print(f"  blueprint: {shape}")
        print(f"  frontmatter keys: {sorted(parsed.frontmatter.keys())}")

        if not equivalents:
            print(f"\n  ✓ No existing cells share this exact shape.")
            print(f"  This draft introduces a new structural pattern in the body.")
            return 0

        print(f"\n  ⚠ {len(equivalents)} existing cells share this shape:")
        for eq in equivalents[:10]:
            print(f"    [{eq.domain}] {eq.name}")
            if eq.source_path:
                print(f"        {eq.source_path}")
        if len(equivalents) > 10:
            print(f"    ... and {len(equivalents) - 10} more")

        print(f"\n  Consider:")
        print(f"    - Are these cells the same family (intentional pattern)?")
        print(f"    - Should this draft align with them, or differentiate?")
        print(f"    - Is one of them a candidate to merge with?")
        return 0


# ---------------------------------------------------------------------------
# ingest-paths — auto-ingest changed files (suitable for git hooks / CI)
# ---------------------------------------------------------------------------


def cmd_ingest_paths(args: argparse.Namespace) -> int:
    """Re-ingest a list of changed paths into the substrate.

    Suitable for use in a git post-commit / post-merge hook or CI step
    so the substrate stays current with the body's tissue. Detects each
    path's domain from its location (specs/, ideas/, etc.) and dispatches
    to the right ingester.
    """
    paths: list[Path] = []
    if args.from_stdin:
        for line in sys.stdin:
            line = line.strip()
            if line:
                paths.append(Path(line))
    paths.extend(Path(p) for p in args.paths)

    if not paths:
        print("ingest-paths: no paths provided", file=sys.stderr)
        return 1

    from app.services.substrate import (
        ingest_concept_file,
        ingest_idea_file,
        ingest_memory_file,
        ingest_presence_file,
        ingest_spec_file,
    )

    DOMAIN_INGESTERS = {
        "spec": ingest_spec_file,
        "idea": ingest_idea_file,
        "concept": ingest_concept_file,
        "presence": ingest_presence_file,
        "memory": ingest_memory_file,
    }

    def _domain_for(path: Path) -> str | None:
        # Accept both relative and absolute paths
        s = str(path).replace("\\", "/")
        parts = s.split("/")
        if "specs" in parts and not path.name.startswith(("INDEX", "TEMPLATE", "MANIFEST")):
            return "spec"
        if "ideas" in parts and not path.name.startswith(("INDEX", "TEMPLATE")):
            return "idea"
        if "concepts" in parts and "vision-kb" in parts and not path.name.startswith(("INDEX", "SCHEMA", "LOG")):
            return "concept"
        if "presences" in parts and not path.name.startswith(("INDEX", "README")):
            return "presence"
        if "memory" in parts and path.name.upper() != "MEMORY.MD":
            return "memory"
        return None

    success = skipped = failed = 0
    with session_scope() as session:
        for path in paths:
            if not path.exists() or path.is_dir() or path.suffix != ".md":
                skipped += 1
                continue
            domain = _domain_for(path)
            if domain is None:
                skipped += 1
                continue
            try:
                # Resolve to absolute so source_path is consistent across
                # callers (the hook, manual annotate, the legacy ingest path).
                cell, bp_id, ctor_id = DOMAIN_INGESTERS[domain](session, path.resolve())
                success += 1
                print(f"  [{domain}] {path.name}: bp={bp_id}")
            except Exception as exc:
                failed += 1
                print(f"  ! failed {path.name}: {exc}", file=sys.stderr)
        session.commit()

    print(f"\ningest-paths: {success} ingested, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
