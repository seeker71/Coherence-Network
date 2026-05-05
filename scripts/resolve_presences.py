#!/usr/bin/env python3
"""Backfill image_url + tagline on presence nodes.

The inspired-by resolver fills these when a node is first minted, but
many older nodes landed before the resolver matured — or had bare
canonical pages on the day of capture — and now sit in the graph with
empty hero art and empty taglines. This worker walks the field, fetches
each node's canonical_url + every URL in presences[], reads og:image and
og:description, and writes back the strongest signal.

Usage:

    # Single node
    python3 scripts/resolve_presences.py --id contributor:abc123

    # Walk every presence missing image or tagline
    python3 scripts/resolve_presences.py --all

    # Re-resolve everything (overwrite existing image/tagline)
    python3 scripts/resolve_presences.py --all --force

    # Cap a partial backfill
    python3 scripts/resolve_presences.py --all --limit 50

Idempotent — re-running with the same flags walks the same set and
skips anything already resolved (unless --force is set).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.services import presence_resolver  # noqa: E402


def _print_summary(results: list[dict]) -> None:
    summary = presence_resolver.summarize(results)
    print()
    print(
        f"nodes scanned: {summary['scanned']}, "
        f"resolved image: {summary['resolved_image']}, "
        f"resolved tagline: {summary['resolved_tagline']}, "
        f"skipped: {summary['skipped']}"
    )


def _print_one(result: dict) -> None:
    nid = result.get("node_id", "?")
    skipped = result.get("skipped_reason")
    if skipped:
        print(f"  {nid}: skipped ({skipped})")
        return
    parts: list[str] = []
    if result.get("image_resolved"):
        parts.append(f"image←{result.get('image_source')}")
    if result.get("tagline_resolved"):
        parts.append(f"tagline←{result.get('tagline_source')}")
    if not parts:
        parts.append("no change")
    print(f"  {nid}: {', '.join(parts)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--id",
        metavar="NODE_ID",
        help="Resolve a single node by id (e.g. contributor:abc123)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Walk every presence node missing image_url or description",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-resolve nodes that already have both image and tagline",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of nodes resolved (only with --all)",
    )
    args = parser.parse_args(argv)

    if args.id:
        if args.limit is not None:
            print("warning: --limit ignored when --id is set", file=sys.stderr)
        print(f"=== Resolving {args.id} (force={args.force}) ===")
        result = presence_resolver.resolve_one(args.id, force=args.force)
        _print_one(result)
        _print_summary([result])
        return 0

    print(
        f"=== Resolving all presences (force={args.force}, "
        f"limit={args.limit if args.limit is not None else 'none'}) ==="
    )
    results = presence_resolver.resolve_all(limit=args.limit, force=args.force)
    for r in results:
        _print_one(r)
    _print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
