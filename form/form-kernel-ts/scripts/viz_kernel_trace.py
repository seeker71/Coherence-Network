#!/usr/bin/env python3
"""viz_kernel_trace.py — Read the form-kernel-rust trace JSON for a
compiled Python program and visualize the Form-shape hot-spots that
drive execution. Identifies optimization targets for the kernel.

The framebuffer-visualizer arc named in lc-form-kernel-runtime-visualizer
ultimately renders heap-cell writes colored by Form category. This script
is the text-altitude sibling: a terminal-based bar chart showing which
(arm_ty, arm_inst) pairs fire most often during native execution. Same
discipline — observe before optimize, attribute to structural shape, not
to source lines — at a deliverable-today altitude.

Usage:
    python3 scripts/viz_kernel_trace.py <file.fk>
    python3 scripts/viz_kernel_trace.py <file.py>    # compiles first

Run from form/form-kernel-ts/.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# Color palette aligned with mfb::render::nodeid_category_palette so the
# terminal viz uses the same hue families the future framebuffer render
# will use. Substrate-write greens, computation reds, control-flow blues,
# container magentas, effect yellows, transmutation purples, type-machinery
# teals. ANSI 256-color codes approximating the RGB palette.
ARM_COLOR = {
    "WITNESS":   "\033[38;5;48m",    # green — substrate self-attestation
    "ACCESS":    "\033[38;5;120m",   # green-yellow — read property
    "MATH":      "\033[38;5;203m",   # red — arithmetic
    "COMPARE":   "\033[38;5;208m",   # orange — comparison
    "LOGIC":     "\033[38;5;220m",   # yellow — boolean
    "COND":      "\033[38;5;167m",   # red-orange — conditional
    "BLOCK":     "\033[38;5;75m",    # blue — control flow scope
    "FNDEF":     "\033[38;5;105m",   # blue-purple — function def
    "FNCALL":    "\033[38;5;39m",    # cyan-blue — function invoke
    "IDENT":     "\033[38;5;110m",   # blue-gray — name resolution
    "LIST":      "\033[38;5;213m",   # magenta — container
    "CALL":      "\033[38;5;226m",   # yellow — external effect
    "METHOD":    "\033[38;5;221m",   # yellow-orange — cell-transform
    "TRANSMUTE": "\033[38;5;141m",   # purple — view-through-Blueprint
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def compile_py_to_fk(py_path: Path) -> Path:
    """Compile a .py file to .fk via the TS kernel's python-compile."""
    fk_path = py_path.with_suffix(".fk")
    subprocess.run(
        ["npx", "tsx", "src/main.ts", "python-compile", str(py_path), str(fk_path)],
        check=True,
        capture_output=True,
    )
    return fk_path


def run_kernel_trace(fk_path: Path) -> dict:
    """Run form-kernel-rust trace on a .fk file. Return the trace JSON."""
    # Locate the release binary.
    script_dir = Path(__file__).resolve().parent
    kernel_bin = (
        script_dir.parent.parent / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
    )
    if not kernel_bin.exists():
        sys.exit(
            f"error: form-kernel-rust binary not found at {kernel_bin}\n"
            "build it first: cd form/form-kernel-rust && cargo build --release"
        )
    result = subprocess.run(
        [str(kernel_bin), "trace", str(fk_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def render_bar_chart(report: dict) -> None:
    """Print a terminal bar chart of (arm_variant_name, count) variants,
    colored by arm family, sorted by descending count."""
    trace = report["trace"]
    variants = trace.get("variants", [])
    total = trace.get("total_walks", 0)
    elapsed = report.get("elapsed_human", "?")

    if not variants:
        print("no dispatch variants recorded (trace was empty)")
        return

    # Width budget for the bar (terminal columns minus label/count).
    cols = max(40, int(os.environ.get("COLUMNS", "100")))
    max_label = max(len(v.get("arm_variant_name") or v["arm_name"]) for v in variants)
    max_count = max(v["count"] for v in variants)
    count_width = len(str(max_count))
    bar_width = cols - max_label - count_width - 12

    print(f"{BOLD}=== Kernel hot-spots ==={RESET}")
    print(f"total walks: {total:,}   elapsed: {elapsed}")
    print()
    for v in variants:
        label = v.get("arm_variant_name") or v["arm_name"]
        count = v["count"]
        share = count / total if total else 0
        arm = v["arm_name"]
        color = ARM_COLOR.get(arm, "")
        bar_len = int(share * bar_width) if total else 0
        bar = "█" * bar_len
        pct = f"{share * 100:5.1f}%"
        print(
            f"  {color}{label:<{max_label}}{RESET}  "
            f"{count:>{count_width},}  "
            f"{DIM}{pct}{RESET}  "
            f"{color}{bar}{RESET}"
        )
    print()


def report_optimization_targets(report: dict) -> None:
    """Name the hot-spot variants and suggest where kernel optimization
    work would have the biggest impact. The structural reading: any
    variant > 10% of total dispatches is a candidate for inline / fast-path
    optimization in the walker."""
    trace = report["trace"]
    variants = trace.get("variants", [])
    total = trace.get("total_walks", 0)
    if not total:
        return

    threshold = 0.10
    hot = [v for v in variants if v["count"] / total >= threshold]
    print(f"{BOLD}=== Optimization targets ==={RESET}")
    if not hot:
        print(f"  {DIM}no variant exceeds {threshold*100:.0f}% of total walks{RESET}")
    else:
        print(f"  {DIM}variants firing > {threshold*100:.0f}% of total walks:{RESET}")
        for v in hot:
            label = v.get("arm_variant_name") or v["arm_name"]
            share = v["count"] / total * 100
            arm = v["arm_name"]
            color = ARM_COLOR.get(arm, "")
            print(
                f"    {color}{label}{RESET}  {share:.1f}%  "
                f"({v['count']:,} dispatches)"
            )
    print()
    print(f"  {DIM}Where to look in the walker:{RESET}")
    print("    IDENT-heavy  → faster name resolution (cache last lookup per frame)")
    print("    MATH-heavy   → inline arithmetic, avoid Recipe lookup for trivial leaves")
    print("    COMPARE/COND → fuse compare+branch into one dispatch")
    print("    FNCALL-heavy → tail-call optimization for self-recursion")
    print("    LIST-heavy   → arena-allocated list-recipe cache")


def main():
    if len(sys.argv) < 2:
        print("usage: viz_kernel_trace.py <file.fk|file.py>", file=sys.stderr)
        sys.exit(2)

    arg_path = Path(sys.argv[1])
    if arg_path.suffix == ".py":
        fk_path = compile_py_to_fk(arg_path)
        print(f"compiled {arg_path} → {fk_path}\n")
    else:
        fk_path = arg_path

    report = run_kernel_trace(fk_path)

    print(f"{BOLD}=== Workload ==={RESET}")
    print(f"file:     {fk_path}")
    print(f"result:   {report.get('result', '?')}")
    print()

    render_bar_chart(report)
    report_optimization_targets(report)


if __name__ == "__main__":
    main()
