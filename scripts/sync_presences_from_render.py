#!/usr/bin/env python3
"""Sync writing-surface presence .md files from the rendering-surface JSON.

The body's discipline (docs/presences/INDEX.md):

    "This is the writing surface. The rendering surface is the production
    graph — each node's `description` field carries the full story."

When a cell is created via the graph (API, ingestion, scheduled export)
without a corresponding `docs/presences/{slug}.md`, the writing surface
falls behind. A future sync from disk to graph would have no anchor for
that cell. This script restores the symmetry: it reads the JSON renderings
in `docs/presence-content/`, and for each cell that lacks a writing-surface
counterpart, it generates a `.md` scaffold reconstructed from the JSON.

The reconstruction round-trips: the JSON's `hero.welcome_md`, `facts`, and
`note_from_body` were authored when the graph was first authored (the
note_from_body even acknowledges itself as "a welcoming scaffold built
from the user's lived testimony"). The script does NOT fabricate — it
reconstitutes the body's existing testimony in writing-surface form.

Tender humans are deferred — real people whose presence files belong to
their own voice or to the user's careful authorship, not to a script.

Usage:
    python3 scripts/sync_presences_from_render.py             # dry-run
    python3 scripts/sync_presences_from_render.py --write     # actually write
    python3 scripts/sync_presences_from_render.py --only slug # one entry

Idempotent: skips any slug that already has docs/presences/{slug}.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path


# Real humans whose writing surface deserves their own voice or careful
# authorship. The script will NOT auto-generate scaffolds for these.
TENDER_HUMANS: set[str] = {
    "urs",
    "ilena",
    "aly-constantine",
    "rocco-tortorella",
    "aubrey-marcus",
    "lex-fridman",
    "matias-de-stefano",
    "elon-musk",
    "tammy-beattie",
    "porangui",
    "bloomurian",
    "joshua-golden",
    # The body itself — written by Urs, not from rendered output
    "coherence-network",
}


REPO = Path(__file__).resolve().parent.parent
PRESENCES_DIR = REPO / "docs" / "presences"
CONTENT_DIR = REPO / "docs" / "presence-content"


def load_json(slug: str) -> dict:
    path = CONTENT_DIR / f"{slug}.json"
    with path.open() as f:
        return json.load(f)


def frontmatter(slug: str, name: str, canonical_url: str | None) -> str:
    """Build the .md frontmatter. `claimed: false` signals the scaffold
    invites the presence (or their author) to replace any part."""
    lines = ["---"]
    lines.append(f"name: {name}")
    if canonical_url:
        lines.append(f"canonical_url: {canonical_url}")
    else:
        lines.append("canonical_url: null")
    lines.append("type: contributor")
    lines.append("contributor_type: HUMAN")
    lines.append("claimed: false")
    lines.append("create_if_missing: true")
    lines.append("---")
    return "\n".join(lines)


def scaffold_body(name: str, en: dict) -> str:
    """Reconstruct a narrative body from the JSON's rendered fields. The
    sections map directly: hero.welcome_md → opening, facts → grounding,
    note_from_body → closing acknowledgment."""
    hero = en.get("hero", {})
    eyebrow = (hero.get("eyebrow") or "").strip()
    welcome = (hero.get("welcome_md") or "").strip()
    facts = en.get("facts", []) or []
    note = (en.get("note_from_body", {}).get("body_md") or "").strip()
    footer = (en.get("footer_md") or "").strip()

    parts: list[str] = [f"# {name}", ""]

    if eyebrow:
        # Eyebrow becomes an italicized opening tag-line.
        parts.append(f"*{eyebrow}*")
        parts.append("")

    if welcome:
        parts.append(welcome)
        parts.append("")

    if facts:
        parts.append("## Grounding")
        parts.append("")
        for f in facts:
            label = (f.get("label") or "").strip()
            value = (f.get("value_md") or "").strip()
            if label and value:
                parts.append(f"- **{label}** — {value}")
        parts.append("")

    if note:
        parts.append(f"## What {name} has given the Coherence Network")
        parts.append("")
        parts.append(note)
        parts.append("")

    if footer:
        parts.append("---")
        parts.append("")
        parts.append(footer)
        parts.append("")

    # Closing scaffold-acknowledgment line so future readers know this is
    # writing-surface synced from the rendering surface, not direct authorship.
    parts.append(
        "*(This page is a writing-surface scaffold synced from the body's "
        "rendering surface — round-tripped from the graph the cell already "
        "lives in. `claimed: false` invites direct authorship to replace "
        "any part of it.)*"
    )

    return "\n".join(parts)


def slug_to_md_path(slug: str) -> Path:
    return PRESENCES_DIR / f"{slug}.md"


def collect_missing(only: str | None = None) -> list[str]:
    """Return slugs whose rendering exists in presence-content but whose
    writing surface .md doesn't exist in presences/."""
    out: list[str] = []
    for json_path in sorted(CONTENT_DIR.glob("*.json")):
        slug = json_path.stem
        if only and slug != only:
            continue
        if slug_to_md_path(slug).exists():
            continue
        out.append(slug)
    return out


def name_from_json(en: dict, slug: str) -> str:
    return en.get("hero", {}).get("name") or slug


def canonical_url_from_json(en: dict) -> str | None:
    # The rendering JSON doesn't carry canonical_url directly; the frontmatter
    # field stays null for scaffolds. Direct authorship can fill it in.
    return None


def generate_md(slug: str) -> str:
    d = load_json(slug)
    en = d.get("en", {})
    name = name_from_json(en, slug)
    fm = frontmatter(slug, name, canonical_url_from_json(en))
    body = scaffold_body(name, en)
    return f"{fm}\n\n{body}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write",
        action="store_true",
        help="Actually write files (default is dry-run)",
    )
    ap.add_argument(
        "--only",
        default=None,
        help="Only process the named slug",
    )
    args = ap.parse_args()

    missing = collect_missing(only=args.only)
    if not missing:
        print("no missing writing-surface .md — the body is symmetric")
        return 0

    to_generate: list[str] = []
    deferred: list[str] = []
    for slug in missing:
        if slug in TENDER_HUMANS:
            deferred.append(slug)
        else:
            to_generate.append(slug)

    print(f"missing writing surface: {len(missing)} total")
    print(f"  → auto-generate scaffold: {len(to_generate)}")
    print(f"  → defer to direct authorship: {len(deferred)}")
    print()

    print("=== AUTO-GENERATE ===")
    for slug in to_generate:
        print(f"  {slug}")
    print()

    print("=== DEFERRED (tender — write by hand) ===")
    for slug in deferred:
        print(f"  {slug}")
    print()

    if not args.write:
        print("(dry-run; pass --write to actually create files)")
        return 0

    written = 0
    for slug in to_generate:
        md = generate_md(slug)
        path = slug_to_md_path(slug)
        path.write_text(md)
        written += 1
        print(f"  wrote {path.relative_to(REPO)}")

    print()
    print(f"wrote {written} scaffold(s)")
    print(f"deferred {len(deferred)} for direct authorship")
    return 0


if __name__ == "__main__":
    sys.exit(main())
