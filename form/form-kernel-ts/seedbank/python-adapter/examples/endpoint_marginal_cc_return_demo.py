# endpoint_marginal_cc_return_demo.py — the body of
# idea_scoring._marginal_cc_return, captured as pure Python and compiled to
# a Form recipe.
#
# Method B prioritization: marginal CC return = (value_gap * conf^2) /
# (remaining_cost + rr * 0.5), where value_gap = max(pv - av, 0.0) and
# remaining_cost = max(ec - ac, 0.1). It prioritizes UNCAPTURED value per
# remaining CC — confidence enters squared so low-confidence ideas are
# discounted twice. The substrate's "what still has the most to give per
# CC left to spend" ranking.
#
# Pure float arithmetic — subtract, multiply, add, divide, and two
# two-argument maxes expressed as comparisons (the kernel's `max` native
# floors floats; an `if a > b` branch is the float-correct, value-identical
# form). No transcendentals, so the same value renders across all three
# runtimes:
#   - CPython
#   - kernel-bmf-run
#   - form-kernel-rust
#
# The 0.0 / 0.1 floors clamp negative gaps and tiny remaining costs; max2
# returns the larger and matches Python's max on every non-NaN input here.


def max2(a, b):
    if a > b:
        return a
    return b


def marginal_cc_return(pv, av, conf, ec, ac, rr):
    value_gap = max2(pv - av, 0.0)
    remaining_cost = max2(ec - ac, 0.1)
    return (value_gap * conf * conf) / (remaining_cost + rr * 0.5)


# Endpoint's frozen sample input — an idea with half its value still
# uncaptured at solid confidence:
#   value_gap = max(8.0 - 3.0, 0.0) = 5.0
#   remaining_cost = max(4.0 - 1.0, 0.1) = 3.0
#   result = (5.0 * 0.8 * 0.8) / (3.0 + 2.0 * 0.5) = 3.2 / 4.0 = 0.8
pv = 8.0
av = 3.0
conf = 0.8
ec = 4.0
ac = 1.0
rr = 2.0

marginal_cc_return(pv, av, conf, ec, ac, rr)
