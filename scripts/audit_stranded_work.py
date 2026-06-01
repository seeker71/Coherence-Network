#!/usr/bin/env python3
"""Find work that may have been stranded on abandoned branches.

The team squash-merges. Squash destroys the merge linkage: after a squash, the
branch's original commits are no longer reachable from main, so `git log
main..branch` reports them as "ahead" even though their CONTENT merged. That
makes commit-count a liar — it cannot tell squash-residue from genuinely-lost
work. So this audit reads CONTENT, not commit graph.

The strongest honest signal of stranded work: a file that exists on the branch
but NOT on main. Something was created there and never reached the body. This
tool lists, for each remote branch ahead of main:

  - commits ahead + last-commit date (staleness)
  - files present on the branch but absent from main  ← the stranded signal
  - a verdict: LIKELY-MERGED (no branch-only files) or REVIEW (has them)

It does not auto-delete or auto-merge. It surfaces candidates a human reviews —
"is this file's work actually on main under a different path, or was it lost?"

Usage:
    python3 scripts/audit_stranded_work.py                 # claude/* + codex/*
    python3 scripts/audit_stranded_work.py --all           # every remote branch
    python3 scripts/audit_stranded_work.py --prefix codex  # one namespace
    python3 scripts/audit_stranded_work.py --review-only    # hide LIKELY-MERGED
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def remote_branches(prefixes: list[str] | None) -> list[str]:
    out = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    branches = [b.strip() for b in out.splitlines() if b.strip()
                and not b.endswith("/HEAD")]
    if prefixes:
        branches = [b for b in branches
                    if any(b.startswith(f"origin/{p}") for p in prefixes)]
    return [b for b in branches if b != "origin/main"]


def branch_only_files(branch: str) -> list[str]:
    """Files that exist on `branch` but not on origin/main — the stranded signal.
    Renames on main are not chased; a flagged file means 'review whether this
    content reached main under any path', which is exactly the human judgment."""
    main_files = set(git("ls-tree", "-r", "--name-only", "origin/main").splitlines())
    branch_files = set(git("ls-tree", "-r", "--name-only", branch).splitlines())
    return sorted(branch_files - main_files)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every remote branch")
    ap.add_argument("--prefix", action="append", default=None,
                    help="branch namespace(s) to scan (default: claude, codex)")
    ap.add_argument("--review-only", action="store_true",
                    help="show only branches with branch-only files")
    args = ap.parse_args()

    git("fetch", "origin", "--quiet")
    prefixes = None if args.all else (args.prefix or ["claude", "codex"])
    branches = remote_branches(prefixes)

    review, merged = [], 0
    for b in branches:
        ahead = git("rev-list", "--count", f"origin/main..{b}").strip() or "0"
        if ahead == "0":
            continue
        only = branch_only_files(b)
        if only:
            date = git("log", "-1", "--format=%ci", b).strip()[:10]
            review.append((b, ahead, date, only))
        else:
            merged += 1

    print(f"Stranded-work audit — {len(branches)} branch(es) scanned, "
          f"{len(review)} need REVIEW, {merged} likely-merged "
          f"(no branch-only files).\n")
    for b, ahead, date, only in sorted(review, key=lambda r: (r[2], -len(r[3]))):
        print(f"⚠  REVIEW  {b}  ({ahead} commits ahead, last {date})")
        print(f"     {len(only)} file(s) on this branch but NOT on main:")
        for f in only[:12]:
            print(f"       + {f}")
        if len(only) > 12:
            print(f"       … and {len(only) - 12} more")
        print()
    if not args.review_only and merged:
        print(f"○  {merged} branch(es) ahead but content-merged "
              f"(squash residue) — safe to prune.")

    # Aggregate: a file on MANY branches but never on main is a recurring orphan
    # — one body of work that never landed, not N separate problems. This turns
    # the per-branch noise into the actual signal: what did we create and lose?
    if review:
        from collections import Counter
        orphan = Counter()
        for _, _, _, only in review:
            orphan.update(only)
        recurring = [(f, n) for f, n in orphan.most_common() if n > 1]
        if recurring:
            print(f"\nRecurring orphans — file on >1 branch, never on main "
                  f"({len(recurring)} file(s)); likely one un-landed body of work:")
            for f, n in recurring[:25]:
                print(f"   {n:3d} branches  {f}")
            if len(recurring) > 25:
                print(f"   … and {len(recurring) - 25} more")
    return 1 if review else 0


if __name__ == "__main__":
    sys.exit(main())
