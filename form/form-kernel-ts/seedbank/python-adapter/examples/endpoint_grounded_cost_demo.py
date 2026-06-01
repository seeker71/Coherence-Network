# endpoint_grounded_cost_demo.py — the GROUNDED-COST REDUCTION of
# grounded_idea_metrics_service.compute_idea_metrics, transmuted to a Form
# recipe. This is the richest deferred slice falling piece by piece now that
# polymorphic structure-access (record_get), the float-field fold, and per-record
# arithmetic are all banked three-way.
#
# THE HONEST DECOMPOSITION. compute_idea_metrics takes SIX pre-fetched
# collections, FILTERS each by idea_id (_filter_by_idea_id / _filter_commits_by_idea),
# and computes many outputs. Filtering is cheap host-side collection-narrowing —
# a separate capability, not a kernel computation — and the host already does it
# before this point. What stays is the NUMERIC REDUCTION over the
# already-relevant records; THAT is what runs kernel-side here:
#   spec_actual_cost_sum    = sum(s["actual_cost"]    for s in specs)
#   spec_estimated_cost_sum = sum(s["estimated_cost"] for s in specs)
#   runtime_cost            = the single runtime_cost_estimate (None→0.0 host-side)
#   commit_cost_sum         = sum(clamp(0.10 + files*0.15 + lines*0.002, 0.05, 10.0)
#                                 for c in commits)
#   lineage_estimated_cost  = sum(l["estimated_cost"] for l in links)
#   computed_actual_cost    = spec_actual_cost_sum + runtime_cost + commit_cost_sum
# The seam: the filtering/fetching and the six-collection join are host
# orchestration; the cost reduction is the kernel computation. The function's
# "deep gate" was never a missing kernel capability — it is host orchestration
# AROUND now-kernel-served reductions.
#
# Banked capabilities this folds together:
#   - float-field fold over a list of records (spec_actual_cost_sum) — the
#     float-add sibling-parity fix (PR #2330)
#   - per-record arithmetic fold (commit_cost_sum) — record_get on int fields,
#     int*float promotion, and a MIN/MAX clamp expressed as max2/min2 branches
#     (the same comparison-branch shape grounded_roi's max2 proves three-way)
#   - single-record field read with a host None-guard (runtime_cost)
#
# The commit formula matches _estimate_commit_cost_sum EXACTLY, including the
# per-commit clamp: BASE_COST=0.10, PER_FILE=0.15, PER_LINE=0.002,
# MIN_COST=0.05, MAX_COST=10.0; cost = max(MIN_COST, min(MAX_COST, base+files*PER_FILE+lines*PER_LINE)).
#
# How the lists travel in: the bridge marshals each input list[dict|model] to a
# kernel list-of-records (_dict_new literal / py_to_value Record per element);
# the recipe iterates via the head/tail fold the python-adapter lowers
# `for r in xs` into. (Go has no _dict_*, so this adapter path is Rust+TS like
# the prior list-of-record routes; the kernel-level three-way clamp + fold is
# proven over record_new in grounded-cost-reduction-band.fk.)
#
# Three-way clean on VALUE and PRINT: the frozen sample is chosen so all six
# outputs are NON-integer floats, which every kernel formats identically:
#   spec_actual_cost_sum    = 3.5 + 1.25            = 4.75
#   spec_estimated_cost_sum = 4.25 + 2.5            = 6.75
#   runtime_cost                                     = 2.25
#   commit_cost_sum         = clamp(0.10+3*0.15+100*0.002) = 0.75
#   lineage_estimated_cost  = 5.25 + 1.5            = 6.75
#   computed_actual_cost    = 4.75 + 2.25 + 0.75    = 7.75
# The final list is [4.75, 6.75, 2.25, 0.75, 6.75, 7.75]. No integer-valued
# float crosses the print boundary named in float-natives-band.fk §print.


def min2(a, b):
    if a > b:
        return b
    return a


def max2(a, b):
    if a > b:
        return a
    return b


def sum_actual_cost(specs):
    total = 0.0
    for s in specs:
        total = total + s["actual_cost"]
    return total


def sum_estimated_cost(specs):
    total = 0.0
    for s in specs:
        total = total + s["estimated_cost"]
    return total


def commit_cost(c):
    base = 0.10 + c["change_files"] * 0.15 + c["lines_added"] * 0.002
    return max2(0.05, min2(10.0, base))


def sum_commit_cost(commits):
    total = 0.0
    for c in commits:
        total = total + commit_cost(c)
    return total


def sum_lineage_cost(links):
    total = 0.0
    for l in links:
        total = total + l["estimated_cost"]
    return total


def grounded_cost(specs, commits, links, runtime_cost):
    spec_actual_cost_sum = sum_actual_cost(specs)
    spec_estimated_cost_sum = sum_estimated_cost(specs)
    commit_cost_sum = sum_commit_cost(commits)
    lineage_estimated_cost = sum_lineage_cost(links)
    computed_actual_cost = spec_actual_cost_sum + runtime_cost + commit_cost_sum
    return [
        spec_actual_cost_sum,
        spec_estimated_cost_sum,
        runtime_cost,
        commit_cost_sum,
        lineage_estimated_cost,
        computed_actual_cost,
    ]


# Endpoint's frozen sample input — already-filtered records for one idea.
specs = [
    {"actual_cost": 3.5, "estimated_cost": 4.25},
    {"actual_cost": 1.25, "estimated_cost": 2.5},
]
commits = [
    {"change_files": 3, "lines_added": 100},
]
links = [
    {"estimated_cost": 5.25},
    {"estimated_cost": 1.5},
]
runtime_cost = 2.25

grounded_cost(specs, commits, links, runtime_cost)
