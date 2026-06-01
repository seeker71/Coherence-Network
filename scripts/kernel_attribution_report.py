#!/usr/bin/env python3
"""Kernel attribution-activity report — which Blueprints/Recipes/natives fire.

The first real step toward the larger direction Urs named: serve most/all API
routes through the Form kernel for full attribution + traceability, then SEE
which Blueprints / Recipes / Cells are most active versus which sit inert and
need a look at why they're registered but never involved.

What it does, honestly scoped to what's measurable today
--------------------------------------------------------
The kernel's ``trace`` subcommand
(`form/form-kernel-rust/src/main.rs` :: ``cli_trace`` / ``Trace``) emits, per
run, the arm-dispatch counts (FNCALL, BLOCK, MATH, METHOD, …), the Form
functions called, and the host-natives fired. The kernel's ``native_blueprint``
native resolves each native name to its Form-category Blueprint NodeID
(e.g. ``abs`` → ``@1.2.27.1``). This report:

  1. Runs each **kernel-served recipe** (the transmuted-endpoint ``.fk`` shapes
     in `form/form-kernel-ts/seedbank/python-adapter/examples/`) through
     ``trace`` — recipes as DATA, one walk each, no special-casing.
  2. AGGREGATES the arm / function / native counts across all recipes into a
     single ranked view: which Blueprints (arm categories), which Recipes
     (Form functions), and which natives fired MOST.
  3. Resolves the fired natives to their Blueprint NodeIDs via
     ``native_blueprint`` — the transparency thread: every native call is
     attributable to a Form category.
  4. Names the **inert** surfaces: registered natives that NEVER fired across
     the kernel-served recipes. These are the "why is this here and not being
     involved?" candidates Urs asked to see.

Honest coverage statement (printed, not buried)
-----------------------------------------------
The activity view is over the **kernel-served routes today** — the
transmuted endpoints' computational cores. The trace gives **arm + native-
Blueprint attribution**, which is real and complete for what runs. Full
per-route Recipe/Cell-level activity across ALL routes requires more routes
transmuted to the kernel; the view widens as coverage grows. This report names
that path rather than faking coverage.

Run
---
    python3 scripts/kernel_attribution_report.py            # human-readable
    python3 scripts/kernel_attribution_report.py --json      # machine-readable
    python3 scripts/kernel_attribution_report.py --top 5     # top-N per section

Exit 0 always when the kernel binary is present (it is a sensing, not a gate).
Exit 2 when the kernel binary is absent — names what it couldn't reach.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The kernel-served recipes today: the transmuted-endpoint computational
# cores. Each is the committed `.fk` whose body the live endpoint runs. Routes
# as DATA — adding a transmuted route here widens the activity view by one row,
# no code change. The expected_result is the documented value-parity anchor
# (API_KERNEL_READINESS.md) so a recipe that traces to the WRONG value is
# visible in the same pass as its activity.
KERNEL_SERVED_RECIPES: list[dict[str, object]] = [
    {
        "route": "/api/utils/coherence_weight",
        "recipe": "endpoint_coherence_weight_demo.fk",
        "expected_result": "16185",
    },
    {
        "route": "/api/utils/nodeid_distance",
        "recipe": "endpoint_nodeid_distance_demo.fk",
        "expected_result": "7",
    },
    {
        "route": "/api/utils/nodeid_compatibility",
        "recipe": "endpoint_nodeid_compatibility_demo.fk",
        "expected_result": "2",
    },
    {
        "route": "/api/utils/weighted_average",
        "recipe": "endpoint_weighted_average_demo.fk",
        "expected_result": "0.8125",
    },
    {
        "route": "/api/utils/simpson_diversity",
        "recipe": "endpoint_simpson_diversity_demo.fk",
        "expected_result": "0.625",
    },
    {
        "route": "/api/utils/idea_score",
        "recipe": "endpoint_idea_score_demo.fk",
        "expected_result": "2.0",
    },
    {
        "route": "/api/utils/marginal_cc_return",
        "recipe": "endpoint_marginal_cc_return_demo.fk",
        "expected_result": "0.8",
    },
    {
        # First kernel-served route to use a transcendental native (ln).
        # breath_balance(1,1,1) — perfectly balanced thirds; H = ln(3) =
        # H_max, so the normalized entropy is 1.0 up to the last ULP of the
        # ln(1/3)*3 vs ln(3) round-off (CPython and Rust agree to the bit).
        "route": "/api/utils/breath_balance",
        "recipe": "endpoint_breath_balance_demo.fk",
        "expected_result": "0.9999999999999998",
    },
    {
        # First LIST-returning kernel-served route. The result is a list of
        # softmax weights; the trace renders it as the list display string, so
        # the parity anchor is that string verbatim. scores [1,2,3] @ temp 1.0
        # shifted by max 3.0 → weights [e^-2, e^-1, 1]/total, summing to 1.0.
        # Element-wise CPython==Rust parity is proven by parity_suite.sh.
        "route": "/api/utils/softmax_weights",
        "recipe": "endpoint_softmax_weights_demo.fk",
        "expected_result": "[0.09003057317038046, 0.24472847105479764, 0.6652409557748218]",
    },
    {
        # First kernel-served routes to use the round_ndigits native
        # (CPython-exact round(x, 4), PR #2320). Cost-vector decomposition:
        # estimated_cost 33.333 → compute 60% / infrastructure 15% /
        # human_attention 25% / opportunity 0 / external 0 / total, each
        # round(_, 4). The decimal input lands on the half-to-even tie-breaks
        # the old round-half-up shim got wrong (infrastructure 4.9999 from
        # 4.99995, human_attention 8.3332 from 8.33325) — so this anchor is
        # the end-to-end proof the round() unlock is correct in production.
        "route": "/api/utils/cost_vector",
        "recipe": "endpoint_cost_vector_demo.fk",
        "expected_result": "[19.9998, 4.9999, 8.3332, 0.0, 0.0, 33.333]",
    },
    {
        # Value-vector decomposition, sibling of cost_vector — same
        # round_ndigits unlock. potential_value 9.205 → adoption 50% /
        # lineage 30% / friction_avoided 20% / revenue 0 / total, each
        # round(_, 4). Per-component CPython==Rust parity proven by
        # parity_suite.sh.
        "route": "/api/utils/value_vector",
        "recipe": "endpoint_value_vector_demo.fk",
        "expected_result": "[4.6025, 2.7615, 1.841, 0.0, 9.205]",
    },
    {
        # Grounded-ROI scalar trio of idea_scoring._with_score — folds the
        # max-as-comparison, the round_ndigits native (PR #2320), and a
        # guarded division (the `if remaining_cost_cc > 0 else 0.0` ternary)
        # into one recipe. Frozen input estimated_cost 60 / actual_cost 12 /
        # potential_value 33.333 / actual_value 8 → remaining_cost_cc 48.0,
        # value_gap_cc 25.333, roi_cc round(25.333/48.0, 4) = 0.5278.
        "route": "/api/utils/grounded_roi",
        "recipe": "endpoint_grounded_roi_demo.fk",
        "expected_result": "[48.0, 25.333, 0.5278]",
    },
]

_EXAMPLES_DIR = (
    ROOT / "form" / "form-kernel-ts" / "seedbank" / "python-adapter" / "examples"
)
_KERNEL_BIN = (
    ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
)


def kernel_bin() -> Path:
    """The form-kernel-rust binary path (honors FORM_KERNEL_RUST_BIN)."""
    override = os.environ.get("FORM_KERNEL_RUST_BIN")
    return Path(override) if override else _KERNEL_BIN


def kernel_available() -> bool:
    p = kernel_bin()
    return p.is_file() and os.access(p, os.X_OK)


def _run_kernel(args: list[str], timeout: float = 20.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(kernel_bin()), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def trace_recipe(recipe_path: Path) -> dict | None:
    """Run a recipe through the kernel's trace mode; return parsed JSON or None."""
    proc = _run_kernel(["trace", str(recipe_path)])
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def native_blueprint(name: str) -> str | None:
    """Resolve a native name to its Form-category Blueprint NodeID, or None."""
    proc = _run_kernel(["--expr", f'(native_blueprint "{name}")'])
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        return None
    # The native returns a NodeID like "@1.2.27.1"; the binary may print it on
    # its own line. Take the last non-empty line that looks like a NodeID.
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("@"):
            return line
    return out.splitlines()[-1].strip() if out else None


