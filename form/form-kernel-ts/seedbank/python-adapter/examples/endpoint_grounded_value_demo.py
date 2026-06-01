# endpoint_grounded_value_demo.py — the VALUE / REALIZATION / CONFIDENCE
# REDUCTION of grounded_idea_metrics_service.compute_idea_metrics, transmuted to
# a Form recipe. With the grounded-COST reduction already serving kernel-side
# (endpoint_grounded_cost_demo.fk, PR #2331), this is the second and final
# numeric slice of compute_idea_metrics — once it serves, the function's whole
# COMPUTATION is kernel-native; only host orchestration (filtering + the
# boolean-presence derivations) remains host-side BY DESIGN.
#
# THE HONEST DECOMPOSITION. compute_idea_metrics derives, per already-filtered
# idea, three families of fact:
#   (a) NUMERIC REDUCTIONS — max-of-signals, a guarded ratio with a min-clamp,
#       a count→level arithmetic (min(1.0, count/N)), a weighted sum, a
#       [0.05, 0.95] clamp. These are pure arithmetic the kernel computes.
#   (b) BOOLEAN / PRESENCE LEVELS — has_specs_with_data, has_lineage,
#       has_friction. Each is an any(...)-over-records boolean-OR fold or a
#       len>0 presence ladder resolving to a 3-level {1.0, 0.5/0.3, 0.0} value.
#       Booleans-over-collections is the deferred filtering-adjacent capability;
#       the host derives these and passes the resolved level in.
#   (c) the FILTERING of the six collections by idea_id — cheap host-side
#       collection-narrowing, a separate capability the host already does.
#
# This recipe runs (a). It takes the host-derived scalar inputs:
#   value candidates    — lineage_measured_value, usage_revenue (=event_count *
#                         _REVENUE_PER_REQUEST, resolved host-side),
#                         spec_actual_value_sum
#   cost candidates      — spec_estimated_cost_sum, lineage_estimated_cost
#   potential            — spec_potential_value_sum (the realization denominator)
#   raw counts           — runtime_event_count, commit_count (the kernel runs the
#                         min(1.0, count/N) threshold arithmetic + the zero-guard)
#   resolved levels      — has_specs_with_data, has_lineage, has_friction (the
#                         boolean/presence ladders the host derived)
# and computes EXACTLY what compute_idea_metrics computes (verified against the
# source lines, constants, and clamps):
#   computed_actual_value   = max(lineage_measured_value, usage_revenue,
#                                 spec_actual_value_sum)
#   computed_estimated_cost = max(spec_estimated_cost_sum, lineage_estimated_cost)
#   value_realization_pct   = min(computed_actual_value / spec_potential_value_sum,
#                                 1.0) if spec_potential_value_sum > 0 else 0.0
#   has_runtime_data        = min(1.0, runtime_event_count / 10.0)
#                                 if runtime_event_count > 0 else 0.0
#   has_commits             = min(1.0, commit_count / 5.0) if commit_count > 0
#                                 else 0.0
#   computed_confidence     = clamp(
#       has_specs_with_data * 0.30 + has_runtime_data * 0.25
#       + has_lineage * 0.25 + has_commits * 0.10 + has_friction * 0.10,
#       0.05, 0.95)
# The weights are _WEIGHT_SPECS=0.30, _WEIGHT_RUNTIME=0.25, _WEIGHT_LINEAGE=0.25,
# _WEIGHT_COMMITS=0.10, _WEIGHT_FRICTION=0.10 — read from the source. The clamp
# is max(0.05, min(0.95, sum)) — never fully certain, never zero. The
# realization guard (spec_potential_value_sum>0) and min(_, 1.0) ceiling are
# verbatim source.
#
# The seam: the kernel keeps the most NUMERIC computation. The host keeps the
# booleans-over-records (the any(...) folds + presence ladders) and the
# collection filtering — both filtering-adjacent capabilities held host-side BY
# DESIGN, not for want of a kernel native. The has_specs_with_data / has_lineage
# / has_friction levels are the precise boolean-OR-over-records sub-gate left
# host-side: each needs an any(s[ac]>0 or s[av]>0) / len>0 ladder; the host
# resolves it to a float and the kernel folds the resolved level.
#
# Banked capabilities this folds together:
#   - max-of-signals as nested max2 comparison-branches (grounded_roi's max2)
#   - a guarded ratio with a min-clamp (the div + `if denom > 0 else 0.0`
#     guard grounded_roi proves, plus a min2 ceiling at 1.0)
#   - count→level threshold arithmetic: min(1.0, count/N) with a zero-guard
#   - a five-term weighted sum and the final [0.05, 0.95] two-sided clamp
#
# Three-way clean on VALUE and PRINT: the frozen sample is chosen so every
# output is a NON-integer float, which every kernel formats identically:
#   lineage_measured_value=12.5, usage_revenue=0.007, spec_actual_value_sum=4.25
#     → computed_actual_value     = max(12.5, 0.007, 4.25)     = 12.5  → 12.5
#   spec_estimated_cost_sum=6.75, lineage_estimated_cost=5.5
#     → computed_estimated_cost   = max(6.75, 5.5)             = 6.75
#   spec_potential_value_sum=20.0
#     → value_realization_pct     = min(12.5 / 20.0, 1.0)      = 0.625
#   runtime_event_count=7
#     → has_runtime_data          = min(1.0, 7/10.0)           = 0.7
#   commit_count=3
#     → has_commits               = min(1.0, 3/5.0)            = 0.6
#   has_specs_with_data=1.0, has_lineage=1.0, has_friction=0.3 (host-resolved)
#     → confidence raw = 1.0*0.30 + 0.7*0.25 + 1.0*0.25 + 0.6*0.10 + 0.3*0.10
#                      = 0.30 + 0.175 + 0.25 + 0.06 + 0.03 = 0.815
#     → computed_confidence       = clamp(0.815, 0.05, 0.95)   = 0.815
# The final list is [12.5, 6.75, 0.625, 0.815]. No integer-valued float crosses
# the print boundary named in float-natives-band.fk §print.


