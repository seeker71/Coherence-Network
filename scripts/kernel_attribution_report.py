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
from datetime import datetime, timezone
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
        # Normalized Shannon entropy over three phase counts — the body of
        # breath_service._shannon_entropy_normalized. Folds two natives into
        # one recipe: math_log (ln, breath_balance's unlock) and round_ndigits
        # (CPython-exact round, cost_vector's unlock). Distinct from
        # breath_balance: subtractive accumulator (+0.0 single-phase, not -0.0)
        # and a round(_, 4) wrapper. shannon_entropy(1,1,1) — equal thirds, H =
        # ln(3) = H_max, round(1.0, 4) = 1.0.
        "route": "/api/utils/shannon_entropy",
        "recipe": "endpoint_shannon_entropy_demo.fk",
        "expected_result": "1.0",
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
    {
        # First STRUCTURE-ACCESS route — the marginal-CC core reading its six
        # inputs from one structured object (a kernel Record marshalled from a
        # Python dict) instead of six scalar bindings. The recipe pulls each
        # field via the `_get` native (python-bmf SUBSCRIPT lowering), now able
        # to read Record fields. Frozen idea {pv 8, av 3, conf 0.8, ec 4, ac 1,
        # rr 2} → value_gap 5.0, remaining_cost 3.0, round((5*0.64)/(3+1), 6) =
        # 0.8. The capability the API_KERNEL_READINESS doc names as the gate
        # behind ~60% of remaining candidates; homogeneous-dict access is the
        # clean subset proven here.
        "route": "/api/utils/idea_marginal_from_record",
        "recipe": "endpoint_idea_marginal_from_record_demo.fk",
        "expected_result": "0.8",
    },
    {
        # First LIST-OF-RECORD-REDUCTION route — gate #1 in API_KERNEL_READINESS.
        # Receives one idea's pre-fetched specs as a LIST of records (marshalled
        # from a Python list[dict|model]; the bridge normalizes model→dict→record
        # at the boundary, dissolving the object-OR-dict polymorphism) and FOLDS
        # four integer grounding signals across it via the head/tail fold the
        # adapter lowers `for s in specs` into: spec_count, total_event_count,
        # specs_with_value_count (a field predicate), max_event_count. The honest
        # integer subset of compute_idea_metrics' confidence/coverage reductions;
        # the float-field fold and the six-collection heterogeneous join stay
        # CPython (named in the ledger). Frozen specs [{ec 3, av 1.5}, {ec 0, av
        # 0.0}, {ec 7, av 2.25}] → [3, 10, 2, 7].
        "route": "/api/utils/idea_grounding_summary",
        "recipe": "endpoint_idea_grounding_summary_demo.fk",
        "expected_result": "[3, 10, 2, 7]",
    },
    {
        # FLOAT-FIELD list-of-record reduction — the capability the integer
        # grounding-summary route named as deferred. Receives one idea's specs
        # as a LIST of records and FOLDS two FLOAT grounding sums across it:
        # spec_actual_cost_sum, spec_actual_value_sum. This was blocked by TS's
        # i32-only add/_plus; the float-add sibling-parity fix opened it, so the
        # float-field fold is value-exact across CPython / Rust / TS. The
        # accumulator seeds at 0.0 so every add walks (float, float). Frozen
        # specs [{ac 3.5, av 1.5}, {ac 1.25, av 0.0}, {ac 0.5, av 2.25}] →
        # [5.25, 3.75].
        "route": "/api/utils/idea_grounded_cost_sum",
        "recipe": "endpoint_idea_grounded_cost_sum_demo.fk",
        "expected_result": "[5.25, 3.75]",
    },
    {
        # The GROUNDED-COST REDUCTION of compute_idea_metrics — the richest
        # deferred slice, falling now that the float-field fold, per-record
        # arithmetic, and structure-access are banked. Given one idea's
        # ALREADY-FILTERED records it folds spec_actual_cost_sum,
        # spec_estimated_cost_sum, commit_cost_sum (per-commit clamp
        # max(0.05, min(10.0, 0.10+files*0.15+lines*0.002)) — _estimate_commit_cost_sum
        # EXACTLY), lineage_estimated_cost, and composes computed_actual_cost =
        # spec_actual_cost_sum + runtime_cost + commit_cost_sum. The honest seam:
        # FILTERING the six collections by idea_id is cheap host-side
        # collection-narrowing (the host already does it); the reduction is the
        # kernel computation. compute_idea_metrics' "deep gate" was never a
        # missing kernel capability — it is host orchestration AROUND now-kernel-
        # served reductions. Frozen sample (specs [{ac 3.5, ec 4.25}, {ac 1.25,
        # ec 2.5}], commit {files 3, lines 100}, links [{ec 5.25}, {ec 1.5}],
        # runtime_cost 2.25) → [4.75, 6.75, 2.25, 0.75, 6.75, 7.75], all
        # NON-integer floats so no value crosses the print boundary.
        "route": "/api/utils/grounded_cost",
        "recipe": "endpoint_grounded_cost_demo.fk",
        "expected_result": "[4.75, 6.75, 2.25, 0.75, 6.75, 7.75]",
    },
    {
        # The VALUE / REALIZATION / CONFIDENCE REDUCTION of compute_idea_metrics
        # — the SECOND and FINAL numeric slice. With the grounded-cost reduction
        # already serving (endpoint_grounded_cost_demo.fk) this completes the
        # function's COMPUTATION kernel-native. From the host-derived scalars it
        # computes computed_actual_value = max(lineage_measured_value,
        # usage_revenue, spec_actual_value_sum), computed_estimated_cost =
        # max(spec_estimated_cost_sum, lineage_estimated_cost),
        # value_realization_pct = min(value/potential, 1.0) guarded by
        # potential>0, has_runtime_data/has_commits = min(1.0, count/N) guarded
        # by count>0, and computed_confidence = clamp(weighted sum, 0.05, 0.95)
        # with weights 0.30/0.25/0.25/0.10/0.10 (_WEIGHT_* from source). The
        # honest seam: the boolean-presence levels (has_specs_with_data /
        # has_lineage / has_friction — any(...)-over-records / len>0 ladders) and
        # the collection filtering stay host-side BY DESIGN. Frozen sample
        # (lineage 12.5, usage_revenue 0.007, spec_actual_value 4.25, spec_est
        # 6.75, lineage_est 5.5, potential 20.0, event_count 7, commit_count 3,
        # has_specs 1.0, has_lineage 1.0, has_friction 0.3) →
        # [12.5, 6.75, 0.625, 0.815], all NON-integer floats so no value crosses
        # the print boundary.
        "route": "/api/utils/grounded_value",
        "recipe": "endpoint_grounded_value_demo.fk",
        "expected_result": "[12.5, 6.75, 0.625, 0.815]",
    },
    {
        # The STRING-MEMBERSHIP SCORING of concept_auto_tagger._score_concept —
        # the FIRST kernel-served route to fold STRING MEMBERSHIP (`kw in text`
        # lowered to str_find(text, kw, 0) >= 0) rather than an int or float
        # field. It opens the text-scoring family. The honest seam: the host
        # tokenizes (the regex _extract_keywords + lowercasing + the " ".join
        # assembly — text preprocessing, a genuine deferred host-side capability)
        # and the kernel SCORES the already-tokenized keyword lists: forward =
        # fraction of idea keywords found in concept_text, reverse = fraction of
        # concept keywords found in idea_text, plus a 0.3 name bonus, combined
        # round(min(0.5*fwd + 0.3*rev + bonus, 1.0), 4) — _score_concept's body,
        # weights/bonus/ceiling verbatim from source. The str_find native is
        # three-way value-identical for ASCII (string-membership-band.fk → 9);
        # the recipe fold is Rust+TS value-exact == CPython (Go carries no _iter).
        # Frozen sample (idea "energy flow"/"coherence xyz", concept "Energy
        # Flow"/"energy flows as coherence through the body field", concept
        # keywords [Energy, Tissue]) → forward 3/4, reverse 1/2, name bonus 0.3 →
        # round(min(0.5*0.75 + 0.3*0.5 + 0.3, 1.0), 4) = 0.825, a non-integer
        # float that prints identically across kernels.
        "route": "/api/utils/concept_match_score",
        "recipe": "endpoint_concept_match_score_demo.fk",
        "expected_result": "0.825",
    },
    {
        # The TAG-RESONANCE SCORING of belief_service._score_tag_match — folds
        # EXACT STRING MEMBERSHIP (str_eq over a list), the equality counterpart
        # to concept_match_score's substring (str_find) fold. The honest seam:
        # the host extracts the two tag lists (profile.interest_tags off the
        # BeliefProfile model + the idea's tags — model field extraction dissolves
        # at the bridge) and dedups each with set() (field extraction + dedup, the
        # deferred host-side capability), and the kernel SCORES the two deduped
        # string lists: matched = how many unique contributor tags appear in
        # idea_tags (nested str_eq fold), then max(0.0, min(1.0, matched /
        # len(contributor_tags))) with a 0.5 empty-guard when either list is empty
        # — _score_tag_match's shape verbatim (empty-guard 0.5 not 0.0; denominator
        # the deduped contributor count; clamp [0,1]). str_eq is COMPARE.EQ,
        # three-way value-identical for ASCII; the recipe's nested fold is Rust+TS
        # value-exact == CPython (Go carries no _iter). Frozen sample (contributor
        # [energy, flow, coherence, field], idea [energy, flow]) → matched 2 of 4 →
        # max(0.0, min(1.0, 2/4)) = 0.5, an exact float that prints identically.
        "route": "/api/utils/tag_match_score",
        "recipe": "endpoint_tag_match_score_demo.fk",
        "expected_result": "0.5",
    },
    {
        # The WORLDVIEW-COSINE SCORING of belief_service._score_worldview_alignment
        # — COSINE SIMILARITY over two parallel axis-vectors, dot(a,b) /
        # (||a||*||b||), the geometric counterpart to tag_match_score's set-
        # membership fold. The honest seam: the host projects both worldview-axes
        # dicts into PARALLEL float vectors in the fixed BeliefAxis order
        # (dict→vector projection, the filtering-adjacent host-side seam) + names
        # matched_axes (cv>0.3 AND iv>0.3, a naming side-output), and the kernel
        # SCORES the two parallel vectors: dot + both sums-of-squares in one
        # parallel index walk, sqrt each norm (math_sqrt), guarded ratio (denom>0
        # else 0.5), clamp [0,1] — _score_worldview_alignment's geometric shape
        # verbatim (the empty-idea_axes → 0.5 branch and matched_axes stay host-side;
        # the zero-denom → 0.5 guard is in the recipe). math_sqrt is IEEE-correct,
        # three-way bit-identical (float-natives-band.fk → sqrt(16)==4.0 tolerance-
        # free; the 1-ULP caveat is math_pow's, not math_sqrt's); the parallel
        # _get-indexed while fold is Rust+TS value-exact == CPython (Go carries no
        # _get/_iter fold, the same situation weighted_average ships under). Frozen
        # sample (contributor [0.6,0,0.8,0,0,0], idea [0.8,0,0.6,0,0,0]) → dot 0.96
        # / (1.0*1.0) = 0.96, an exact rational that prints identically; the
        # irrational-cosine edge (1/sqrt(2) = 0.7071067811865475) is three-way
        # bit-identical.
        "route": "/api/utils/worldview_alignment",
        "recipe": "endpoint_worldview_alignment_demo.fk",
        "expected_result": "0.96",
    },
    {
        # The COVERAGE/SCORE REDUCTION of collective_health_service.
        # _coherence_summary — four guarded coverage ratios + a weighted-sum
        # score with the task_count==0 neutral guard (0.5) and a [0.0, 1.0]
        # clamp, each output round(_, 4). Built entirely from banked
        # capabilities: safe_ratio's `if denom>0 else default` (grounded_value),
        # the neutral guard + two-sided clamp as max2/min2 branches, and
        # round_ndigits. The honest seam: the host walks the heterogeneous task
        # `context` dicts to produce the counts (the dict-over-collection
        # extraction held host-side BY DESIGN); the kernel folds the ratios +
        # score + round. Pure arithmetic, no _iter/_get fold, so three-way clean
        # including Go. Frozen sample (task_count 10, target 7, evidence 5,
        # task_card 6, scores_sum 4.5, scores_len 6) → [0.665, 0.7, 0.6, 0.75,
        # 0.5], all NON-integer floats so no value crosses the print boundary.
        "route": "/api/utils/coherence_summary_score",
        "recipe": "endpoint_coherence_summary_score_demo.fk",
        "expected_result": "[0.665, 0.7, 0.6, 0.75, 0.5]",
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


def aggregate(collect_edges: bool = False) -> dict:
    """Trace every kernel-served recipe and aggregate the attribution signal.

    ``collect_edges`` (default False) adds a ``per_route_natives`` key carrying
    the per-route native fire-counts — the raw material the ``--record`` path
    persists as edge-events. It is OFF by default so the no-flag run (human and
    ``--json``) is byte-identical to today.

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
    # Per-route native fire-counts — the raw material of the edge-event
    # (route -> native -> count). Kept on the aggregate so --record can persist
    # it as edge-events WITHOUT re-tracing; it costs nothing when not recorded.
    per_route_natives: list[dict] = []
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
        route_natives: dict[str, int] = defaultdict(int)
        for n in tr.get("natives", []):
            nm = n.get("name", "?")
            cnt = int(n.get("count", 0))
            native_counts[nm] += cnt
            route_natives[nm] += cnt
        per_route_natives.append({"route": entry["route"], "natives": dict(route_natives)})
        per_recipe.append(rec)

    # Attribute each fired native to its Blueprint NodeID (transparency thread).
    natives_with_bp: dict[str, dict] = {}
    for name, count in native_counts.items():
        natives_with_bp[name] = {
            "count": count,
            "blueprint": native_blueprint(name),
        }

    inert = _inert_natives(set(native_counts))
    report: dict = {
        "per_recipe": per_recipe,
        "arms": dict(arm_counts),
        "functions": dict(fn_counts),
        "natives": natives_with_bp,
        "inert_natives": inert,
        # Embodiment projection (lc-the-trace-is-the-memory, move 3): the fired
        # Blueprint NodeIDs projected toward the activity-weighted center;
        # |projection| -> 0 = the body's lived structural center. The inert
        # block carries the undefined-projection class.
        "embodiment": embodiment_projection(natives_with_bp),
        "embodiment_inert": embodiment_inert(natives_with_bp, inert),
        "reached": reached,
        "eligible": len(KERNEL_SERVED_RECIPES),
    }
    if collect_edges:
        # Only present under --record: the per-route native fire-counts that
        # become edge-event rows. Kept OFF the default dict so the no-flag run
        # (human and --json) is byte-identical to today — zero behavior change.
        report["per_route_natives"] = per_route_natives
    return report


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


# ---------------------------------------------------------------------------
# Embodiment projection — lc-the-trace-is-the-memory, move (3).
#
# The concept: categories genuinely embodied — co-fired by real execution —
# develop a shared value-equivalence whose scalar projection approaches zero;
# inert categories (registered, never fired) stay far / undefined. This is the
# working instrument over the CURRENT attribution snapshot. It reuses the
# body's OWN structural distance — the Manhattan distance over the NodeID
# 4-tuple (pkg, level, type, instance) that /api/utils/nodeid_distance
# computes (see endpoint_nodeid_distance_demo.py / utils.nodeid_distance_py) —
# rather than inventing a new metric. Core-abstraction-first: ONE projection
# mechanism over the fired Blueprint NodeIDs as DATA.
#
# Honest scope (printed, not buried): this projects over the per-Blueprint
# fire counts the report already aggregates — a snapshot, not yet the
# persisted edge-event memory the concept names as the larger next build.
# What it measures is real: structural distance from the activity-weighted
# center of what actually fires. What it is NOT: a record that accumulates
# across runs (each run recomputes the snapshot), nor a value-equivalence
# learned from co-firing history (that needs the edge-event ledger).
# ---------------------------------------------------------------------------


def _parse_nodeid(nid: str | None) -> tuple[int, int, int, int] | None:
    """Parse a Blueprint NodeID string '@pkg.level.type.inst' to a 4-tuple."""
    if not nid or not nid.startswith("@"):
        return None
    parts = nid[1:].split(".")
    if len(parts) != 4:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    except ValueError:
        return None


def _nodeid_distance(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Manhattan distance over the NodeID 4-tuple — the body's own metric.

    Identical shape to utils.nodeid_distance_py / endpoint_nodeid_distance_demo:
    sum of absolute differences across (pkg, level, type, instance). Floats are
    allowed because the embodied center is an activity-weighted centroid (a
    mean position), not a discrete lattice node.
    """
    return sum(abs(a[i] - b[i]) for i in range(4))


def embodiment_projection(natives: dict) -> dict:
    """Project each fired Blueprint NodeID category toward the embodied center.

    Input: the ``natives`` map from ``aggregate()`` — {native_name -> {count,
    blueprint}}. Natives sharing a Blueprint NodeID ARE one category
    (content-addressing: same structure, same query key), so the projection's
    primary unit is the distinct fired NodeID, with its member natives and
    total fire-count.

    The embodied center is the **activity-weighted centroid** of the fired
    NodeID 4-tuples — each NodeID weighted by its total fire-count. It is the
    "center of mass of what fires": the structural position the bulk of live
    execution clusters around. The projection of a category is its Manhattan
    NodeID-distance from that centroid (the body's own nodeid_distance shape).

    The honest property the concept demands holds: ``|projection| -> 0`` for
    the categories structurally closest to the activity center, which are the
    ones the highest-fire natives belong to; categories farther in NodeID
    space project larger. Inert categories are handled separately by
    ``embodiment_inert`` — zero edge-events means projection **undefined**, a
    distinct class, never ranked near zero by coordinate accident.

    Returns:
      - center:    [pkg, level, type, inst] activity-weighted centroid (floats)
      - total_fires: total fire-count across all fired NodeIDs (the weight sum)
      - categories: [{blueprint, nodeid, fires, share, projection, natives}]
                    sorted by projection ascending (most-embodied first).
    """
    # Collapse natives -> distinct fired Blueprint NodeIDs (the categories).
    by_node: dict[str, dict] = {}
    for name, info in natives.items():
        bp = info.get("blueprint")
        tup = _parse_nodeid(bp)
        if tup is None:
            # A fired native whose NodeID won't resolve has no structural
            # position — it can't be projected. Honest: skip from the geometric
            # projection (it still appears in the hot-natives section).
            continue
        slot = by_node.setdefault(
            bp, {"nodeid": tup, "fires": 0, "natives": []}
        )
        slot["fires"] += int(info.get("count", 0))
        slot["natives"].append(name)

    if not by_node:
        return {"center": None, "total_fires": 0, "categories": []}

    total = sum(s["fires"] for s in by_node.values()) or 1
    center = tuple(
        sum(s["nodeid"][i] * s["fires"] for s in by_node.values()) / total
        for i in range(4)
    )

    categories: list[dict] = []
    for bp, s in by_node.items():
        categories.append(
            {
                "blueprint": bp,
                "nodeid": list(s["nodeid"]),
                "fires": s["fires"],
                "share": round(s["fires"] / total, 4),
                "projection": round(_nodeid_distance(s["nodeid"], center), 4),
                "natives": sorted(s["natives"]),
            }
        )
    # Most-embodied first: smallest |projection|, ties broken by more fires.
    categories.sort(key=lambda c: (c["projection"], -c["fires"]))

    return {
        "center": [round(c, 4) for c in center],
        "total_fires": total,
        "categories": categories,
    }


def embodiment_inert(natives: dict, inert_names: list[str]) -> dict:
    """The inert class — registered natives that never fired.

    The concept's "no edge-events -> projection undefined" partition: these are
    not ranked near zero, they are far-by-definition. Where a NodeID resolves,
    we report its structural distance from the embodied center FOR CONTEXT (so
    an operator can see how far out the never-fired tissue sits), but the
    projection itself stays ``None`` — undefined — because zero activity means
    the category has not converged toward anything. Where no NodeID resolves,
    the native carries no structural position at all: the purest "why are you
    here, never involved?" candidate.

    Needs the projection's center, so the caller passes the fired ``natives``
    to recompute it (cheap; keeps this function pure over its inputs).
    """
    proj = embodiment_projection(natives)
    center = proj["center"]
    rows: list[dict] = []
    for name in inert_names:
        bp = native_blueprint(name)
        if bp == "null":  # the kernel's sentinel for an uncatalogued native
            bp = None
        tup = _parse_nodeid(bp)
        dist = (
            round(_nodeid_distance(tup, tuple(center)), 4)
            if (tup is not None and center is not None)
            else None
        )
        rows.append(
            {
                "native": name,
                "blueprint": bp,
                "nodeid": list(tup) if tup else None,
                "projection": None,  # undefined: zero edge-events
                "structural_distance": dist,  # context only, not the projection
            }
        )
    # Resolvable ones first (sorted by structural distance), unresolvable last.
    rows.sort(
        key=lambda r: (
            r["structural_distance"] is None,
            r["structural_distance"] if r["structural_distance"] is not None else 0.0,
            r["native"],
        )
    )
    return {"center": center, "inert": rows}


# ---------------------------------------------------------------------------
# Edge-event memory — lc-the-trace-is-the-memory, moves (1) and (2), the SAFE
# offline slice.
#
# Move 1: the execution trace IS memory, recorded as edge-events
# (firing-cell, touched-cell, event). Here the firing-cell is the route's
# recipe, the touched-cell is the native's Blueprint NodeID, and the event is
# a fire-count for this run. We persist each as an append-only JSONL row so the
# memory ACCUMULATES across runs instead of evaporating with each snapshot.
#
# Move 2: query per cell IS query per category — the Blueprint NodeID is the
# content-addressed category, so summing accumulated fire_counts per NodeID
# (across all routes and all recorded runs) gives the per-category memory the
# projection reads.
#
# CRITICAL SEAM (off the hot path): this records the OFFLINE attribution run's
# traces, NOT the live `serve_via_kernel` request path. Recording on the live
# request path (async / sampled / opt-in, to avoid regressing the sub-100µs
# inline-kernel profile) is a SEPARATE, larger decision that belongs to Urs —
# it touches production latency. This module never touches a live route.
#
# Gating: like runtime_event_store.enabled(), recording is OPT-IN and a no-op
# when the store path is unconfigured. A fresh checkout with no path set runs
# the report identically to today — no writes, no file, no side-effects.
# ---------------------------------------------------------------------------

_EDGE_EVENTS_ENV = "KERNEL_EDGE_EVENTS_PATH"


def edge_events_path() -> Path | None:
    """The configured edge-event store path, or None when unconfigured.

    Reads ``KERNEL_EDGE_EVENTS_PATH``. When unset/blank the store is disabled —
    recording is a no-op and the accumulated read finds no memory (falls back
    to the snapshot). This is the runtime_event_store.enabled() gating shape:
    opt-in, no-op by default, no side-effects in a fresh checkout.
    """
    raw = os.environ.get(_EDGE_EVENTS_ENV, "").strip()
    return Path(raw) if raw else None


# ---------------------------------------------------------------------------
# The surprise gate — lc-identity-is-shared-blueprint-and-recipe, the honest
# memory economy.
#
# The concept: low surprise == embodied identity == |projection| -> 0. What is
# cheap to predict (the embodied center) does not need to be persistently
# tracked — it lives in RAM/the-run only. Only the SURPRISING tail (large
# projection = far from the activity-weighted center = model-changing = worth
# the cost of remembering) gets written to durable memory.
#
# The instrument already exists: embodiment_projection() computes, per category
# (Blueprint NodeID), its Manhattan distance from the activity-weighted center.
# That projection IS the surprise proxy. The gate is one comparison over the
# categories-as-DATA: persist iff projection > threshold.
#
# Threshold honesty (the default and why): the gate is RELATIVE, not a magic
# constant. The default is the MEAN projection across the fired categories —
# the "above-average surprise" tail. A relative threshold is the honest choice
# because it adapts to the actual distribution of this run rather than asserting
# a fixed cutoff that would mean different things as the route surface grows.
# The mean (not the median) is chosen so the embodied CENTER — the lowest-
# projection, highest-proximity category (e.g. _plus @1.2.27.1, the activity
# centroid the bulk of execution clusters around) — stays below the line and is
# NOT persisted, while categories sitting structurally far out cross it. On the
# current 3-category surface {1.64, 8.64, 10.36} the mean is 6.88: _plus's 1.64
# stays RAM-only (predictable center), the two far categories persist. The
# median (8.64) would also keep _plus in RAM but would drop a genuinely-far
# category that sits at the median — the mean keeps the full surprising tail.
#
# Modes (KERNEL_SURPRISE_MODE / --surprise-mode), all over the same gate:
#   mean   (default) — persist projection > mean(projections): above-average surprise
#   median           — persist projection > median(projections)
#   fixed:<T>        — persist projection > T (absolute; for debugging/pinning)
#   topk:<K>         — persist the K most-surprising categories
# The threshold each resolves to is REPORTED, never buried — the operator sees
# the cutoff and which categories landed on each side.
# ---------------------------------------------------------------------------

_SURPRISE_MODE_ENV = "KERNEL_SURPRISE_MODE"
_DEFAULT_SURPRISE_MODE = "mean"


def is_surprising(projection: float, threshold: float) -> bool:
    """The gate — ONE comparison over a category's projection as DATA.

    Surprising == far from the embodied center == projection ABOVE the
    threshold. The embodied center (|projection| -> 0) is by definition NOT
    surprising: it stays below the line and lives in RAM only. Strict ``>`` so
    a category sitting exactly at a relative threshold (e.g. the lone median
    category) is treated as predictable, not persisted — the gate keeps the
    tail, not the boundary.
    """
    return projection > threshold


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def surprise_threshold(
    categories: list[dict], mode: str = _DEFAULT_SURPRISE_MODE
) -> tuple[float, str]:
    """Resolve the projection threshold for the given categories + mode.

    Returns ``(threshold, resolved_mode_label)``. The categories carry the
    embodiment projection already computed by ``embodiment_projection``; this
    reduces their projections to a single cutoff per the chosen mode. ONE
    resolver over the projections-as-DATA — the modes differ only in the
    statistic, not in the gate.

    ``mean``/``median`` are relative (adapt to this run's distribution).
    ``fixed:<T>`` pins an absolute cutoff (debug/pin). ``topk:<K>`` resolves to
    a threshold just below the K-th largest projection so the same ``> T`` gate
    keeps exactly the K most-surprising categories.
    """
    projs = [c["projection"] for c in categories]
    if not projs:
        return (0.0, mode)

    m = (mode or _DEFAULT_SURPRISE_MODE).strip().lower()

    if m.startswith("fixed:"):
        try:
            t = float(m.split(":", 1)[1])
        except ValueError:
            t = sum(projs) / len(projs)
            return (t, f"mean (bad fixed: spec, fell back)")
        return (t, f"fixed:{t:g}")

    if m.startswith("topk:"):
        try:
            k = int(m.split(":", 1)[1])
        except ValueError:
            k = 1
        k = max(0, min(k, len(projs)))
        if k == 0:
            # Keep nothing: threshold above the max so the gate excludes all.
            return (max(projs), "topk:0 (persist none)")
        if k >= len(projs):
            # Keep all: threshold below the min so the gate includes all.
            return (min(projs) - 1.0, f"topk:{k} (persist all {len(projs)})")
        # Threshold strictly between the K-th and (K+1)-th largest projection,
        # so `> T` keeps exactly the top K. Strict `>` means we set T to the
        # (K+1)-th largest value itself: the K above it pass, it and below stay.
        ranked_desc = sorted(projs, reverse=True)
        return (ranked_desc[k], f"topk:{k}")

    if m == "median":
        return (_median(projs), "median")

    # default: mean — the above-average-surprise tail.
    return (sum(projs) / len(projs), "mean")


def surprise_split(
    report: dict, mode: str = _DEFAULT_SURPRISE_MODE
) -> dict:
    """Partition the fired categories into surprising (persist) vs RAM-only.

    Reads the embodiment projection already on the report, resolves the
    threshold for ``mode``, and applies ``is_surprising`` to each category.
    Returns:
      - threshold:       the resolved projection cutoff
      - mode:            the resolved mode label (what was actually applied)
      - surprising:      [blueprint, ...] categories ABOVE the gate (persisted)
      - predictable:     [blueprint, ...] categories at/below the gate (RAM only)
      - surprising_full / predictable_full: the full category dicts for each side
    The split is pure DATA over the categories — the recorder consumes
    ``surprising`` as the set of Blueprint NodeIDs whose rows are written.
    """
    emb = report.get("embodiment") or {}
    cats = emb.get("categories") or []
    threshold, resolved = surprise_threshold(cats, mode)
    surprising_full = [c for c in cats if is_surprising(c["projection"], threshold)]
    predictable_full = [
        c for c in cats if not is_surprising(c["projection"], threshold)
    ]
    return {
        "threshold": round(threshold, 4),
        "mode": resolved,
        "surprising": [c["blueprint"] for c in surprising_full],
        "predictable": [c["blueprint"] for c in predictable_full],
        "surprising_full": surprising_full,
        "predictable_full": predictable_full,
    }


def record_edge_events(
    report: dict,
    path: Path,
    *,
    surprise_gated: bool = True,
    mode: str = _DEFAULT_SURPRISE_MODE,
) -> dict:
    """Persist this run's per-route fire-events as edge-event rows (JSONL).

    SURPRISE-GATED by default (lc-identity-is-shared-blueprint-and-recipe): the
    predictable embodied center (|projection| -> 0) is kept in RAM only; ONLY
    the surprising tail (category projection ABOVE the threshold) is written.
    This corrects the naive "record everything" recorder — the body stops
    paying full memory cost for what it already predicts.

    ONE record function over the aggregate's per-route natives as DATA: each
    (route, native, blueprint, fire_count) row is emitted IFF its category's
    Blueprint NodeID is in the surprising set. ``surprise_gated=False`` opts
    back into the legacy everything-recorder (debugging / parity baseline).

    Row shape (unchanged): {recorded_at, run_id, route, native, blueprint,
    fire_count} — plus, when gated, ``surprise`` carrying the projection and
    threshold so the persisted memory is self-describing about WHY it was kept.

    The native's Blueprint NodeID is the content-addressed category (move 2):
    pulled from the run's already-resolved ``natives`` map; no extra kernel
    calls. Returns a dict: {written, skipped, threshold, mode, surprising,
    predictable} — the RAM-vs-persist split, so the gating is visible.
    """
    natives = report.get("natives", {})
    recorded_at = datetime.now(timezone.utc).isoformat()
    run_id = recorded_at  # one run == one timestamped batch of edge-events

    split = surprise_split(report, mode)
    threshold = split["threshold"]
    # Map each category dict by Blueprint NodeID for fast projection lookup.
    proj_by_bp = {
        c["blueprint"]: c["projection"]
        for c in (report.get("embodiment", {}) or {}).get("categories", [])
    }
    surprising_bps = set(split["surprising"])

    rows: list[dict] = []
    skipped = 0
    for route_entry in report.get("per_route_natives", []):
        route = route_entry["route"]
        for native, fire_count in route_entry["natives"].items():
            bp = (natives.get(native) or {}).get("blueprint")
            if surprise_gated and bp not in surprising_bps:
                # Predictable center (or unresolved NodeID) — RAM only, not
                # persisted. Unresolved-NodeID categories have no projection /
                # structural position, so the gate cannot call them surprising;
                # honest default is to NOT persist (matches the inert handling).
                skipped += 1
                continue
            row = {
                "recorded_at": recorded_at,
                "run_id": run_id,
                "route": route,
                "native": native,
                "blueprint": bp,
                "fire_count": int(fire_count),
            }
            if surprise_gated:
                # Self-describing: the persisted trace carries WHY it was kept.
                row["surprise"] = {
                    "projection": proj_by_bp.get(bp),
                    "threshold": threshold,
                    "mode": split["mode"],
                }
            rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    return {
        "written": len(rows),
        "skipped": skipped,
        "threshold": threshold,
        "mode": split["mode"],
        "gated": surprise_gated,
        "surprising": split["surprising"],
        "predictable": split["predictable"],
        "surprising_full": split["surprising_full"],
        "predictable_full": split["predictable_full"],
    }


def read_edge_events(path: Path) -> list[dict]:
    """Read all accumulated edge-event rows from the JSONL store."""
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def accumulated_natives(rows: list[dict]) -> dict:
    """Fold accumulated edge-events into a ``natives``-shaped map.

    Sums ``fire_count`` per native across ALL recorded runs and routes, pairing
    each with its Blueprint NodeID. The output is the SAME shape
    ``embodiment_projection`` consumes for the snapshot — so the projection
    mechanism is ONE function, fed either the live snapshot or the accumulated
    memory. This is move (2) made concrete: per-NodeID summation across history
    is the per-category memory.
    """
    by_native: dict[str, dict] = {}
    for row in rows:
        name = row.get("native")
        if not name:
            continue
        slot = by_native.setdefault(name, {"count": 0, "blueprint": row.get("blueprint")})
        slot["count"] += int(row.get("fire_count", 0))
        if slot["blueprint"] is None:
            slot["blueprint"] = row.get("blueprint")
    return by_native


def accumulated_report(path: Path) -> dict | None:
    """Build a projection over the ACCUMULATED edge-event memory, or None.

    Reads the whole store, folds it per category (move 2), and runs the SAME
    ``embodiment_projection`` over the accumulated fire-counts. Returns a dict
    carrying the runs/rows counts and the accumulated projection, or None when
    no memory has been recorded yet (caller falls back to the snapshot and says
    so — honest about empty history).
    """
    rows = read_edge_events(path)
    if not rows:
        return None
    natives = accumulated_natives(rows)
    run_ids = {r.get("run_id") for r in rows if r.get("run_id")}
    return {
        "runs": len(run_ids),
        "rows": len(rows),
        "natives": natives,
        "embodiment": embodiment_projection(natives),
    }


# ---------------------------------------------------------------------------
# The LEARNING half — lc-identity-is-shared-blueprint-and-recipe, the build the
# fold recipe stood ready for. The compression-fold recipe APPLIES a given
# reduction (idx + coeffs); this LEARNS, per category, WHICH dimension of the
# accumulated edge-event memory went redundant and the coeffs that fold it.
#
# Per category (Blueprint NodeID — content-addressing), the accumulated rows
# form a matrix: one row per recorded edge-event, columns the numeric
# dimensions of that memory:
#
#     [pkg, level, type, inst, fire_count]
#
# (the four NodeID components + the fire-count signal). A dimension is
# REDUNDANT iff it is LINEARLY PREDICTABLE from the others across the
# category's rows with ZERO residual — exactly the condition `reconstruct`
# needs, since `predicted[idx] = Σ_{j≠idx} coeffs[j] · inputs[j]` is a linear
# combination with NO intercept. The learner solves least-squares for those
# coeffs per candidate dimension and measures the residual; a dimension whose
# residual is within float tolerance is genuinely redundant — safe to fold
# losslessly. A dimension that carries residual is surprising — NEVER folded
# (folding it would lose information; the concept's whole point).
#
# Honesty bar (named, not buried): redundancy == max-abs residual ≤
# _REDUNDANCY_TOL. This is exact linear redundancy (a constant dimension, or a
# literal linear combination of the others across ALL rows), not a noisy fit.
# A category where every dimension carries residual above tolerance is NOT
# compressible — the learner says so and folds nothing.
#
# core-abstraction-first: ONE learner over categories-as-DATA and dimensions-
# as-DATA. No per-dimension or per-category special-casing — the spec (idx +
# coeffs) drops out as values the same `compress`/`reconstruct` recipe applies.
#
# OFFLINE only: reads the persisted memory, runs the analysis, optionally
# writes the compressed memory. Never the live request path.
# ---------------------------------------------------------------------------

# The numeric dimensions of a category's edge-event memory, in column order.
# projection is DELIBERATELY excluded from the folded matrix: it is a
# per-category CONSTANT derived from the NodeID position (the same value on
# every row of a category), so it is trivially redundant but carries no
# independent signal — folding it proves nothing the NodeID columns don't. The
# honest dimensions that vary across a category's rows are the four NodeID
# components (constant within a category) plus fire_count (the one that moves).
_MEMORY_DIMS = ["pkg", "level", "type", "inst", "fire_count"]

# Redundancy tolerance: a dimension counts as redundant iff the least-squares
# reconstruction's max-abs residual across the category's rows is at or below
# this. Tight enough that only EXACT linear redundancy (constant column or a
# literal linear combination) passes — never a noisy fit. The normal-equations
# solve introduces float round-off at the 1e-12 scale on integer data, so the
# bar sits a few orders above that and far below any real residual (the
# fire_count axis carries residual ~14, six orders larger).
_REDUNDANCY_TOL = 1e-6


def _memory_matrix(rows: list[dict]) -> list[list[float]]:
    """Build the per-row dimension matrix for ONE category's edge-events.

    Each row -> [pkg, level, type, inst, fire_count] as floats. The four NodeID
    components come from the row's Blueprint (constant within a category by
    content-addressing); fire_count is the per-event signal that varies.
    """
    M: list[list[float]] = []
    for r in rows:
        tup = _parse_nodeid(r.get("blueprint"))
        if tup is None:
            continue
        M.append(
            [
                float(tup[0]),
                float(tup[1]),
                float(tup[2]),
                float(tup[3]),
                float(int(r.get("fire_count", 0))),
            ]
        )
    return M


def _solve_least_squares_no_intercept(
    M: list[list[float]], idx: int
) -> tuple[list[float], float]:
    """Predict column ``idx`` from the OTHER columns, no intercept.

    Solves ``A x = M[:,idx]`` in the least-squares sense (normal equations
    ``AᵀA x = Aᵀy``) where ``A`` is M with column idx removed. Returns
    ``(coeffs, residual)`` where ``coeffs`` is the FULL N-length coefficient
    vector with ``coeffs[idx] = 0`` (the axis does not predict itself — exactly
    the shape ``reconstruct`` consumes) and ``residual`` is the MAX-ABS
    prediction error across the rows (the honest redundancy measure: a single
    surprising row keeps the dimension out of the redundant set).

    Pure Python (Gaussian elimination with partial pivoting) — no numpy
    dependency, and the matrices are tiny (≤5 columns).
    """
    n = len(M)
    d = len(M[0]) if M else 0
    cols = [j for j in range(d) if j != idx]
    k = len(cols)
    if n == 0 or k == 0:
        return ([0.0] * d, float("inf"))

    # Normal equations: AᵀA (k×k) and Aᵀy (k).
    ata = [[sum(M[r][cols[a]] * M[r][cols[b]] for r in range(n)) for b in range(k)] for a in range(k)]
    aty = [sum(M[r][cols[a]] * M[r][idx] for r in range(n)) for a in range(k)]

    # Augmented [AᵀA | Aᵀy], Gauss-Jordan with partial pivot.
    aug = [ata[i][:] + [aty[i]] for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(aug[r][c]))
        if abs(aug[piv][c]) < 1e-12:
            # Singular pivot — that predictor column is constant-zero or
            # collinear; leave its coefficient 0 and move on (a degenerate
            # predictor cannot help, the residual measure judges the outcome).
            continue
        aug[c], aug[piv] = aug[piv], aug[c]
        pv = aug[c][c]
        aug[c] = [v / pv for v in aug[c]]
        for r in range(k):
            if r != c and abs(aug[r][c]) > 1e-15:
                f = aug[r][c]
                aug[r] = [aug[r][t] - f * aug[c][t] for t in range(k + 1)]
    x = [aug[i][k] for i in range(k)]

    # Max-abs residual across rows (the redundancy measure).
    resid = 0.0
    for r in range(n):
        pred = sum(x[a] * M[r][cols[a]] for a in range(k))
        resid = max(resid, abs(pred - M[r][idx]))

    coeffs = [0.0] * d
    for a in range(k):
        coeffs[cols[a]] = x[a]
    return (coeffs, resid)


def _is_integer_coeffs(coeffs: list[float], tol: float = 1e-9) -> bool:
    """True when every coefficient is (within tol) an integer.

    Integer coeffs + integer dimension values keep the Form ``compress`` /
    ``reconstruct`` round-trip on exact integers — no float crosses the kernel
    print boundary, so the proof is byte-exact across siblings.
    """
    return all(abs(c - round(c)) <= tol for c in coeffs)


def learn_redundant_dimensions(rows: list[dict]) -> dict:
    """Per category, LEARN which dimension(s) of the memory are redundant.

    Groups the accumulated edge-event rows by Blueprint NodeID (the category),
    builds each category's dimension matrix, and for every candidate dimension
    solves the no-intercept least-squares predictor. A dimension is REDUNDANT
    iff its residual ≤ ``_REDUNDANCY_TOL`` — exactly linearly predictable from
    the others, so ``reconstruct`` recovers it without loss.

    Per category it picks ONE dimension to fold (the redundant one with the
    smallest residual; ties broken toward INTEGER coeffs so the Form round-trip
    stays on exact integers, then toward the lowest index for determinism).
    A category with NO redundant dimension is reported as NOT compressible —
    nothing folded, honestly named.

    Returns:
      {
        "dims": _MEMORY_DIMS,
        "tolerance": _REDUNDANCY_TOL,
        "categories": [
          {
            "blueprint", "rows", "n_dims",
            "redundant": [{"idx","dim","residual","coeffs","integer_coeffs"}],
            "compressible": bool,
            "fold": {"idx","dim","coeffs","residual","integer_coeffs"} | None,
            "sample_vec": [..],   # one real row, for the round-trip proof
          }, ...
        ],
      }
    """
    by_bp: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        bp = r.get("blueprint")
        if bp:
            by_bp[bp].append(r)

    categories: list[dict] = []
    for bp, cat_rows in sorted(by_bp.items()):
        M = _memory_matrix(cat_rows)
        d = len(_MEMORY_DIMS)
        cat: dict = {
            "blueprint": bp,
            "rows": len(M),
            "n_dims": d,
            "redundant": [],
            "compressible": False,
            "fold": None,
            "sample_vec": [int(round(x)) for x in M[0]] if M else None,
        }
        if not M:
            categories.append(cat)
            continue

        for idx in range(d):
            coeffs, resid = _solve_least_squares_no_intercept(M, idx)
            if resid <= _REDUNDANCY_TOL:
                # Round coeffs that are integers-within-tol to clean ints, so
                # the fold spec is exact for the Form round-trip.
                int_ok = _is_integer_coeffs(coeffs)
                clean = [round(c) if int_ok else c for c in coeffs]
                cat["redundant"].append(
                    {
                        "idx": idx,
                        "dim": _MEMORY_DIMS[idx],
                        "residual": resid,
                        "coeffs": clean,
                        "integer_coeffs": int_ok,
                    }
                )

        if cat["redundant"]:
            cat["compressible"] = True
            # Pick the fold: smallest residual, prefer integer coeffs, then
            # lowest index — deterministic, and integer-clean for the proof.
            best = min(
                cat["redundant"],
                key=lambda rd: (rd["residual"], not rd["integer_coeffs"], rd["idx"]),
            )
            cat["fold"] = {
                "idx": best["idx"],
                "dim": best["dim"],
                "coeffs": best["coeffs"],
                "residual": best["residual"],
                "integer_coeffs": best["integer_coeffs"],
            }
        categories.append(cat)

    return {
        "dims": _MEMORY_DIMS,
        "tolerance": _REDUNDANCY_TOL,
        "categories": categories,
    }


# ---------------------------------------------------------------------------
# Driving the REAL Form compress/reconstruct recipe on the proof case.
#
# The concept says compression IS a Form recipe — so the round-trip proof must
# run the actual kernel recipe (grammars/compression-fold.fk), not a Python
# reimplementation. The learner runs in Python (least-squares over the rows);
# the APPLY + PROOF drives the real recipe through the kernel on the
# representative integer vector. We say plainly which part ran where.
# ---------------------------------------------------------------------------

_COMPRESSION_FOLD_GRAMMAR = (
    ROOT / "form" / "form-stdlib" / "grammars" / "compression-fold.fk"
)


def _form_list(ints: list[int]) -> str:
    """Render a Python int list as a Form ``(list ...)`` literal."""
    return "(list " + " ".join(str(int(round(x))) for x in ints) + ")"


def drive_form_fold(
    vec: list[int], idx: int, coeffs: list[int]
) -> dict | None:
    """Run the REAL Form compress/reconstruct recipe on one vector via the kernel.

    Drives ``grammars/compression-fold.fk``: ``compress(vec, idx)`` then
    ``reconstruct(folded, idx, coeffs)``, and ``cf-list-eq`` of the result with
    the original — all inside the Form runtime, no Python arithmetic on the
    fold itself. Returns:
      {"exact": bool, "n": int, "folded_len": int, "reconstructed": [..]}
    or None when the kernel/grammar is unavailable (honest: the analysis still
    reports the LEARNED redundancy, marked as Python-only-not-kernel-proven).

    Integer vec + integer coeffs keep the whole round-trip on exact integers, so
    the kernel's printed result is byte-exact — the same value the band proves
    three-way.
    """
    if not kernel_available() or not _COMPRESSION_FOLD_GRAMMAR.is_file():
        return None
    expr = (
        "(do"
        f"  (let v {_form_list(vec)})"
        f"  (let folded (compress v {idx}))"
        f"  (let coeffs {_form_list(coeffs)})"
        f"  (let rebuilt (reconstruct folded {idx} coeffs))"
        "  (list (cf-list-eq rebuilt v) (len v) (len folded) rebuilt))"
    )
    # Write the driver beside nothing — pass it as a second source after the
    # grammar prelude (mirrors validate.sh's prelude+test invocation).
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".fk", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(expr + "\n")
        driver = fh.name
    try:
        proc = _run_kernel([str(_COMPRESSION_FOLD_GRAMMAR), driver])
    finally:
        try:
            os.unlink(driver)
        except OSError:
            pass
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        return None
    last = out.splitlines()[-1].strip()
    # Expect a Form list like: [1, 5, 4, [1, 2, 34, 1, 7]]
    try:
        parsed = json.loads(last)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) != 4:
        return None
    return {
        "exact": parsed[0] == 1,
        "n": int(parsed[1]),
        "folded_len": int(parsed[2]),
        "reconstructed": parsed[3],
        "raw": last,
    }