# ---------------------------------------------------------------------------
# The ONE aggregation mechanism — recipes as DATA, summed into a ranked view.
# ---------------------------------------------------------------------------


def aggregate() -> dict:
    """Trace every kernel-served recipe and aggregate the attribution signal.

    Returns a dict with:
      - per_recipe:  [{route, recipe, result, expected, parity, elapsed_us,
                       missing}]  (missing == recipe `.fk` not on disk)
      - arms:        {arm_variant_name -> total count}     (Blueprint activity)
      - functions:   {form-fn name -> total count}          (Recipe activity)
      - natives:     {native name -> {count, blueprint}}    (native activity)
      - inert_natives:  [names registered in the kernel that never fired]
      - reached:     count of recipes actually traced
      - eligible:    count of recipes named (== reached + missing + failed)
    """
    arm_counts: dict[str, int] = defaultdict(int)
    fn_counts: dict[str, int] = defaultdict(int)
    native_counts: dict[str, int] = defaultdict(int)
    per_recipe: list[dict] = []
    reached = 0

    for entry in KERNEL_SERVED_RECIPES:
        recipe_name = str(entry["recipe"])
        recipe_path = _EXAMPLES_DIR / recipe_name
        rec: dict = {
            "route": entry["route"],
            "recipe": recipe_name,
            "expected": entry["expected_result"],
        }
        if not recipe_path.is_file():
            # The `.fk` is a deploy-time-compiled artifact; in a fresh worktree
            # it may be absent. Name it, don't fake a trace.
            rec.update({"missing": True, "result": None, "parity": None})
            per_recipe.append(rec)
            continue

        trace = trace_recipe(recipe_path)
        if trace is None:
            rec.update({"failed": True, "result": None, "parity": None})
            per_recipe.append(rec)
            continue

        reached += 1
        result = str(trace.get("result", ""))
        rec["result"] = result
        rec["elapsed_us"] = trace.get("elapsed_us")
        rec["parity"] = result == str(entry["expected_result"])

        tr = trace.get("trace", {})
        for v in tr.get("variants", []):
            arm_counts[v.get("arm_variant_name", "?")] += int(v.get("count", 0))
        for f in tr.get("functions", []):
            fn_counts[f.get("name", "?")] += int(f.get("count", 0))
        for n in tr.get("natives", []):
            native_counts[n.get("name", "?")] += int(n.get("count", 0))
        per_recipe.append(rec)

    # Attribute each fired native to its Blueprint NodeID (transparency thread).
    natives_with_bp: dict[str, dict] = {}
    for name, count in native_counts.items():
        natives_with_bp[name] = {
            "count": count,
            "blueprint": native_blueprint(name),
        }

    return {
        "per_recipe": per_recipe,
        "arms": dict(arm_counts),
        "functions": dict(fn_counts),
        "natives": natives_with_bp,
        "inert_natives": _inert_natives(set(native_counts)),
        "reached": reached,
        "eligible": len(KERNEL_SERVED_RECIPES),
    }


