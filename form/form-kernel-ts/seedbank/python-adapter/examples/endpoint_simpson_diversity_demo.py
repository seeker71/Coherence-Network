# endpoint_simpson_diversity_demo.py — the body of
# vitality_service._simpson_diversity, captured as pure Python and compiled
# to a Form recipe.
#
# Simpson's diversity index: 1 - sum(p_i^2), where p_i = count_i / total.
# Returns 0.0 for no diversity (a single category, or no counts), and
# approaches 1.0 as the distribution spreads across many even categories.
# It is the substrate's spread signal: how evenly contributors' dominant
# worldview axes are distributed across the network.
#
# Pure list + float arithmetic — division, multiplication, subtraction. No
# transcendentals, so the same value renders across all three runtimes:
#   - CPython
#   - kernel-bmf-run
#   - form-kernel-rust
#
# The total <= 0 guard returns 0.0 (an empty or all-zero count list has no
# diversity to measure) — matched exactly by the recipe's branch.


def sum_ints(counts):
    total = 0
    i = 0
    n = len(counts)
    while i < n:
        total = total + counts[i]
        i = i + 1
    return total


def sum_sq_proportions(counts, total_f):
    acc = 0.0
    p = 0.0
    i = 0
    n = len(counts)
    while i < n:
        p = counts[i] / total_f
        acc = acc + p * p
        i = i + 1
    return acc


def simpson_diversity(counts):
    total = sum_ints(counts)
    if total <= 0:
        return 0.0
    # total + 0.0 forces IEEE-754 true division in the loop (the kernel's
    # `div` is integer division on two ints; Python's `/` is always float).
    # Value-identical to the original `counts[i] / total`.
    total_f = total + 0.0
    return 1.0 - sum_sq_proportions(counts, total_f)


# Endpoint's frozen sample input — four worldview-axis buckets of sizes
# 2, 1, 1, with one empty: total = 4, sum of squared proportions =
# 0.5^2 + 0.25^2 + 0.25^2 = 0.25 + 0.0625 + 0.0625 = 0.375, so the index
# is 1.0 - 0.375 = 0.625.
counts = [2, 1, 1]

simpson_diversity(counts)