def compress_memory(path: Path) -> dict | None:
    """Learn per-category redundancy over the accumulated memory and fold it.

    The wiring that closes the autoencoder loop:
      1. read the accumulated edge-event memory,
      2. LEARN, per category, which dimension is redundant (least-squares),
      3. APPLY the Form compression-fold to the redundant axis and PROVE the
         round-trip recovers it EXACTLY on a real recorded vector (driving the
         actual kernel recipe), and
      4. report the size reduction (N→N−1 per row) for the compressible
         categories, and honestly name the categories where nothing was
         redundant.

    Returns None when there is no accumulated memory yet (caller says so).
    Otherwise a dict carrying the learning result, the per-compressible-category
    kernel-driven round-trip proof, and the structural shrink. OFFLINE: this
    reads and analyzes; it does not mutate the live store unless a future
    writer is wired (the fold is proven, the compressed store write is a
    deliberate, separately-named step).
    """
    rows = read_edge_events(path)
    if not rows:
        return None
    learned = learn_redundant_dimensions(rows)
    run_ids = {r.get("run_id") for r in rows if r.get("run_id")}

    proofs: list[dict] = []
    compressible = 0
    for cat in learned["categories"]:
        if not cat["compressible"] or not cat["fold"] or not cat["sample_vec"]:
            continue
        compressible += 1
        fold = cat["fold"]
        # Drive the REAL Form recipe on this category's representative vector.
        coeffs = [int(round(c)) for c in fold["coeffs"]] if fold["integer_coeffs"] else fold["coeffs"]
        kernel_proof = None
        if fold["integer_coeffs"]:
            kernel_proof = drive_form_fold(cat["sample_vec"], fold["idx"], coeffs)
        redundant_dims = {rd["dim"] for rd in cat["redundant"]}
        non_redundant = [d for d in _MEMORY_DIMS if d not in redundant_dims]
        proofs.append(
            {
                "blueprint": cat["blueprint"],
                "rows": cat["rows"],
                "n_dims": cat["n_dims"],
                "fold_idx": fold["idx"],
                "fold_dim": fold["dim"],
                "non_redundant": non_redundant,
                "residual": fold["residual"],
                "coeffs": fold["coeffs"],
                "integer_coeffs": fold["integer_coeffs"],
                "sample_vec": cat["sample_vec"],
                "kernel_proof": kernel_proof,
                # Structural shrink: each of `rows` row-vectors goes N -> N-1.
                "shrink": {
                    "before_dims": cat["n_dims"],
                    "after_dims": cat["n_dims"] - 1,
                    "rows": cat["rows"],
                    "scalars_before": cat["n_dims"] * cat["rows"],
                    "scalars_after": (cat["n_dims"] - 1) * cat["rows"],
                },
            }
        )

    return {
        "runs": len(run_ids),
        "rows": len(rows),
        "learned": learned,
        "proofs": proofs,
        "compressible_count": compressible,
        "incompressible_count": len(learned["categories"]) - compressible,
    }