# Registered natives the kernel ships. Sourced from the kernel's own
# `register_native(...)` calls (main.rs). We don't need the full set to be
# exhaustive — the honest signal is "these are registered and never fired
# across the kernel-served recipes," i.e. dormant relative to TODAY's
# coverage. A native firing on no current route is a candidate for "why is it
# here / which route would exercise it." This list names the natives an
# operator would expect a richer route surface to involve.
_REGISTERED_NATIVES_SAMPLE = {
    # arithmetic / list ops the endpoint recipes DO use
    "_plus", "abs", "_get", "_iter", "head", "tail", "len", "nth",
    # natives registered but NOT exercised by the pure-compute recipes —
    # they wait for routes that do I/O, structure, or witness work.
    "native_blueprint", "trace", "fetch", "print", "str", "concat",
    "map", "filter", "fold", "range", "str_to_int", "str_to_float",
    "split", "to_json", "from_json",
}


def _inert_natives(fired: set[str]) -> list[str]:
    """Registered natives that never fired across the kernel-served recipes.

    Honest framing: 'inert relative to today's four pure-compute routes', not
    'dead code'. Each is a native a future transmuted route (I/O, structure,
    witness) would exercise — naming them is the 'why here, not involved?'
    view Urs asked for. The list grows accurate as more natives are catalogued
    and shrinks as more routes are transmuted.
    """
    return sorted(_REGISTERED_NATIVES_SAMPLE - fired)


