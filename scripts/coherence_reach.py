#!/usr/bin/env python3
"""coherence_reach — measure where an identity is named across the body.

Walks the repo for textual mentions of an identity (default:
contributor:seeker71 / Urs) and buckets the result by node-domain
(specs, ideas, concepts, presences, lineage, field, people, web,
api, scripts, doc, other). Output is a per-bucket count plus,
optionally, the file list.

This is a referential measure, not a structural one — it answers
"where is this identity named?" not "where is this identity
substrate-equivalent?". The substrate kernel holds Blueprint
identity; this tool sits beside it and reads the body's text.

Honest about what it is: a textual sieve. When the glyph layer
(specs/glyph-render-witness-proof.md) is implemented the same
question can be asked through prev_glyph Merkle walks and the
answer becomes lineage-attested rather than text-grep-attested.
Until then, this is what we have, and what we have is enough to
falsify or confirm narrative claims about reach.

Usage:
    coherence_reach.py                            # Urs, all buckets
    coherence_reach.py contributor:seeker71       # explicit identity
    coherence_reach.py --json                     # machine output
    coherence_reach.py --list <bucket>            # show files in a bucket
    coherence_reach.py --save <path>              # write JSON attestation
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Known identities — extend here as the body gains named contributors.
IDENTITY_ALIASES: dict[str, list[str]] = {
    "contributor:seeker71": [
        r"\bUrs\b",
        r"\bUrs Muff\b",
        r"\burs-muff\b",
        r"\bursmuff\b",
        r"\bseeker71\b",
        r"contributor:seeker71",
        r"/people/urs\b",
    ],
}

# File extensions worth scanning. Binary types and lock/build files excluded.
SCAN_EXTENSIONS = {".md", ".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".txt", ".yaml", ".yml"}

EXCLUDE_DIRS = {
    ".git", "node_modules", ".next", ".venv", "venv",
    "dist", "build", "__pycache__", ".claude",
    ".pytest_cache", ".mypy_cache", "coverage",
}

# Bucket assignment by path prefix. First match wins; order matters.
BUCKET_PREFIXES: list[tuple[str, str]] = [
    ("specs/", "spec"),
    ("ideas/", "idea"),
    ("docs/vision-kb/concepts/", "concept"),
    ("docs/vision-kb/guides/", "guide"),
    ("docs/vision-kb/", "kb-other"),
    ("docs/presences/", "presence"),
    ("docs/lineage/", "lineage"),
    ("docs/field/", "field"),
    ("docs/coherence-substrate/", "substrate-doc"),
    ("docs/", "doc"),
    ("web/content/people/", "people"),
    ("web/content/", "web-content"),
    ("web/", "web"),
    ("api/", "api"),
    ("cli/", "cli"),
    ("scripts/", "scripts"),
    ("mcp-server/", "mcp"),
    ("experiments/", "experiments"),
]


def classify(path: Path) -> str:
    rel = path.as_posix()
    for prefix, name in BUCKET_PREFIXES:
        if rel.startswith(prefix):
            return name
    return "other"


def scan(identity: str) -> dict:
    aliases = IDENTITY_ALIASES.get(identity)
    if aliases is None:
        raise SystemExit(
            f"unknown identity: {identity}\n"
            f"known: {', '.join(IDENTITY_ALIASES)}\n"
            f"to add, edit IDENTITY_ALIASES in scripts/coherence_reach.py"
        )
    pattern = re.compile("|".join(aliases))

    bucket_counts: dict[str, int] = {}
    bucket_files: dict[str, list[str]] = {}
    bucket_mentions: dict[str, int] = {}
    total_files = 0
    total_mentions = 0

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDE_DIRS for part in rel_path.parts):
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            continue
        try:
            text = path.read_text(errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        hits = pattern.findall(text)
        if not hits:
            continue
        rel = rel_path.as_posix()
        bucket = classify(rel_path)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        bucket_mentions[bucket] = bucket_mentions.get(bucket, 0) + len(hits)
        bucket_files.setdefault(bucket, []).append(rel)
        total_files += 1
        total_mentions += len(hits)

    for files in bucket_files.values():
        files.sort()

    return {
        "identity": identity,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_files": total_files,
        "total_mentions": total_mentions,
        "buckets": {
            name: {
                "files": bucket_counts[name],
                "mentions": bucket_mentions[name],
                "paths": bucket_files[name],
            }
            for name in sorted(bucket_counts, key=lambda k: -bucket_counts[k])
        },
    }


def print_human(report: dict, list_bucket: str | None = None) -> None:
    print(f"Reach of {report['identity']} as of {report['measured_at']}")
    print(f"  total files mentioning identity: {report['total_files']}")
    print(f"  total mention count:             {report['total_mentions']}")
    print()
    print(f"  {'bucket':16s} {'files':>6s} {'mentions':>10s}")
    print(f"  {'-' * 16} {'-' * 6} {'-' * 10}")
    for name, data in report["buckets"].items():
        print(f"  {name:16s} {data['files']:6d} {data['mentions']:10d}")

    if list_bucket:
        bucket = report["buckets"].get(list_bucket)
        if bucket is None:
            print(f"\nbucket '{list_bucket}' not found", file=sys.stderr)
            return
        print(f"\nfiles in bucket '{list_bucket}':")
        for path in bucket["paths"]:
            print(f"  {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "identity",
        nargs="?",
        default="contributor:seeker71",
        help="identity to measure (default: contributor:seeker71)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    parser.add_argument("--list", metavar="BUCKET", help="print all file paths in named bucket")
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="also write JSON attestation to PATH (always full report, regardless of --json)",
    )
    args = parser.parse_args(argv)

    report = scan(args.identity)

    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(report, indent=2) + "\n")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report, list_bucket=args.list)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
