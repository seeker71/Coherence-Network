# endpoint_grounded_roi_demo.py — the grounded-ROI scalar core of
# idea_scoring._with_score, captured as pure Python and compiled to a Form
# recipe.
#
# Grounded ROI: given an idea's estimated/actual cost and potential/actual
# value, compute the three CC scalars _with_score attaches to IdeaWithScore:
#   value_gap          = max(potential_value - actual_value, 0.0)
#   remaining_cost_cc  = round(max(estimated_cost - actual_cost, 0.0), 4)
#   value_gap_cc       = round(value_gap, 4)
#   roi_cc             = round(value_gap_cc / remaining_cost_cc, 4)
#                          if remaining_cost_cc > 0 else 0.0
#
# This route folds three prior unlocks into one shape:
#   - the two-argument `max` expressed as a comparison (the kernel's `max`
#     native floors floats; an `if a > b` branch is float-correct and
#     value-identical), exactly as idea_score / marginal_cc_return do;
#   - the round_ndigits native (PR #2320) lowering Python's two-arg
#     round(x, 4) to CPython-exact half-to-even rounding;
#   - a guarded division — the `if remaining_cost_cc > 0 else 0.0` ternary
#     is a conditional in the recipe, never dividing by zero.
#
# The `(estimated_cost or 0.0)` / `(actual_cost or 0.0)` falsy-coalescing in
# _with_score is a host concern (the FastAPI route coalesces before the
# recipe runs); this is the pure math after it, over already-float scalars.
#
# The result is a LIST of the three components in struct order —
# [remaining_cost_cc, value_gap_cc, roi_cc] — and the FastAPI route assembles
# the named struct from the positional list (same list-returning shape as
# cost_vector / value_vector).


def max2(a, b):
    if a > b:
        return a
    return b


def grounded_roi(estimated_cost, actual_cost, potential_value, actual_value):
    value_gap = max2(potential_value - actual_value, 0.0)
    remaining_cost_cc = round(max2(estimated_cost - actual_cost, 0.0), 4)
    value_gap_cc = round(value_gap, 4)
    roi_cc = round(value_gap_cc / remaining_cost_cc, 4) if remaining_cost_cc > 0 else 0.0
    return [remaining_cost_cc, value_gap_cc, roi_cc]


# Endpoint's frozen sample input — a partially-realized idea: 60 CC estimated,
# 12 spent → 48 remaining; 33.333 potential, 8 captured → 25.333 gap;
# roi = round(25.333 / 48.0, 4) = round(0.52777..., 4) = 0.5278.
estimated_cost = 60.0
actual_cost = 12.0
potential_value = 33.333
actual_value = 8.0

grounded_roi(estimated_cost, actual_cost, potential_value, actual_value)
