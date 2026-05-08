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
    ingest_memory_file,
    lattice_stats,
)
from app.services.unified_db import session as session_scope


MEMORY_DIR = Path.home() / ".claude/projects/-Users-ursmuff-source-Coherence-Network/memory"


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


def cmd_memories() -> int:
    """Ingest all memory files under the auto-loaded memory directory."""
    if not MEMORY_DIR.exists():
        print(f"Memory directory not found: {MEMORY_DIR}", file=sys.stderr)
        return 1
    md_files = sorted(MEMORY_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files in {MEMORY_DIR}", file=sys.stderr)
        return 1
    # Skip the index — it's not a memory, it's a pointer list
    md_files = [p for p in md_files if p.name.upper() != "MEMORY.MD"]
    print(f"Ingesting {len(md_files)} memory files from {MEMORY_DIR}")
    return cmd_ingest(md_files)


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
    if args.memories:
        return cmd_memories()
    if args.equivalent:
        return cmd_equivalent(args.equivalent[0], args.equivalent[1])
    if args.paths:
        return cmd_ingest([Path(p) for p in args.paths])
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
