#!/usr/bin/env python3
"""grammar_coverage.py — surface which file formats have Form grammars.

Audit instrument for the question Urs named: *do we have form grammar
for all the file formats in the repo, so we can ingest any file into
form native object space if we choose to?*

The honest answer comes from data: scan the repo for file extensions,
cross-reference against `docs/coherence-substrate/*-grammar.form`,
report what's covered and what's a gap. Pure-read; no writes.

Two modes:
  --summary  (default) — table per extension with file count, grammar
                          path (or '— gap'), and wiring status
  --gaps               — only the extensions with no Form grammar yet

The wiring column tracks whether the grammar is also reachable through
`form_cli convert --tongue <name>` today (json is wired; the rest
are .form skeletons named in their files but not yet plumbed into the
CLI's tongue dispatch).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAMMARS_DIR = REPO_ROOT / "docs" / "coherence-substrate"

# Map known file-extension → (grammar_filename, language_cell_name).
# A nil grammar_filename means "no Form grammar yet". A nil cli_tongue
# means "grammar exists but not wired into form_cli convert yet".
EXTENSION_MAP = {
    "json":  ("json-grammar.form",   "json"),
    "yaml":  ("yaml-grammar.form",   None),
    "yml":   ("yaml-grammar.form",   None),
    "form":  (None,                  None),   # the substrate's own tongue
    "md":    (None,                  None),
    "py":    (None,                  None),
    "ts":    (None,                  None),
    "tsx":   (None,                  None),
    "js":    (None,                  None),
    "mjs":   (None,                  None),
    "rs":    (None,                  None),
    "go":    (None,                  None),
    "sh":    (None,                  None),
    "toml":  (None,                  None),
    "sql":   (None,                  None),
    "html":  (None,                  None),
    "css":   (None,                  None),
    "xml":   (None,                  None),
    "txt":   ("prose-as-recipe.form", None),
    "jsonl": ("json-grammar.form",   None),   # one JSON object per line
    "png":   ("png-grammar.form",    None),
    "jpg":   ("image-grammar.form",  None),
    "jpeg":  ("image-grammar.form",  None),
    "gif":   ("image-grammar.form",  None),
    "svg":   ("image-grammar.form",  None),   # vector — partial fit; honest about it
    "webp":  ("image-grammar.form",  None),
    "mp3":   ("audio-grammar.form",  None),
    "wav":   ("audio-grammar.form",  None),
    "flac":  ("audio-grammar.form",  None),
    "ogg":   ("audio-grammar.form",  None),
    "m4a":   ("audio-grammar.form",  None),
    "fk":    (None,                  None),   # the body's own format-kernel tongue
    "bml":   (None,                  None),   # the BML origin tongue
}


def _scan_repo() -> Counter:
    counts: Counter = Counter()
    skip = (".git", "node_modules", ".claude/worktrees", ".next",
            ".venv", "__pycache__", "dist", "build")
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        parts = p.relative_to(REPO_ROOT).parts
        if any(s in parts or s.replace("/", "") in parts for s in skip):
            continue
        ext = p.suffix.lstrip(".").lower()
        if ext:
            counts[ext] += 1
    return counts


def _existing_grammars() -> set[str]:
    if not GRAMMARS_DIR.exists():
        return set()
    return {p.name for p in GRAMMARS_DIR.glob("*-grammar.form")}


def _classify(ext: str, counts: Counter, existing: set[str]) -> dict:
    n = counts.get(ext, 0)
    grammar, cli_tongue = EXTENSION_MAP.get(ext, (None, None))
    grammar_present = bool(grammar and grammar in existing)
    return {
        "ext":             ext,
        "count":           n,
        "grammar":         grammar if grammar_present else None,
        "grammar_named":   grammar,         # named in the map, may not exist yet
        "cli_wired":       cli_tongue,
        "unknown":         ext not in EXTENSION_MAP,
    }


def print_summary(counts: Counter, existing: set[str]) -> None:
    rows = []
    for ext, n in counts.most_common():
        if n < 2:           # skip rare singletons for legibility
            continue
        rows.append(_classify(ext, counts, existing))

    ext_w = max(6, max((len(r["ext"]) for r in rows), default=6))
    print(f"{'ext':<{ext_w}}  {'count':>6}  {'grammar':<32}  {'cli wired':<12}  status")
    print("-" * (ext_w + 6 + 32 + 12 + 14 + 6))
    for r in rows:
        if r["grammar"]:
            status = "covered"
        elif r["grammar_named"]:
            status = "grammar absent"
        elif r["unknown"]:
            status = "unmapped"
        else:
            status = "gap"
        grammar = r["grammar"] or "—"
        cli = r["cli_wired"] or "—"
        print(f"{r['ext']:<{ext_w}}  {r['count']:>6}  {grammar:<32}  {cli:<12}  {status}")

    covered = sum(1 for r in rows if r["grammar"])
    gaps = sum(1 for r in rows if not r["grammar"])
    print()
    print(f"summary: {covered} extensions covered by a .form grammar, "
          f"{gaps} gaps. {sum(1 for r in rows if r['cli_wired'])} wired "
          f"into form_cli convert.")


def print_gaps(counts: Counter, existing: set[str]) -> None:
    rows = []
    for ext, n in counts.most_common():
        if n < 2:
            continue
        r = _classify(ext, counts, existing)
        if r["grammar"] is None:
            rows.append(r)

    if not rows:
        print("no gaps — every file extension in the repo (≥2 files) has a Form grammar.")
        return

    print("Gaps (file extensions without a Form grammar):")
    print()
    ext_w = max(6, max(len(r["ext"]) for r in rows))
    print(f"  {'ext':<{ext_w}}  {'count':>6}  {'note':<60}")
    print("  " + "-" * (ext_w + 6 + 62))
    for r in rows:
        if r["grammar_named"] and r["grammar_named"] not in existing:
            note = f"named {r['grammar_named']} but file absent"
        elif r["unknown"]:
            note = "no mapping yet"
        else:
            note = "no grammar yet"
        print(f"  {r['ext']:<{ext_w}}  {r['count']:>6}  {note:<60}")
    print()
    print(f"{len(rows)} extension(s) want a Form grammar. Each is one")
    print(f".form Language cell away — see grammar-as-recipe.form for the shape.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gaps", action="store_true",
                        help="show only the extensions with no Form grammar")
    args = parser.parse_args()

    counts = _scan_repo()
    existing = _existing_grammars()

    if args.gaps:
        print_gaps(counts, existing)
    else:
        print_summary(counts, existing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
