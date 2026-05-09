#!/usr/bin/env python3
"""Ingest markdown-with-frontmatter files into the coherence-substrate.

Phase 3 vertical slice. Reads `.md` files (memory files for now, with the
domain extending in phase 4 to specs/concepts/ideas/presences) and
populates the substrate_nodes + substrate_named_cells tables.

Usage:
    python3 scripts/substrate_ingest.py <path>...
    python3 scripts/substrate_ingest.py --memories
    python3 scripts/substrate_ingest.py --stats

Examples:
    # Ingest a single memory file
    python3 scripts/substrate_ingest.py docs/...

    # Ingest all memory files in the auto-loaded MEMORY directory
    python3 scripts/substrate_ingest.py --memories

    # Just print lattice stats
    python3 scripts/substrate_ingest.py --stats
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate import (
    find_equivalent_cells,
    ingest_concept_file,
    ingest_idea_file,
    ingest_memory_file,
    ingest_presence_file,
    ingest_spec_file,
    lattice_stats,
)
from app.services.unified_db import session as session_scope


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


def cmd_ingest(paths: list[Path]) -> int:
    with session_scope() as session:
        for path in paths:
            if not path.exists() or path.is_dir():
                print(f"  skip (not a file): {path}", file=sys.stderr)
                continue
            if path.suffix != ".md":
                print(f"  skip (not .md): {path}", file=sys.stderr)
                continue
            cell, bp_id, ctor_id = ingest_memory_file(session, path)
            print(
                f"  ingested {path.name}: cell_id={cell.cell_id} "
                f"blueprint={bp_id} ctor={ctor_id}"
            )
        session.commit()
    return 0


def cmd_ingest_domain(domain: str) -> int:
    """Ingest all .md files for a given domain."""
    if domain not in _INGESTERS:
        print(f"Unknown domain: {domain}. Choose from {list(_INGESTERS)}", file=sys.stderr)
        return 1
    base, ingester, filter_fn = _INGESTERS[domain]
    if not base.exists():
        print(f"{domain} directory not found: {base}", file=sys.stderr)
        return 1
    md_files = sorted([p for p in base.glob("*.md") if filter_fn(p)])
    if not md_files:
        print(f"No {domain} files in {base}", file=sys.stderr)
        return 0
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


def cmd_memories() -> int:
    return cmd_ingest_domain("memory")


def cmd_backfill_all() -> int:
    """Ingest all five domains."""
    rc = 0
    for domain in ("memory", "spec", "idea", "concept", "presence"):
        rc |= cmd_ingest_domain(domain)
    return rc


def cmd_stats() -> int:
    with session_scope() as session:
        stats = lattice_stats(session)
        print("Coherence-substrate lattice stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    return 0


def cmd_equivalent(domain: str, name: str) -> int:
    """Find structurally-equivalent cells to the given (domain, name)."""
    from app.services.substrate import lookup_cell
    with session_scope() as session:
        cell = lookup_cell(session, domain, name)
        if cell is None:
            print(f"No cell found for ({domain}, {name})", file=sys.stderr)
            return 1
        print(f"Cell: {domain}/{name}")
        print(f"  blueprint={cell.blueprint}")
        print(f"  source_path={cell.source_path}")
        equivalents = find_equivalent_cells(
            session, cell.blueprint, exclude_name=cell.name
        )
        if not equivalents:
            print(f"  no structurally equivalent cells")
        else:
            print(f"  structurally equivalent cells ({len(equivalents)}):")
            for eq in equivalents:
                print(f"    - {eq.domain}/{eq.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files to ingest")
    parser.add_argument(
        "--memories",
        action="store_true",
        help="Ingest all auto-loaded memory files",
    )
    parser.add_argument(
        "--specs",
        action="store_true",
        help="Ingest all spec files",
    )
    parser.add_argument(
        "--ideas",
        action="store_true",
        help="Ingest all idea files",
    )
    parser.add_argument(
        "--concepts",
        action="store_true",
        help="Ingest all vision-kb concept files",
    )
    parser.add_argument(
        "--presences",
        action="store_true",
        help="Ingest all presence files",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all five domains (memory, spec, idea, concept, presence)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print lattice stats",
    )
    parser.add_argument(
        "--equivalent",
        nargs=2,
        metavar=("DOMAIN", "NAME"),
        help="Find structurally-equivalent cells to (DOMAIN, NAME)",
    )
    args = parser.parse_args(argv)

    if args.stats:
        return cmd_stats()
    if args.all:
        return cmd_backfill_all()
    if args.memories:
        return cmd_ingest_domain("memory")
    if args.specs:
        return cmd_ingest_domain("spec")
    if args.ideas:
        return cmd_ingest_domain("idea")
    if args.concepts:
        return cmd_ingest_domain("concept")
    if args.presences:
        return cmd_ingest_domain("presence")
    if args.equivalent:
        return cmd_equivalent(args.equivalent[0], args.equivalent[1])
    if args.paths:
        return cmd_ingest([Path(p) for p in args.paths])
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
