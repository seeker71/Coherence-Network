#!/usr/bin/env python3
"""Add clickable cross-links to specs INDEX and spec files for GitHub navigation.

Three fixes:
1. Specs INDEX — link every row to its spec file
2. Spec files — add clickable link back to parent idea after frontmatter
3. Spec files — add clickable links to source files after frontmatter
"""

import re
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO / "specs"
IDEAS_DIR = REPO / "ideas"


def get_spec_files():
    """Return dict mapping spec identifiers to filenames."""
    mapping = {}
    for f in SPECS_DIR.glob("*.md"):
        if f.name in ("INDEX.md", "TEMPLATE.md"):
            continue
        stem = f.stem
        # Extract leading number if present
        m = re.match(r"^(\d+)", stem)
        if m:
            mapping[m.group(1)] = f.name
        # Also map full stem
        mapping[stem] = f.name
    return mapping


def get_idea_files():
    """Return set of idea slugs that have .md files."""
    return {f.stem for f in IDEAS_DIR.glob("*.md") if f.name != "INDEX.md"}


def fix_specs_index(spec_map):
    """Add links to spec rows in INDEX.md."""
    index_path = SPECS_DIR / "INDEX.md"
    content = index_path.read_text()
    lines = content.split("\n")
    changed = 0

    for i, line in enumerate(lines):
        # Match table rows like: | 112 | Prompt A/B ROI Measurement | done |
        # But skip rows that already have links
        m = re.match(r"^(\|\s*)(\d+|[\w-]+)(\s*\|\s*)(.+?)(\s*\|\s*\w+\s*\|)\s*$", line)
        if not m:
            continue
        spec_id = m.group(2).strip()
        title = m.group(4).strip()

        # Skip if already linked
        if "[" in spec_id or "[" in title:
            continue

        # Find matching spec file
        filename = spec_map.get(spec_id)
        if not filename:
            # Try matching by title slug
            continue

        # Link the title to the spec file
        new_title = f"[{title}]({filename})"
        lines[i] = f"{m.group(1)}{spec_id}{m.group(3)}{new_title}{m.group(5)}"
        changed += 1

    index_path.write_text("\n".join(lines))
    print(f"  INDEX.md: linked {changed} rows")


def fix_spec_crosslinks(idea_slugs):
    """Add parent idea link and source file links to each spec file."""
    linked_ideas = 0
    linked_sources = 0

    for spec_file in sorted(SPECS_DIR.glob("*.md")):
        if spec_file.name in ("INDEX.md", "TEMPLATE.md"):
            continue

        content = spec_file.read_text()

        # Parse frontmatter
        if not content.startswith("---"):
            continue

        end = content.index("---", 3)
        frontmatter = content[3:end]
        body = content[end + 3:]

        # Extract idea_id
        idea_match = re.search(r"^idea_id:\s*(.+)$", frontmatter, re.MULTILINE)
        idea_id = idea_match.group(1).strip() if idea_match else None

        # Extract source files
        source_files = re.findall(r"^\s*-\s*file:\s*(.+)$", frontmatter, re.MULTILINE)

        # Build the navigation block
        nav_lines = []

        # Parent idea link
        if idea_id and idea_id in idea_slugs:
            nav_lines.append(f"> **Parent idea**: [{idea_id}](../ideas/{idea_id}.md)")

        # Source file links
        if source_files:
            links = [f"[`{f.strip()}`](../{f.strip()})" for f in source_files]
            nav_lines.append(f"> **Source**: {' | '.join(links)}")

        if not nav_lines:
            continue

        nav_block = "\n".join(nav_lines) + "\n"

        # Check if nav block already exists
        if "> **Parent idea**:" in body or "> **Source**:" in body:
            continue

        # Insert nav block right after frontmatter (before body)
        # Body starts with \n typically
        body_stripped = body.lstrip("\n")
        new_content = content[:end + 3] + "\n\n" + nav_block + "\n" + body_stripped
        spec_file.write_text(new_content)

        if idea_id and idea_id in idea_slugs:
            linked_ideas += 1
        if source_files:
            linked_sources += 1

    print(f"  Spec files: added {linked_ideas} idea links, {linked_sources} source links")


def main():
    spec_map = get_spec_files()
    idea_slugs = get_idea_files()

    print("1. Fixing Specs INDEX links...")
    fix_specs_index(spec_map)

    print("2. Adding crosslinks to spec files...")
    fix_spec_crosslinks(idea_slugs)

    print("Done.")


if __name__ == "__main__":
    main()
