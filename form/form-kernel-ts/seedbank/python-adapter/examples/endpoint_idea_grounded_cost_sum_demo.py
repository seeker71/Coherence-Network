# endpoint_idea_grounded_cost_sum_demo.py — SUMMING A FLOAT FIELD over a LIST
# OF RECORDS. This is the capability the list-of-record-reduction wave named as
# deferred: the integer-field fold shipped three-way, but folding a FLOAT field
# (`sum(s["actual_cost"] for s in specs)`) was blocked because the TS kernel's
# `add`/`_plus` were i32-only — float operands threw on the MATH walker arm and
# on the `_plus` native. With the float-add sibling-parity fix (the bare-width
# MATH arm now promotes to f64 at runtime, and `_plus` gained the float arms),
# the float-field fold is sibling-portable: CPython == Rust == Go == TS.
#
# This is the float half of grounded_idea_metrics_service.compute_idea_metrics'
# cost/value reductions — `spec_actual_cost_sum` and `spec_actual_value_sum`
# fold the per-spec float cost/value across one idea's pre-fetched specs. The
# integer signals shipped in endpoint_idea_grounding_summary_demo; this is the
# float-field-sum companion the ledger named as the next gate.
#
# The seed accumulator is 0.0 (a float), so every `total = total + s[field]`
# walks (float, float) and stays a float through to the result. The route folds
# BOTH float fields (actual_cost and actual_value) and returns the pair so a
# single recipe proves the float-field reduction over two parallel fields.
#
# How the list travels in: identical to the integer route — the bridge marshals
# the input list[dict|model] to a kernel list-of-records (`record_new` literal /
# py_to_value Record per element), and the recipe iterates via the head/tail
# fold the python-adapter lowers `for s in specs` into.
#
# Three-way clean on VALUE: the sample sums land on non-integer floats (cost =
# 3.5 + 1.25 + 0.5 = 5.25; value = 1.5 + 0.0 + 2.25 = 3.75), which print
# identically across all kernels. (An integer-valued float result — e.g. 5.0 —
# would print `5.0` on Rust but `5` on Go/TS; that residual print-layer
# divergence is named in float-natives-band.fk, and the sample avoids it.)


def total_actual_cost(specs):
    total = 0.0
    for s in specs:
        total = total + s["actual_cost"]
    return total


def total_actual_value(specs):
    total = 0.0
    for s in specs:
        total = total + s["actual_value"]
    return total


def grounded_cost_sum(specs):
    return [
        total_actual_cost(specs),
        total_actual_value(specs),
    ]


# Endpoint's frozen sample input — three spec records for one idea.
# total_actual_cost  = 3.5 + 1.25 + 0.5  = 5.25
# total_actual_value = 1.5 + 0.0  + 2.25 = 3.75
# The final list is [5.25, 3.75].
specs = [
    {"actual_cost": 3.5, "actual_value": 1.5},
    {"actual_cost": 1.25, "actual_value": 0.0},
    {"actual_cost": 0.5, "actual_value": 2.25},
]

grounded_cost_sum(specs)