def render_compress_memory(result: dict, top: int | None) -> str:
    """Render the learn-and-fold report — the autoencoder loop, closed."""
    out: list[str] = []
    out.append("# Kernel memory compression — LEARN the redundant axis, then FOLD it")
    out.append("")
    out.append(
        f"Read {result['rows']} edge-event rows across {result['runs']} recorded "
        f"run(s); grouped by Blueprint NodeID (the content-addressed category)."
    )
    out.append(
        "  Per category the memory is a matrix: one row per edge-event, columns"
    )
    out.append(
        f"  the numeric dimensions {result['learned']['dims']}."
    )
    out.append(
        "  A dimension is REDUNDANT iff it is linearly predictable from the"
    )
    out.append(
        f"  others with max-abs residual ≤ {result['learned']['tolerance']:g}"
    )
    out.append(
        "  (exact linear redundancy — a constant column or a literal linear"
    )
    out.append(
        "  combination, never a noisy fit). The learner solves no-intercept"
    )
    out.append(
        "  least-squares per candidate dimension; the residual is the honest"
    )
    out.append("  redundancy measure. Learning runs in PYTHON.")
    out.append("")
    out.append(
        f"  Compressible categories: {result['compressible_count']}   "
        f"NOT compressible: {result['incompressible_count']}"
    )
    out.append("")

    # The compressible categories — folded, with the kernel-driven round-trip.
    out.append("## Compressible categories — folded N → N−1, round-trip proven")
    out.append("")
    if not result["proofs"]:
        out.append("  (no category had a redundant dimension — nothing folded)")
    for p in result["proofs"]:
        out.append(
            f"  · {p['blueprint']}  ({p['rows']} rows, {p['n_dims']} dims)"
        )
        out.append(
            f"      LEARNED redundant dim: [{p['fold_idx']}] {p['fold_dim']}  "
            f"(residual {p['residual']:.2e})"
        )
        out.append(
            f"      coeffs (predict {p['fold_dim']} from the rest): {p['coeffs']}"
            f"{'  (integer)' if p['integer_coeffs'] else '  (float)'}"
        )
        kp = p["kernel_proof"]
        if kp is not None:
            verdict = "EXACT ✓" if kp["exact"] else "✗ NOT EXACT"
            out.append(
                f"      FORM recipe (kernel-driven): compress({p['sample_vec']}, "
                f"{p['fold_idx']}) → len {kp['folded_len']}; "
                f"reconstruct → {kp['reconstructed']}  [{verdict}]"
            )
            out.append(
                f"      round-trip N→N−1: {kp['n']} → {kp['folded_len']} "
                f"per row — the dropped {p['fold_dim']} re-derived exactly."
            )
        else:
            out.append(
                "      FORM recipe NOT driven (kernel/grammar unavailable, or "
                "float coeffs) — redundancy LEARNED in Python, fold not "
                "kernel-proven this run."
            )
        # The honest per-category NEGATIVE on real data: the dimension(s) that
        # were NOT redundant — the surprising axes the learner REFUSED to fold.
        out.append(
            f"      NOT folded (carries surprise, residual > tol): "
            f"{', '.join(p['non_redundant']) or '(none)'} — folding these would "
            "LOSE information; honestly left."
        )
        sh = p["shrink"]
        out.append(
            f"      structural shrink: {sh['rows']} rows × "
            f"{sh['before_dims']} dims = {sh['scalars_before']} scalars  →  "
            f"{sh['rows']} × {sh['after_dims']} = {sh['scalars_after']} scalars "
            f"(−{sh['rows']} per fold, lossless)."
        )
        out.append("")

    # The honest negative — categories where nothing was redundant.
    out.append("## NOT compressible — every dimension carries surprise")
    out.append("")
    any_incompressible = False
    for cat in result["learned"]["categories"]:
        if cat["compressible"]:
            continue
        any_incompressible = True
        out.append(
            f"  · {cat['blueprint']}  ({cat['rows']} rows) — no dimension is "
            "linearly predictable within tolerance; folding any would LOSE"
        )
        out.append(
            "    information. Honestly left at full size."
        )
    if not any_incompressible:
        out.append(
            "  No category was incompressible — and that is the HONEST structural"
        )
        out.append(
            "  truth, not a gap: a category is content-addressed by its Blueprint"
        )
        out.append(
            "  NodeID, so its four structural columns (pkg, level, type, inst) are"
        )
        out.append(
            "  CONSTANT across the category's rows — constant ⇒ trivially"
        )
        out.append(
            "  redundant ⇒ always at least one foldable dimension. The genuine"
        )
        out.append(
            "  NON-redundant axis on real data is fire_count (the one that VARIES"
        )
        out.append(
            "  and carries surprise — the same axis the surprise-gate keys on);"
        )
        out.append(
            "  the learner refuses to fold it in every category above. A wholly-"
        )
        out.append(
            "  incompressible category (ALL dims surprising) is reachable by"
        )
        out.append(
            "  construction (a full-rank matrix with no linear dependence) but"
        )
        out.append(
            "  does not arise under content-addressing — so the negative shows"
        )
        out.append(
            "  here at the DIMENSION level (fire_count, never folded), not the"
        )
        out.append("  category level.")
    out.append("")

    out.append("## What ran where, and what stays named")
    out.append("")
    out.append(
        "  LEARNING (which dim is redundant + the coeffs): PYTHON least-squares"
    )
    out.append(
        "  over the accumulated rows. APPLY + ROUND-TRIP PROOF: the REAL Form"
    )
    out.append(
        "  compress/reconstruct recipe (grammars/compression-fold.fk) driven"
    )
    out.append(
        "  through the kernel on each compressible category's representative"
    )
    out.append(
        "  integer vector — the fold is Form-native, not a Python trick."
    )
    out.append("")
    out.append(
        "  Still named (not built here): non-linear redundancy (only exact"
    )
    out.append(
        "  LINEAR redundancy is detected); online/continuous learning (this is"
    )
    out.append(
        "  an offline batch over the persisted store); a per-category LEARNED"
    )
    out.append(
        "  retention threshold over time; and recording on the LIVE"
    )
    out.append(
        "  serve_via_kernel request path (this reads the OFFLINE store only)."
    )
    out.append("")
    return "\n".join(out)


