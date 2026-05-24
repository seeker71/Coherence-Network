#!/usr/bin/env python3
"""Evaluate the pytest predicates on every active spec and promote to done
when the test suite passes. Companion to upgrade_specs_to_form_predicates.py
which adds the predicates and promotes draft → active.

Two states this pass distinguishes that the previous pass cannot:
  - active : implemented (source files present) but test status unknown
             or failing
  - done   : implemented AND its pytest target passes

Pure file-shape predicates are not the test of implementation — passing
behavior is. This pass invokes pytest_passes via subprocess for each
spec's test target, then updates status. The substrate's content-
addressing can't shortcut subprocess invocations (impure), so each call
runs fresh.

Conservative: only PROMOTES active → done. Does not demote done → active
(test failures may be transient infra issues; manual review wanted).

Usage:
    python3 scripts/evaluate_spec_tests.py [--dry-run] [--limit N]
        [--timeout SECONDS] [--only-newly-promoted]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"


def read_status(path: Path) -> str | None:
    m = re.search(r"^status:\s*(\S+)", path.read_text(), re.MULTILINE)
    return m.group(1) if m else None


def extract_pytest_targets(path: Path) -> list[str]:
    """Find pytest_passes("...") predicates in the spec's done_when block."""
    text = path.read_text()
    m = re.search(r"^done_when:\n((?:  - .*\n)*)", text, re.MULTILINE)
    if not m:
        return []
    out: list[str] = []
    for line in m.group(1).splitlines():
        mm = re.search(r"pytest_passes\(\s*['\"]([^'\"]+)['\"]\s*\)", line)
        if mm:
            out.append(mm.group(1))
    return out


def run_pytest(target: str, timeout: int) -> tuple[bool, str]:
    """Run pytest against target. Returns (passed, last_line_of_output)."""
    cmd = ["python3", "-m", "pytest", "-q", "--no-header", target]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except FileNotFoundError:
        return False, "pytest not found"
    if r.stdout:
        last = r.stdout.strip().split("\n")[-1]
    elif r.stderr:
        last = r.stderr.strip().split("\n")[-1]
    else:
        last = ""
    return r.returncode == 0, last[:90]


def update_status(path: Path, new_status: str) -> None:
    text = path.read_text()
    new_text = re.sub(
        r"^(status:\s*)\S+",
        rf"\g<1>{new_status}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_text != text:
        path.write_text(new_text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=180,
                    help="Per-pytest-invocation timeout in seconds (default 180).")
    args = ap.parse_args()

    spec_paths = sorted([
        p for p in SPECS_DIR.glob("*.md")
        if p.name not in ("INDEX.md", "TEMPLATE.md")
    ])

    active_specs = [p for p in spec_paths if read_status(p) == "active"]
    if args.limit:
        active_specs = active_specs[: args.limit]

    print(f"Evaluating pytest predicates on {len(active_specs)} active specs...")
    print()

    promoted: list[Path] = []
    test_failing: list[tuple[Path, str]] = []
    no_pytest: list[Path] = []

    t0 = time.time()
    for i, path in enumerate(active_specs):
        targets = extract_pytest_targets(path)
        if not targets:
            no_pytest.append(path)
            continue

        all_passed = True
        last_line = ""
        for target in targets:
            ok, msg = run_pytest(target, args.timeout)
            if not ok:
                all_passed = False
                last_line = msg
                break

        elapsed = time.time() - t0
        if all_passed:
            print(f"  [{i+1:3d}/{len(active_specs)}] ✓ {path.name}  "
                  f"({len(targets)} target(s), {elapsed:.0f}s elapsed)")
            promoted.append(path)
        else:
            print(f"  [{i+1:3d}/{len(active_specs)}] ✗ {path.name}  "
                  f"({last_line})")
            test_failing.append((path, last_line))

    print()
    print(f"Results:")
    print(f"  promoted → done : {len(promoted)}")
    print(f"  test failing    : {len(test_failing)}")
    print(f"  no pytest target: {len(no_pytest)}")
    print(f"  total active    : {len(active_specs)}")
    print(f"  wall time       : {time.time() - t0:.1f}s")

    if args.dry_run or not promoted:
        return 0

    print()
    print(f"Updating {len(promoted)} spec(s) status: active → done")
    for path in promoted:
        update_status(path, "done")

    return 0


if __name__ == "__main__":
    sys.exit(main())
