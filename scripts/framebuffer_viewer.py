#!/usr/bin/env python3
"""framebuffer_viewer.py — render the kernel's framebuffer as a text panel.

The Form kernels (Go, Rust, TS) all record source-attributed cell
creations in a side-map keyed by NodeID. `(framebuffer-events)` returns
that map's contents as a list. The native primitive exists; nobody was
watching the recording. This script is the observer — it runs a Form
file through the Go kernel, dumps the events list at the end, and
renders the activity as a text-mode visualization (counts, top
Blueprints, density chart, category buckets).

Usage:
    framebuffer_viewer.py <form-file.fk> [--core CORE_PATH]

The --core flag points at the pre-compiled core.fk (validate.sh's
prepare_sources step produces it under /tmp/form-source.*/). When the
input file declares `; preludes: a.fk b.fk ...` they are loaded between
core and the test, matching validate.sh's convention.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GO_BIN = REPO / "form" / "form-kernel-go" / "bin-go"

# NodeID textual form from the Go kernel: @pkg.level.type.instance
NID_RE = re.compile(r"@(\d+)\.(\d+)\.(\d+)\.(\d+)")


def read_preludes(form_path: Path) -> list[str]:
    """Mirror validate.sh: a `; preludes:` header lists extra files
    loaded between core.fk and the test file."""
    for line in form_path.read_text().splitlines():
        m = re.match(r"^;\s*preludes:\s*(.*)$", line)
        if m:
            return [s for s in m.group(1).split() if s]
        if line.strip() and not line.lstrip().startswith(";"):
            break
    return []


def run_kernel(form_file: Path, core: Path | None) -> str:
    """Build a driver that ends with `(framebuffer-events)` so the
    kernel's final printed value is the events list. Return stdout."""
    preludes = read_preludes(form_file)
    files: list[str] = []
    if core is not None:
        files.append(str(core))
    for p in preludes:
        full = REPO / "form" / p
        if full.exists():
            files.append(str(full))
        else:
            print(f"warn: prelude not found, skipping: {p}", file=sys.stderr)
    files.append(str(form_file))

    # The driver: a one-line file whose value is the events list. Becomes
    # the final expression of the implicit multi-file do-block.
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as fp:
        fp.write("(framebuffer-events)\n")
        driver = Path(fp.name)

    try:
        files.append(str(driver))
        result = subprocess.run(
            [str(GO_BIN), *files],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"kernel exited {result.returncode}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
        return result.stdout
    finally:
        driver.unlink(missing_ok=True)


def parse_events(out: str) -> list[tuple[int, int, int, int]]:
    """Pull every NodeID from the kernel's final printed value.
    Returns a list of (pkg, level, type, instance) tuples."""
    return [tuple(map(int, m.groups())) for m in NID_RE.finditer(out)]


def bar(count: int, peak: int, width: int = 32) -> str:
    if peak <= 0:
        return ""
    n = max(1, round(width * count / peak)) if count > 0 else 0
    return "█" * n


def render(form_file: Path, events: list[tuple[int, int, int, int]]) -> None:
    total = len(events)
    print()
    print(f"  framebuffer  ·  {form_file.name}")
    print(f"  {'─' * 56}")
    print(f"  events recorded            {total:>6}")
    print(f"  distinct Blueprints        {len({(p, l, t) for p, l, t, _ in events}):>6}")
    print(f"  distinct NodeIDs           {len(set(events)):>6}")
    print()

    if total == 0:
        print("  the framebuffer is empty — no intern_node_at calls reached")
        print("  the recording side-map. add some, or check the input file.")
        print()
        return

    # Top Blueprints — (pkg, level, type) tells you the *shape* of cells
    # being authored, irrespective of instance churn.
    bp = Counter((p, l, t) for p, l, t, _ in events)
    peak = bp.most_common(1)[0][1]
    print("  top Blueprints  (pkg.level.type)            count   density")
    print(f"  {'─' * 56}")
    for (p, l, t), c in bp.most_common(10):
        label = f"@{p}.{l}.{t}.*"
        print(f"  {label:<24}  {c:>10}   {bar(c, peak)}")
    print()

    # Bucket by (pkg, level) — coarser; reveals which substrate layer
    # the activity lives in (BASIC, MEMORY, COMPOSITE, etc.).
    layer = Counter((p, l) for p, l, _, _ in events)
    print("  layer breakdown  (pkg.level)             cells")
    print(f"  {'─' * 56}")
    for (p, l), c in layer.most_common():
        print(f"  @{p}.{l}.*.*                            {c:>10}")
    print()

    # Instance spread — how much instance churn under each Blueprint?
    # High churn = many distinct cells of the same shape; low churn =
    # the same handful of cells getting re-attributed.
    spread = Counter()
    for p, l, t, _ in events:
        spread[(p, l, t)] += 0  # init
    inst_by_bp: dict[tuple[int, int, int], set[int]] = {}
    for p, l, t, i in events:
        inst_by_bp.setdefault((p, l, t), set()).add(i)
    print("  instance spread  (distinct instances per Blueprint, top 5)")
    print(f"  {'─' * 56}")
    top5 = sorted(inst_by_bp.items(), key=lambda kv: -len(kv[1]))[:5]
    for (p, l, t), inst_set in top5:
        print(f"  @{p}.{l}.{t}.*                          {len(inst_set):>10}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("form_file", type=Path, help="Form file to run (ends with framebuffer activity)")
    ap.add_argument("--core", type=Path, default=None, help="Pre-compiled core.fk (e.g. /tmp/form-source.*/form-stdlib__core.fk)")
    args = ap.parse_args()

    if not args.form_file.exists():
        print(f"no such file: {args.form_file}", file=sys.stderr)
        return 1
    if not GO_BIN.exists():
        print(f"go kernel not built — run: cd form && ./validate.sh", file=sys.stderr)
        return 1

    out = run_kernel(args.form_file, args.core)
    events = parse_events(out)
    render(args.form_file, events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
