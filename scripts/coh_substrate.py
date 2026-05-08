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
        print(f"{domain} dir not found: {base}", file=sys.stderr)
        return 1
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
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
