# endpoint_idea_score_demo.py — the body of idea_scoring._score, captured as
# pure Python and compiled to a Form recipe.
#
# Free-energy idea score: (potential_value * confidence) / denom, where
# denom = max(estimated_cost + resistance_risk, 0.5). The 0.5 CC floor
# prevents astronomically inflated scores when both cost and risk are near
# zero. It is the substrate's value-per-cost prioritization signal — the
# number select_idea ranks the backlog by.
#
# Pure float arithmetic — multiply, add, divide, and a two-argument max
# expressed as a comparison (the kernel's `max` native floors floats; an
# `if a > b` branch is the float-correct, value-identical form). No
# transcendentals, so the same value renders across all three runtimes:
#   - CPython
#   - TS evalPython
#   - form-kernel-rust
#
# max2(a, b) == max(a, b) for the non-NaN floats this carries: both return
# the larger, and the floor case (a == 0.5 == b) returns 0.5 either way.


def max2(a, b):
    if a > b:
        return a
    return b


def idea_score(potential_value, confidence, estimated_cost, resistance_risk):
    denom = max2(estimated_cost + resistance_risk, 0.5)
    return (potential_value * confidence) / denom


# Endpoint's frozen sample input — a mid-confidence idea with real cost and
# risk: (8.0 * 0.75) / max(2.0 + 1.0, 0.5) = 6.0 / 3.0 = 2.0.
potential_value = 8.0
confidence = 0.75
estimated_cost = 2.0
resistance_risk = 1.0

idea_score(potential_value, confidence, estimated_cost, resistance_risk)