def render_accumulated(acc: dict, top: int | None) -> str:
    """Render the accumulated-memory projection — the memory the body kept."""
    out: list[str] = []
    out.append("# Kernel attribution — ACCUMULATED edge-event memory")
    out.append("")
    out.append(
        f"Read {acc['rows']} edge-event rows across {acc['runs']} recorded run(s) "
        f"from the persisted store."
    )
    out.append(
        "  Each row is (route, native, Blueprint NodeID, fire_count) — the trace"
    )
    out.append(
        "  recorded as an edge-event (lc-the-trace-is-the-memory, moves 1-2). The"
    )
    out.append(
        "  projection below reads the ACCUMULATED fire-counts, not one snapshot:"
    )
    out.append(
        "  fire-counts grow run over run, and the center reflects history."
    )
    out.append("")
    emb = acc.get("embodiment") or {}
    if emb.get("categories"):
        center = emb["center"]
        center_str = ".".join(f"{c:g}" for c in center)
        out.append(
            f"  Embodied center (activity-weighted NodeID centroid of "
            f"{emb['total_fires']} ACCUMULATED fires): @{center_str}"
        )
        out.append("")
        out.append("    proj  fires  share  Blueprint    natives")
        for c in _ranked_categories(emb["categories"], top):
            members = ", ".join(c["natives"])
            out.append(
                f"    {c['projection']:>6.3f}  {c['fires']:>4}  {c['share']:>5.3f}  "
                f"{c['blueprint']:<11}  {members}"
            )
    else:
        out.append("  (no resolvable Blueprint NodeIDs in the accumulated memory)")
    out.append("")
    out.append(
        "  This is the snapshot->memory transition, bounded to the OFFLINE"
    )
    out.append(
        "  attribution path. Recording on the LIVE serve_via_kernel request path"
    )
    out.append(
        "  (async/sampled/opt-in, to protect the sub-100µs profile) is the named"
    )
    out.append("  larger build — a separate Urs-level decision, not done here.")
    out.append("")
    return "\n".join(out)


