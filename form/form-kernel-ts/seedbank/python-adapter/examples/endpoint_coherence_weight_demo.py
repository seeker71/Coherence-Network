# endpoint_coherence_weight_demo.py — the body of a FastAPI endpoint,
# captured as pure Python and compiled to a Form recipe.
#
# This file is the proof-of-shape for the question Urs named:
# "can we replace FastAPI with native Form kernel" — the first transmutation
# gesture. The endpoint /api/utils/coherence_weight in api/app/routers/utils.py
# now runs this exact computation through form-kernel-rust instead of
# executing Python inline. FastAPI stays as the HTTP doorway; the body
# is a Form recipe.
#
# What the endpoint does: given a list of integer values and a threshold,
# compute a weighted coherence score where each above-threshold value
# contributes with a position-based decay (first counts 100×, second 50×,
# third 25×, rest 10×) plus a bonus of 100× the count of above-threshold
# entries. Same shape as python_substrate_demo.py — distinct values so
# it's its own parity-suite entry.
#
# Three runtimes produce identical results:
#   - CPython (the FastAPI shim still calls this on the parity_suite path)
#   - TS evalPython (the bootstrap evaluator)
#   - form-kernel-rust (what the live endpoint actually shells into)


def weighted_score(value, position):
    if position == 0:
        return value * 100
    if position == 1:
        return value * 50
    if position == 2:
        return value * 25
    return value * 10


def coherence_score(values, threshold):
    total = 0
    position = 0
    for v in values:
        if v >= threshold:
            total = total + weighted_score(v, position)
            position = position + 1
    return total


def count_above(values, threshold):
    n = 0
    for v in values:
        if v >= threshold:
            n = n + 1
    return n


def coherence_weight(values, threshold):
    above = count_above(values, threshold)
    coherence = coherence_score(values, threshold)
    return above * 100 + coherence


# Endpoint's frozen sample input — the parity_suite tail expression is
# the value the FastAPI route returns for this exact input. Distinct
# from python_substrate_demo.py: more values, different threshold.
values = [72, 38, 91, 55, 28, 67, 84, 45, 95, 12]
threshold = 50

coherence_weight(values, threshold)
