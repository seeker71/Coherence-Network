# endpoint_shannon_entropy_demo.py — the body of
# breath_service._shannon_entropy_normalized, captured as pure Python and
# compiled to a Form recipe.
#
# Shannon entropy normalized to [0, 1] over three phase counts (gas / water
# / ice). Maximum entropy is ln(3) when the three phases are equally
# represented; the result is H / H_max rounded to 4 places. Returns 0.0 when
# only one phase is present (H = 0). Distinct from breath_balance:
#   - the per-term accumulator SUBTRACTS (`entropy = entropy - p*ln(p)`), so a
#     single nonzero phase yields +0.0 (not breath_balance's trailing-negation
#     -0.0);
#   - the result is wrapped in round(_, 4) — CPython-exact via round_ndigits;
#   - the empty guard is `total == 0` (vs breath_balance's `total <= 0`).
#
# This route folds two prior unlocks into one shape: the math.log
# transcendental native (ln, breath_balance's unlock) and the round_ndigits
# native (PR #2320, cost_vector's unlock). math.log(3) is the H_max
# denominator; round(entropy / max_entropy, 4) is the CPython-exact rounding.
#
# Edge discipline — the log-of-zero guard: a count contributes p*ln(p) ONLY
# when count > 0, so ln(0) is never evaluated. total == 0 returns 0.0 up
# front; max_entropy = ln(3) is always positive, so the `if max_entropy > 0`
# branch in the source always takes the rounded division (the else 0.0 is
# unreachable in practice but kept for byte-identity with the Python source).

import math


def shannon_entropy_normalized(gas, water, ice):
    total = gas + water + ice
    if total == 0:
        return 0.0

    max_entropy = math.log(3)  # ln(3) for three categories
    # total + 0.0 forces IEEE-754 true division (the kernel's `div` is integer
    # division on two ints; Python's `/` is always float).
    total_f = total + 0.0
    entropy = 0.0
    if gas > 0:
        p = gas / total_f
        entropy = entropy - p * math.log(p)
    if water > 0:
        p = water / total_f
        entropy = entropy - p * math.log(p)
    if ice > 0:
        p = ice / total_f
        entropy = entropy - p * math.log(p)

    return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0


# Endpoint's frozen sample input — perfectly balanced thirds: gas = water =
# ice = 1, total = 3. Each proportion is 1/3; H = -3 * (1/3) * ln(1/3) =
# ln(3) = H_max, so the normalized entropy is round(1.0, 4) = 1.0.
gas = 1
water = 1
ice = 1

shannon_entropy_normalized(gas, water, ice)