def _ranked(counts: dict, top: int | None) -> list[tuple]:
    items = sorted(counts.items(), key=lambda kv: (-_count_of(kv[1]), kv[0]))
    return items[:top] if top else items


def _count_of(value) -> int:
    return value["count"] if isinstance(value, dict) else int(value)


def render(report: dict, top: int | None) -> str:
    out: list[str] = []
    out.append("# Kernel attribution-activity report")
    out.append("")
    out.append(
        f"Kernel-served routes traced: {report['reached']}/{report['eligible']} "
        "(the transmuted-endpoint computational cores)."
    )
    out.append("")

    # Per-recipe: value parity + elapsed, so a wrong value shows next to activity.
    out.append("## Recipes traced (value-parity anchored)")
    out.append("")
    for r in report["per_recipe"]:
        if r.get("missing"):
            out.append(f"  · {r['route']}  —  recipe `.fk` absent (not compiled here)")
            continue
        if r.get("failed"):
            out.append(f"  · {r['route']}  —  trace FAILED")
            continue
        parity = "✓" if r.get("parity") else "✗ PARITY BREAK"
        us = r.get("elapsed_us")
        us_str = f"{us}µs" if us is not None else "?"
        out.append(
            f"  · {r['route']}  →  {r['result']} (expected {r['expected']}) "
            f"{parity}  ·  {us_str}"
        )
    out.append("")

    # Blueprint activity (arm categories — the Form Blueprints exercised).
    out.append("## Hot Blueprints (arm-dispatch categories)")
    out.append("")
    for name, count in _ranked(report["arms"], top):
        out.append(f"  {count:>6}  {name}")
    out.append("")

    # Recipe activity (Form functions invoked).
    out.append("## Hot Recipes (Form functions called)")
    out.append("")
    if report["functions"]:
        for name, count in _ranked(report["functions"], top):
            out.append(f"  {count:>6}  {name}")
    else:
        out.append("  (no named Form functions — recipes inline their bodies)")
    out.append("")

    # Native activity, each attributed to its Blueprint NodeID.
    out.append("## Hot natives (each attributed to its Blueprint NodeID)")
    out.append("")
    for name, info in _ranked(report["natives"], top):
        bp = info.get("blueprint") or "?"
        out.append(f"  {info['count']:>6}  {name:<16} {bp}")
    out.append("")

    # Inert — the 'why here, not involved?' candidates.
    out.append("## Inert natives (registered, never fired across these routes)")
    out.append("")
    if report["inert_natives"]:
        out.append(
            "  These natives are registered in the kernel but no kernel-served"
        )
        out.append(
            "  route exercises them today. Each is a candidate for 'why is this"
        )
        out.append(
            "  here, and which route would involve it?' — they wait for routes"
        )
        out.append("  that do I/O, structure, or witness work, not pure arithmetic:")
        out.append("")
        out.append("    " + ", ".join(report["inert_natives"]))
    else:
        out.append("  (every catalogued native fired — full involvement)")
    out.append("")

    # The honest coverage statement — printed, not buried.
    out.append("## Coverage — what this view sees, and the path to full coverage")
    out.append("")
    out.append(
        "  Today the view covers the kernel-served routes: the transmuted-"
    )
    out.append(
        "  endpoint computational cores. The attribution is real and complete"
    )
    out.append(
        "  for what runs — arm-dispatch + native-Blueprint resolution. Full"
    )
    out.append(
        "  per-route Recipe/Cell activity across ALL routes requires more routes"
    )
    out.append(
        "  transmuted to the kernel. The path: transmute routes incrementally"
    )
    out.append(
        "  (each earns value parity), the wellness probe guards the surface, and"
    )
    out.append("  this activity view widens by one row per transmuted route.")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--top", type=int, default=None, help="top-N per section")
    args = parser.parse_args(argv)

    if not kernel_available():
        msg = (
            f"kernel binary not found at {kernel_bin()} — "
            "build it (cargo build --release in form/form-kernel-rust) to trace."
        )
        if args.json:
            print(json.dumps({"error": msg, "reached": 0}, indent=2))
        else:
            print(f"(could not reach the kernel binary)\n  {msg}")
        return 2

    report = aggregate()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