def min2(a, b):
    if a > b:
        return b
    return a


def max2(a, b):
    if a > b:
        return a
    return b


def grounded_value(lineage_measured_value, usage_revenue, spec_actual_value_sum, spec_estimated_cost_sum, lineage_estimated_cost, spec_potential_value_sum, runtime_event_count, commit_count, has_specs_with_data, has_lineage, has_friction):
    computed_actual_value = max2(
        max2(lineage_measured_value, usage_revenue), spec_actual_value_sum
    )
    computed_estimated_cost = max2(spec_estimated_cost_sum, lineage_estimated_cost)
    value_realization_pct = 0.0
    if spec_potential_value_sum > 0:
        value_realization_pct = min2(
            computed_actual_value / spec_potential_value_sum, 1.0
        )
    has_runtime_data = 0.0
    if runtime_event_count > 0:
        has_runtime_data = min2(1.0, runtime_event_count / 10.0)
    has_commits = 0.0
    if commit_count > 0:
        has_commits = min2(1.0, commit_count / 5.0)
    confidence_raw = has_specs_with_data * 0.30 + has_runtime_data * 0.25 + has_lineage * 0.25 + has_commits * 0.10 + has_friction * 0.10
    computed_confidence = max2(0.05, min2(0.95, confidence_raw))
    return [
        computed_actual_value,
        computed_estimated_cost,
        value_realization_pct,
        computed_confidence,
    ]


# Endpoint's frozen sample input — host-derived scalars for one idea.
lineage_measured_value = 12.5
usage_revenue = 0.007
spec_actual_value_sum = 4.25
spec_estimated_cost_sum = 6.75
lineage_estimated_cost = 5.5
spec_potential_value_sum = 20.0
runtime_event_count = 7
commit_count = 3
has_specs_with_data = 1.0
has_lineage = 1.0
has_friction = 0.3

grounded_value(lineage_measured_value, usage_revenue, spec_actual_value_sum, spec_estimated_cost_sum, lineage_estimated_cost, spec_potential_value_sum, runtime_event_count, commit_count, has_specs_with_data, has_lineage, has_friction)
