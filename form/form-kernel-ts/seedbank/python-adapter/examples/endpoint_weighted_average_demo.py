# endpoint_weighted_average_demo.py — the body of /api/utils/weighted_average,
# captured as pure Python and compiled to a Form recipe.
#
# Third endpoint transmuted under the @serve_via_kernel habit. The
# weighted average of a list of coherence-style scores against a list
# of weights is the substrate's bread-and-butter combinator — every
# multi-signal coherence aggregation goes through this shape.
#
# Floats throughout: scores live in [0.0, 1.0]; weights live in [0.0, 1.0]
# and need not sum to 1.0 (the result divides by total weight). Pure
# IEEE 754; the chosen inputs are exact binary fractions so the three
# runtimes' rendered tail values match byte-for-byte.
#
# Three runtimes produce identical results:
#   - CPython
#   - TS evalPython
#   - form-kernel-rust


def dot(values, weights):
    total = 0.0
    i = 0
    n = len(values)
    while i < n:
        total = total + values[i] * weights[i]
        i = i + 1
    return total


def sum_floats(weights):
    total = 0.0
    i = 0
    n = len(weights)
    while i < n:
        total = total + weights[i]
        i = i + 1
    return total


def weighted_average(values, weights):
    numerator = dot(values, weights)
    denominator = sum_floats(weights)
    return numerator / denominator


# Endpoint's frozen sample input — exact in IEEE 754:
#   numerator = 0.5*0.25 + 0.75*0.25 + 1.0*0.5 = 0.125 + 0.1875 + 0.5 = 0.8125
#   denominator = 0.25 + 0.25 + 0.5 = 1.0
#   result = 0.8125
values = [0.5, 0.75, 1.0]
weights = [0.25, 0.25, 0.5]

weighted_average(values, weights)
