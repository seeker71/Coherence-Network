#!/usr/bin/env python3
"""Generate Markdown changelog sections from Conventional Commits between two refs."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict


_TYPE_ORDER = ("feat", "fix", "perf", "refactor", "docs", "test", "chore", "ci", "build")
_TYPE_TITLES = {
    "feat": "### Features",
    "fix": "### Fixes",
    "perf": "### Performance",
    "refactor": "### Refactors",
    "docs": "### Documentation",
    "test": "### Tests",
    "chore": "### Chores",
    "ci": "### CI",
    "build": "### Build",
}

# Conventional Commits 1.0.0: type(scope)!?: description
_CC_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]+\))?(?P<breaking>!)?:\s*(?P<rest>.+)$",
    re.IGNORECASE,
)


def _git(*args: str) -> str:
    out = subprocess.check_output(["git", *args], text=True, stderr=subprocess.STDOUT)
    return out.strip()


def _commits_between(prev_tag: str, head: str) -> list[str]:
    try:
        if prev_tag:
            raw = _git("log", f"{prev_tag}..{head}", "--pretty=format:%s", "--no-merges")
        else:
            raw = _git("log", head, "--pretty=format:%s", "--no-merges", "--max-count=500")
    except subprocess.CalledProcessError:
        raw = _git("log", head, "--pretty=format:%s", "--max-count=200", "--no-merges")
    if not raw:
        return []
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


def _bucket(subject: str) -> tuple[str, str]:
    m = _CC_RE.match(subject)
    if not m:
        return "other", subject
    ctype = m.group("type").lower()
    rest = m.group("rest").strip()
    if m.group("breaking"):
        return "feat", f"BREAKING: {rest}" if ctype != "feat" else rest
    if ctype not in _TYPE_TITLES:
        return "other", subject
    return ctype, rest


def build_markdown(prev_tag: str, head: str, title: str | None) -> str:
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")
    commits = _commits_between(prev_tag, head)
    if not commits:
        lines.append("_No conventional commits in range._")
        return "\n".join(lines)

    buckets: dict[str, list[str]] = defaultdict(list)
    for subj in commits:
        b, text = _bucket(subj)
        buckets[b].append(f"- {text}")

    ordered = [t for t in _TYPE_ORDER if t in buckets]
    for t in sorted(k for k in buckets if k not in _TYPE_ORDER and k != "other"):
        ordered.append(t)
    if "other" in buckets:
        ordered.append("other")

    for b in ordered:
        if b == "other":
            lines.append("### Others")
            lines.extend(buckets["other"])
            lines.append("")
            continue
        label = _TYPE_TITLES.get(b, f"### {b.capitalize()}")
        lines.append(label)
        lines.extend(buckets[b])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--prev-tag",
        default="",
        help="Previous git tag (empty: use full history up to HEAD)",
    )
    p.add_argument("--head", default="HEAD", help="Revision to end the range (default HEAD).")
    p.add_argument(
        "--title",
        default="",
        help="Optional markdown title line (e.g. '## v1.2.3')",
    )
    args = p.parse_args()
    try:
        md = build_markdown(args.prev_tag.strip(), args.head, args.title or None)
    except subprocess.CalledProcessError as e:
        print(e, file=sys.stderr)
        return 1
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
