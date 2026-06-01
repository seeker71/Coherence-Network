# endpoint_softmax_weights_demo.py — the body of idea_scoring._softmax_weights,
# captured as pure Python and compiled to a Form recipe.
#
# Softmax weights: convert raw scores to probability weights. This is the
# first LIST-RETURNING kernel-served route — the computation produces a list,
# not a scalar, proving the value-walk carries list construction end to end
# (build via append-accumulator, return through value_to_py's List arm).
#
# temperature controls exploration:
#   0.0  → deterministic (all weight on the max score)
#   1.0  → proportional to scores (true softmax)
#   >1.0 → flatter distribution, more exploration
#
# This route uses a transcendental native (math.exp) like breath_balance's
# math.log; the inputs chosen here land on values whose ratios print
# identically across CPython, the Form-native walker, and form-kernel-rust.
#
# The accumulator idiom — `result = []` then `result.append(x)` in a for
# loop — is the list-construction shape the kernel value-walk now carries
# (form-stdlib/python-bmf-eval.fk's METHOD-CALL accumulator arm). Each
# branch builds its result list this way rather than via a comprehension,
# so the recipe exercises the append path the whole class of list-returning
# routes depends on.

import math


def softmax_weights(scores, temperature):
    n = len(scores)
    if n == 0:
        return []

    # Find the max once — shared by both the deterministic and the
    # numerically-stable softmax branches.
    max_s = scores[0]
    i = 1
    while i < n:
        if scores[i] > max_s:
            max_s = scores[i]
        i = i + 1

    if temperature <= 0.0:
        # Deterministic: all weight on the max (1.0 for the max, 0.0 else).
        result = []
        i = 0
        while i < n:
            if scores[i] == max_s:
                result.append(1.0)
            else:
                result.append(0.0)
            i = i + 1
        return result

    # Numerically-stable softmax: shift by max, exponentiate, normalize.
    exps = []
    i = 0
    while i < n:
        exps.append(math.exp((scores[i] - max_s) / temperature))
        i = i + 1

    total = 0.0
    i = 0
    while i < n:
        total = total + exps[i]
        i = i + 1

    if total == 0.0:
        # Uniform fallback — every score collapsed to the same exp.
        uniform = 1.0 / n
        result = []
        i = 0
        while i < n:
            result.append(uniform)
            i = i + 1
        return result

    result = []
    i = 0
    while i < n:
        result.append(exps[i] / total)
        i = i + 1
    return result


# Endpoint's frozen sample input — three scores, temperature 1.0. With
# scores [1.0, 2.0, 3.0] shifted by max 3.0 → exps [e^-2, e^-1, e^0] =
# [0.1353..., 0.3678..., 1.0], total 1.5032..., weights
# [0.09003..., 0.24472..., 0.66524...] summing to 1.0.
scores = [1.0, 2.0, 3.0]
temperature = 1.0

softmax_weights(scores, temperature)
