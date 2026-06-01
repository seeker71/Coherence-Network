# endpoint_idea_grounding_summary_demo.py — REDUCING OVER A LIST OF RECORDS,
# the gate-#1 capability the API_KERNEL_READINESS ledger names. Every prior
# structure-access route read fields from ONE record (the marginal-CC core);
# this is the FIRST kernel-served route to receive a LIST of records and FOLD a
# field across it.
#
# The honest subset of grounded_idea_metrics_service.compute_idea_metrics: its
# confidence/grounding signals reduce over the pre-fetched per-idea collections
# —
#   spec_count                = len(idea_specs)
#   total_event_count         = sum(s["event_count"] for s in idea_specs)
#   specs_with_value_count    = count(s for s in idea_specs if s["actual_value"] > 0)
#   max_event_count           = max(s["event_count"] for s in idea_specs)
# These are the INTEGER reductions the full function builds has_specs_with_data
# / runtime coverage from. The FILTERING (`_filter_by_idea_id`) is the host's
# job — an I/O-adjacent join the route does before handing the recipe the
# already-per-idea list; the kernel does the REDUCTION. The full
# compute_idea_metrics also folds FLOAT fields (spec_actual_cost_sum) and reads
# six heterogeneous object-OR-dict collections — those stay CPython (the
# float-field fold is Rust-carrier-exact but TS-i32-blocked, and the
# heterogeneous-collection join is a separate gate; both named in the ledger).
#
# How the list travels into the recipe: the route's bindings carry one `specs`
# list of dicts. form_kernel_bridge marshals it to a kernel list-of-records —
# `_fk_literal` renders each element as `(record_new ...)` (subprocess path) and
# lib.rs `py_to_value` marshals each dict to a `Value::Record` (inline path),
# the list arm recursing element-wise. The recipe iterates via the head/tail
# fold the python-adapter lowers `for s in specs` into and reads each field via
# the kernel's record accessor.
#
# Three-way clean: every reduction here is over an INTEGER field (or a
# float-field PREDICATE, never a float SUM), so the result is an integer that
# prints identically across CPython / Rust / TS. The recipe returns a LIST of
# the four integer signals in struct order; the route assembles the named
# response from the positional list (same list-returning shape as cost_vector).


def spec_count(specs):
    n = 0
    for s in specs:
        n = n + 1
    return n


def total_event_count(specs):
    total = 0
    for s in specs:
        total = total + s["event_count"]
    return total


def specs_with_value_count(specs):
    c = 0
    for s in specs:
        if s["actual_value"] > 0:
            c = c + 1
    return c


def max_event_count(specs):
    mx = 0
    for s in specs:
        if s["event_count"] > mx:
            mx = s["event_count"]
    return mx


def grounding_summary(specs):
    return [
        spec_count(specs),
        total_event_count(specs),
        specs_with_value_count(specs),
        max_event_count(specs),
    ]


# Endpoint's frozen sample input — three spec records for one idea. spec_count
# = 3; total_event_count = 3 + 0 + 7 = 10; specs_with_value_count = 2 (the first
# and third carry actual_value > 0); max_event_count = max(3, 0, 7) = 7. The
# final list is [3, 10, 2, 7].
specs = [
    {"event_count": 3, "actual_value": 1.5},
    {"event_count": 0, "actual_value": 0.0},
    {"event_count": 7, "actual_value": 2.25},
]

grounding_summary(specs)
