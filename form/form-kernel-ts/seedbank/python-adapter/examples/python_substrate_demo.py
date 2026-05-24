# python_substrate_demo.py — Python with the same shape as real
# substrate-talking code: helper functions, accumulator loops over
# lists, conditional dispatch by position. Not a toy — exercises
# every Python construct the pipeline supports end-to-end.
#
# Computes a weighted-coherence score over a (cell-id, score) list:
#   - filter pairs below threshold
#   - weight remaining by index-position decay (later items count less)
#   - sum into integer coherence (weights expressed as percent-of-100
#     to stay in integer arithmetic — the kernel's MATH arms are
#     int-only today; float natives are an honest follow-up gap)
#
# Runs identically across CPython, TS evalPython, and form-kernel-rust.

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

values = [85, 42, 99, 60, 30, 75, 88, 50]
threshold = 50

above = count_above(values, threshold)
coherence = coherence_score(values, threshold)

above * 100 + coherence
