#!/usr/bin/env python3
"""Feed git (commit message -> diff) pairs into the form-cli training catalog.

Each merged commit is a labeled (intent -> code) training pair: the message is the
intent, the diff is the realization, the label is `merged` (passed review + CI; for
.fk/.form commits, four-way at merge time). The pair-shape, the three separable
lanes (raw / transmute / reasoning), and content-addressing live in
form-stdlib/training-catalog.fk; this is the host-IO bootstrap carrier that sources
git into the existing catalog_capture on the `git-commit-to-diff` lane. North star:
the kernel reads git itself via a host-io source-scan recipe (a named frontier wall
in form/fourth-arm-bands.txt) — this carrier composts when that lands.

Usage:
  git_training_corpus.py --range ORIG_HEAD..HEAD   # post-merge: just-landed commits
  git_training_corpus.py --backfill 200            # manual: last N .fk/.form commits
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-server"))
from coherence_mcp_server.form_cli_tools import catalog_capture  # noqa: E402

LANE = "git-commit-to-diff"
MAX_DIFF = 8000  # bound each record; the full diff always lives in git


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def _commits(range_spec: str | None, backfill: int | None) -> list[str]:
    if backfill:
        return _git("log", "--format=%H", "-n", str(backfill), "--", "*.fk", "*.form").split()
    if range_spec:
        return _git("log", "--format=%H", range_spec, "--", "*.fk", "*.form").split()
    return []


def feed(commits: list[str]) -> int:
    fed = 0
    for sha in commits:
        msg = _git("show", "-s", "--format=%s%n%n%b", sha).strip()
        diff = _git("show", sha, "--format=", "--unified=3")[:MAX_DIFF]
        if not msg or not diff.strip():
            continue
        # request = intent, raw = transmuted = diff (merged code is the trusted
        # realization — no fear to transmute), lane + outcome carry the label.
        catalog_capture(msg, diff, diff, LANE, "merged")
        fed += 1
    return fed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--range", dest="range_spec", default=None,
                    help="git range of just-merged commits, e.g. ORIG_HEAD..HEAD")
    ap.add_argument("--backfill", type=int, default=None,
                    help="manual backfill: last N .fk/.form commits")
    args = ap.parse_args()
    fed = feed(_commits(args.range_spec, args.backfill))
    print(f"[catalog] {LANE}: fed {fed} (intent->code) pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