def _ranked(counts: dict, top: int | None) -> list[tuple]:
    items = sorted(counts.items(), key=lambda kv: (-_count_of(kv[1]), kv[0]))
    return items[:top] if top else items


def _count_of(value) -> int:
    return value["count"] if isinstance(value, dict) else int(value)


def _ranked_categories(categories: list[dict], top: int | None) -> list[dict]:
    """Embodiment categories are pre-sorted by projection; apply --top only."""
    return categories[:top] if top else categories


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

    # Embodiment projection — lc-the-trace-is-the-memory, move (3).
    emb = report.get("embodiment") or {}
    out.append("## Embodiment projection (|projection| → 0 = the body's lived center)")
    out.append("")
    if emb.get("categories"):
        center = emb["center"]
        center_str = ".".join(f"{c:g}" for c in center)
        out.append(
            f"  Embodied center (activity-weighted NodeID centroid of {emb['total_fires']} "
            f"fires): @{center_str}"
        )
        out.append(
            "  Each fired Blueprint NodeID category projected to its Manhattan"
        )
        out.append(
            "  distance from that center (the body's own nodeid_distance metric)."
        )
        out.append(
            "  Smaller = nearer the structural center of what actually fires."
        )
        out.append("")
        out.append("    proj  fires  share  Blueprint    natives")
        for c in _ranked_categories(emb["categories"], top):
            members = ", ".join(c["natives"])
            out.append(
                f"    {c['projection']:>6.3f}  {c['fires']:>4}  {c['share']:>5.3f}  "
                f"{c['blueprint']:<11}  {members}"
            )
        out.append("")
        # The inert / undefined-projection class.
        inert_block = report.get("embodiment_inert") or {}
        inert_rows = inert_block.get("inert") or []
        out.append(
            "  Inert categories — never fired, projection UNDEFINED (no edge-events):"
        )
        out.append(
            "  the 'why are you here, not involved?' class. structural-dist is"
        )
        out.append(
            "  context only (how far the never-fired tissue sits), NOT a projection."
        )
        out.append("")
        for r in inert_rows:
            bp = r["blueprint"] or "(no NodeID — no structural position)"
            sd = r["structural_distance"]
            sd_str = f"struct-dist {sd:>6.3f}" if sd is not None else "struct-dist     —"
            out.append(f"    undefined  {sd_str}  {bp:<11}  {r['native']}")
    else:
        out.append(
            "  (no fired Blueprint NodeIDs resolved — projection unavailable)"
        )
    out.append("")
    out.append(
        "  Honest scope: this projects over the CURRENT attribution snapshot"
    )
    out.append(
        "  (per-Blueprint fire counts recomputed this run), not yet the"
    )
    out.append(
        "  persisted edge-event memory the concept names. It measures structural"
    )
    out.append(
        "  distance from the activity-weighted center of what fires — real, but"
    )
    out.append(
        "  a snapshot. The edge-event ledger (accumulating across runs, learning"
    )
    out.append(
        "  value-equivalence from co-firing history) is the named next build."
    )
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
    parser.add_argument(
        "--record",
        action="store_true",
        help=(
            "persist this run's per-route fire-events as edge-events, "
            "SURPRISE-GATED (lc-identity-is-shared-blueprint-and-recipe): only "
            "the surprising tail (projection above the threshold) is written; "
            "the predictable embodied center stays in RAM only. OPT-IN and a "
            f"no-op unless {_EDGE_EVENTS_ENV} is set. The default run (no "
            "--record) writes nothing."
        ),
    )
    parser.add_argument(
        "--surprise-mode",
        default=None,
        help=(
            "how the persistence threshold is resolved from the per-category "
            "projections: mean (default; above-average-surprise tail), median, "
            "fixed:<T> (absolute cutoff), or topk:<K> (the K most-surprising). "
            f"Env {_SURPRISE_MODE_ENV} sets the default; this flag overrides it."
        ),
    )
    parser.add_argument(
        "--record-everything",
        action="store_true",
        help=(
            "opt OUT of the surprise gate and persist EVERY category's "
            "fire-events (the legacy #2341 record-everything behavior). For "
            "debugging / parity baselines only — the gated recorder is default."
        ),
    )
    parser.add_argument(
        "--from-memory",
        action="store_true",
        help=(
            "read the projection over the ACCUMULATED edge-event memory across "
            "all recorded runs (falls back to the live snapshot if none recorded)."
        ),
    )
    parser.add_argument(
        "--compress-memory",
        action="store_true",
        help=(
            "LEARN, per category, which dimension of the accumulated edge-event "
            "memory is redundant (linearly predictable from the others, zero "
            "residual), then APPLY the Form compression-fold (N→N−1) to drop it "
            "— proving the round-trip recovers it EXACTLY on real recorded data "
            "(lc-identity-is-shared-blueprint-and-recipe, the learning half). "
            "OFFLINE: reads the persisted store, no hot path. No-op when no "
            f"memory recorded ({_EDGE_EVENTS_ENV} unset / empty)."
        ),
    )
    args = parser.parse_args(argv)

    store_path = edge_events_path()

    # --compress-memory: the autoencoder loop closed — learn the redundant axis
    # per category over the accumulated memory, then fold it via the real Form
    # recipe. OFFLINE, opt-in, no-op when no memory recorded.
    if args.compress_memory:
        result = compress_memory(store_path) if store_path is not None else None
        if result is not None:
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(render_compress_memory(result, args.top))
            return 0
        note = (
            "(no accumulated edge-event memory to compress"
            + (
                f" at {store_path} — record runs with --record first)"
                if store_path is not None
                else f" — set {_EDGE_EVENTS_ENV} and record runs with --record first)"
            )
        )
        print(note)
        return 0

    # --from-memory: read the accumulated memory and project over it. Honest
    # fallback: if no memory recorded yet, say so and fall through to the
    # snapshot so the command always returns a useful projection.
    if args.from_memory:
        acc = accumulated_report(store_path) if store_path is not None else None
        if acc is not None:
            if args.json:
                print(json.dumps(acc, indent=2))
            else:
                print(render_accumulated(acc, args.top))
            return 0
        note = (
            "(no accumulated edge-event memory yet"
            + (
                f" at {store_path} — record runs with --record first;"
                if store_path is not None
                else f" — set {_EDGE_EVENTS_ENV} and record runs with --record first;"
            )
            + " showing the live snapshot instead)"
        )
        print(note)
        print("")
        # fall through to the snapshot path below

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

    report = aggregate(collect_edges=args.record)

    if args.record:
        if store_path is None:
            # Gated no-op, like runtime_event_store.enabled() == False. Named,
            # not silent — so an operator knows recording was requested but the
            # store is unconfigured.
            note = (
                f"(--record requested but {_EDGE_EVENTS_ENV} is unset — "
                "no edge-events written; set it to a writable path to accumulate)"
            )
            if not args.json:
                print(note)
        else:
            mode = (
                args.surprise_mode
                or os.environ.get(_SURPRISE_MODE_ENV, "").strip()
                or _DEFAULT_SURPRISE_MODE
            )
            gated = not args.record_everything
            result = record_edge_events(
                report, store_path, surprise_gated=gated, mode=mode
            )
            if not args.json:
                if gated:
                    surprising = result["surprising"]
                    predictable = result["predictable"]
                    print(
                        f"(SURPRISE-GATED record → {store_path})"
                    )
                    print(
                        f"  threshold: projection > {result['threshold']:g} "
                        f"(mode: {result['mode']}) — the above-surprise tail"
                    )
                    print(
                        f"  persisted {result['written']} edge-event row(s) from "
                        f"{len(surprising)} SURPRISING categor"
                        f"{'y' if len(surprising) == 1 else 'ies'} "
                        "(far from the embodied center):"
                    )
                    for c in result["surprising_full"]:
                        print(
                            f"    proj {c['projection']:>7.3f}  {c['blueprint']:<11}  "
                            f"{', '.join(c['natives'])}"
                        )
                    print(
                        f"  kept {result['skipped']} row(s) from "
                        f"{len(predictable)} PREDICTABLE categor"
                        f"{'y' if len(predictable) == 1 else 'ies'} in RAM ONLY "
                        "(near the embodied center, not persisted):"
                    )
                    for c in result["predictable_full"]:
                        print(
                            f"    proj {c['projection']:>7.3f}  {c['blueprint']:<11}  "
                            f"{', '.join(c['natives'])}"
                        )
                    print(
                        "  the body sees what it keeps and what it lets go — "
                        "--from-memory reads the accumulation."
                    )
                else:
                    print(
                        f"(record-EVERYTHING (gate off) → recorded "
                        f"{result['written']} edge-event rows to {store_path}; "
                        "legacy #2341 behavior, no surprise gate)"
                    )
        # Don't leak the recording-only key into --json output.
        report.pop("per_route_natives", None)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
