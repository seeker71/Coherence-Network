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
