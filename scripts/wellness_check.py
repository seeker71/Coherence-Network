#!/usr/bin/env python3
"""Wellness check — a gentle sensing of the body.

Surfaces drift between what the orientation documents claim and what the
filesystem actually holds. Finds files at visible locations that nothing
reaches for. Reports composting progress on known draft trails.

Run: make wellness   (or)   python3 scripts/wellness_check.py

Not an audit. A felt-sense reading. The body stays supple through
continuous tending — this tool is how we notice where tending is needed
without having to stumble over it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files at root that are meant to be there even without incoming refs.
# Config, tooling, canonical orientation, license-style docs.
ROOT_EXEMPT = {
    "CLAUDE.md",
    "AGENTS.md",
    "AGENT.md",
    "README.md",
    "README.template.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
}


def count_files(dir_name: str, exclude: set[str]) -> int:
    d = ROOT / dir_name
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.md") if p.name not in exclude)


def read_first_match(path: Path, pattern: str) -> int | None:
    if not path.exists():
        return None
    m = re.search(pattern, path.read_text())
    return int(m.group(1)) if m else None


def git_grep_refs(name: str) -> list[str]:
    """Files that mention `name`, excluding itself and known noise dirs."""
    r = subprocess.run(
        ["git", "grep", "-l", "--no-color", name, "--",
         "*.md", "*.py", "*.ts", "*.tsx", "*.sh", "*.json",
         "*.yml", "*.yaml", "Makefile", "*.toml"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return [line for line in r.stdout.splitlines() if line and line != name]


def sense_proprioception() -> list[str]:
    findings = []

    # specs/INDEX.md
    actual = count_files("specs", {"INDEX.md", "TEMPLATE.md"})
    claimed = read_first_match(ROOT / "specs" / "INDEX.md", r"(\d+)\s+specs\s+\(")
    if claimed is None:
        findings.append(f"  specs/INDEX.md — count pattern not found; cannot verify")
    elif claimed == actual:
        findings.append(f"  specs/INDEX.md — aligned ({actual} specs)")
    else:
        findings.append(f"  specs/INDEX.md — drift: INDEX claims {claimed}, body has {actual}")

    # ideas/INDEX.md — "N super-ideas"
    actual_i = count_files("ideas", {"INDEX.md"})
    claimed_i = read_first_match(ROOT / "ideas" / "INDEX.md", r"(\d+)\s+super-ideas")
    if claimed_i is None:
        findings.append(f"  ideas/INDEX.md — count pattern not found; cannot verify")
    elif claimed_i == actual_i:
        findings.append(f"  ideas/INDEX.md — aligned ({actual_i} super-ideas)")
    else:
        findings.append(f"  ideas/INDEX.md — drift: INDEX claims {claimed_i}, body has {actual_i}")

    # vision-kb/INDEX.md concept count
    # Exclude language variants (lc-name.lang.md) from the concept tally —
    # translations are the same concept in another voice, not separate concepts.
    vkb_concepts_dir = ROOT / "docs" / "vision-kb" / "concepts"
    if vkb_concepts_dir.is_dir():
        actual_c = sum(
            1 for p in vkb_concepts_dir.glob("*.md")
            if p.name.count(".") == 1  # lc-foo.md has one dot; lc-foo.de.md has two
        )
        claimed_c = read_first_match(
            ROOT / "docs" / "vision-kb" / "INDEX.md",
            r"\*\*Concepts\*\*:\s*(\d+)",
        )
        if claimed_c is None:
            findings.append(f"  vision-kb/INDEX.md — concept count pattern not found")
        elif claimed_c == actual_c:
            findings.append(f"  vision-kb/INDEX.md — aligned ({actual_c} concepts)")
        else:
            findings.append(
                f"  vision-kb/INDEX.md — drift: INDEX claims {claimed_c}, body has {actual_c}"
            )

    return findings


def sense_circulation() -> list[str]:
    """Root-level .md files with no incoming references."""
    findings = []
    for p in sorted(ROOT.glob("*.md")):
        if p.name in ROOT_EXEMPT:
            continue
        refs = git_grep_refs(p.name)
        if not refs:
            findings.append(f"  {p.name} — no readers")
    if not findings:
        findings.append("  root is clear; every .md has circulation")
    return findings


def sense_metabolism() -> list[str]:
    """Progress on known draft trails."""
    findings = []
    drafts = sorted(ROOT.glob("docs/LIVING_COLLECTIVE_*.md"))
    if not drafts:
        findings.append("  no LIVING_COLLECTIVE_*.md drafts remain at top of docs/")
    else:
        total_lines = sum(sum(1 for _ in p.open()) for p in drafts)
        findings.append(f"  {len(drafts)} drafts remain — {total_lines} lines awaiting home")
        for p in drafts:
            lines = sum(1 for _ in p.open())
            findings.append(f"    · {p.name} ({lines} lines)")
    return findings


def main() -> int:
    print("# Wellness check\n")
    print("A gentle sensing. Not an audit. Drift is the signal,")
    print("not the problem.\n")

    print("## Proprioception — do the maps match the body?\n")
    for line in sense_proprioception():
        print(line)
    print()

    print("## Circulation — what at root has no readers?\n")
    for line in sense_circulation():
        print(line)
    print()

    print("## Metabolism — composting-in-progress\n")
    for line in sense_metabolism():
        print(line)
    print()

    print("(Feedback is the blood. Run me anytime the body")
    print(" feels slightly off; I'll name what I can sense.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
