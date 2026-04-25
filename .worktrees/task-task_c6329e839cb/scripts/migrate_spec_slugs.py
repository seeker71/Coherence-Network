#!/usr/bin/env python3
"""Migrate spec slugs: strip numeric prefixes from spec IDs everywhere.

Phase 0: Rename spec files on disk (NNN-foo.md → foo.md)
Phase 1: Re-key EXPLICIT_SPEC_IDEA_MAP in seed_db.py
Phase 2: Update hardcoded spec ID references in source code
Phase 3: Update config/spec_prefix_canonical_map.json
Phase 4: Regenerate specs/INDEX.md

Usage:
    python3 scripts/migrate_spec_slugs.py --dry-run   # preview changes
    python3 scripts/migrate_spec_slugs.py              # execute migration
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
PREFIX_RE = re.compile(r"^(\d{3})-(.+)$")


def strip_prefix(slug: str) -> str:
    """Strip leading NNN- prefix from a spec slug."""
    m = PREFIX_RE.match(slug)
    return m.group(2) if m else slug


def build_rename_map() -> dict[str, str]:
    """Map old filenames → new filenames for spec files on disk."""
    renames = {}
    for f in sorted(SPECS_DIR.glob("*.md")):
        if f.name in ("INDEX.md", "TEMPLATE.md"):
            continue
        m = PREFIX_RE.match(f.stem)
        if m:
            new_name = f"{m.group(2)}.md"
            renames[f.name] = new_name
    return renames


# ---------------------------------------------------------------------------
# Phase 0: Rename spec files
# ---------------------------------------------------------------------------

def phase0_rename_files(renames: dict[str, str], dry_run: bool) -> int:
    count = 0
    for old_name, new_name in sorted(renames.items()):
        old_path = SPECS_DIR / old_name
        new_path = SPECS_DIR / new_name
        if new_path.exists():
            print(f"  SKIP {old_name} → {new_name} (target exists)")
            continue
        if dry_run:
            print(f"  WOULD rename {old_name} → {new_name}")
        else:
            old_path.rename(new_path)
            print(f"  RENAMED {old_name} → {new_name}")
        count += 1
    return count


# ---------------------------------------------------------------------------
# Phase 1: Re-key EXPLICIT_SPEC_IDEA_MAP in seed_db.py
# ---------------------------------------------------------------------------

def phase1_rekey_seed_map(dry_run: bool) -> int:
    seed_file = REPO_ROOT / "scripts" / "seed_db.py"
    content = seed_file.read_text()

    # Match lines like:    "NNN-slug-name": "idea-id",
    pattern = re.compile(r'(\s*)"(\d{3})-([^"]+)"(\s*:\s*"[^"]+")')
    new_lines = []
    count = 0
    for line in content.splitlines(keepends=True):
        m = pattern.search(line)
        if m:
            indent, _prefix, slug, rest = m.groups()
            new_line = line[:m.start()] + f'{indent}"{slug}"{rest}' + line[m.end():]
            new_lines.append(new_line)
            count += 1
        else:
            new_lines.append(line)

    if count and not dry_run:
        seed_file.write_text("".join(new_lines))
    print(f"  Re-keyed {count} entries in seed_db.py")

    # Also update the comment example: e.g. "001-health-check"
    if not dry_run and count:
        content2 = seed_file.read_text()
        content2 = content2.replace(
            'name = path.stem  # e.g. "001-health-check"',
            'name = path.stem  # e.g. "health-check"',
        )
        seed_file.write_text(content2)

    return count


# ---------------------------------------------------------------------------
# Phase 2: Update hardcoded spec IDs + file paths in source code
# ---------------------------------------------------------------------------

def _find_source_files() -> list[Path]:
    """Find all Python/shell/JSON files to update (excluding specs/ and docs/)."""
    dirs = [
        REPO_ROOT / "api",
        REPO_ROOT / "scripts",
        REPO_ROOT / "mcp-server",
        REPO_ROOT / "config",
    ]
    extensions = {".py", ".sh", ".json"}
    files = []
    for d in dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix in extensions and f.is_file():
                files.append(f)
    # Also include CLAUDE.md
    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        files.append(claude_md)
    return files


def phase2_update_source_refs(renames: dict[str, str], dry_run: bool) -> int:
    """Update spec file path references and hardcoded spec IDs in source code."""
    # Build replacement patterns:
    # 1. File paths: specs/NNN-foo.md → specs/foo.md
    # 2. Spec IDs in strings: "NNN-foo" → "foo" (but only when in spec context)
    # 3. # spec: NNN-foo → # spec: foo

    files = _find_source_files()
    total_changes = 0

    for fpath in files:
        try:
            content = fpath.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue

        original = content

        # Replace spec file path references: specs/NNN-xxx.md → specs/xxx.md
        for old_name, new_name in renames.items():
            content = content.replace(f"specs/{old_name}", f"specs/{new_name}")

        # Replace "# spec: NNN-xxx" comments
        content = re.sub(
            r"# spec: (\d{3})-([a-z])",
            r"# spec: \2",
            content,
        )

        # Replace @spec_traced("NNN-xxx", ...) calls
        content = re.sub(
            r'@spec_traced\("(\d{3})-([^"]+)"',
            r'@spec_traced("\2"',
            content,
        )

        # Replace spec_id="NNN-xxx" in Python code
        content = re.sub(
            r'spec_id="(\d{3})-([^"]+)"',
            r'spec_id="\2"',
            content,
        )

        # Replace "spec_id": "NNN-xxx" in Python/JSON
        content = re.sub(
            r'"spec_id":\s*"(\d{3})-([^"]+)"',
            r'"spec_id": "\2"',
            content,
        )

        if content != original:
            changes = sum(1 for a, b in zip(original.splitlines(), content.splitlines()) if a != b)
            total_changes += changes
            if dry_run:
                print(f"  WOULD update {fpath.relative_to(REPO_ROOT)} ({changes} lines)")
            else:
                fpath.write_text(content)
                print(f"  UPDATED {fpath.relative_to(REPO_ROOT)} ({changes} lines)")

    return total_changes


# ---------------------------------------------------------------------------
# Phase 3: Empty the canonical map
# ---------------------------------------------------------------------------

def phase3_empty_canonical_map(dry_run: bool) -> None:
    config_file = REPO_ROOT / "config" / "spec_prefix_canonical_map.json"
    if not config_file.exists():
        print("  No canonical map file found — skipping")
        return

    new_content = """{
  "generated_at": "2026-04-06",
  "policy": "All spec files now use plain slugs (no numeric prefixes). This map is no longer needed.",
  "duplicates": {}
}
"""
    if dry_run:
        print("  WOULD empty config/spec_prefix_canonical_map.json")
    else:
        config_file.write_text(new_content)
        print("  EMPTIED config/spec_prefix_canonical_map.json")


# ---------------------------------------------------------------------------
# Phase 4: Regenerate specs/INDEX.md
# ---------------------------------------------------------------------------

def phase4_regenerate_index(dry_run: bool) -> None:
    index_path = SPECS_DIR / "INDEX.md"
    spec_files = sorted(
        f for f in SPECS_DIR.glob("*.md")
        if f.name not in ("INDEX.md", "TEMPLATE.md")
    )

    lines = [
        "# Spec Index\n",
        "\n",
        f"**{len(spec_files)} specs** — plain slug convention (no numeric prefixes).\n",
        "\n",
        "| Spec | File |\n",
        "|------|------|\n",
    ]
    for f in spec_files:
        slug = f.stem
        lines.append(f"| {slug} | [{f.name}]({f.name}) |\n")

    content = "".join(lines)

    if dry_run:
        print(f"  WOULD regenerate INDEX.md ({len(spec_files)} entries)")
    else:
        index_path.write_text(content)
        print(f"  REGENERATED INDEX.md ({len(spec_files)} entries)")


# ---------------------------------------------------------------------------
# Phase 5: Update CLAUDE.md spec ID conventions
# ---------------------------------------------------------------------------

def phase5_update_claude_md(dry_run: bool) -> None:
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return
    content = claude_md.read_text()
    original = content

    # Update the convention example
    content = content.replace(
        "Spec IDs = file stems (e.g. `002-agent-orchestration-api`) — same as registry key",
        "Spec IDs = file stems (e.g. `agent-orchestration-api`) — same as registry key",
    )

    if content != original:
        if dry_run:
            print("  WOULD update CLAUDE.md spec ID convention example")
        else:
            claude_md.write_text(content)
            print("  UPDATED CLAUDE.md spec ID convention example")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate spec slugs: strip numeric prefixes")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    args = parser.parse_args()

    renames = build_rename_map()
    print(f"\nSpec slug migration — {len(renames)} files to rename\n")

    print("Phase 0: Rename spec files")
    n0 = phase0_rename_files(renames, args.dry_run)

    print("\nPhase 1: Re-key EXPLICIT_SPEC_IDEA_MAP")
    n1 = phase1_rekey_seed_map(args.dry_run)

    print("\nPhase 2: Update source code references")
    n2 = phase2_update_source_refs(renames, args.dry_run)

    print("\nPhase 3: Empty canonical map")
    phase3_empty_canonical_map(args.dry_run)

    print("\nPhase 4: Regenerate INDEX.md")
    phase4_regenerate_index(args.dry_run)

    print("\nPhase 5: Update CLAUDE.md")
    phase5_update_claude_md(args.dry_run)

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Done: {n0} files renamed, {n1} map entries re-keyed, {n2} source lines updated")


if __name__ == "__main__":
    main()
