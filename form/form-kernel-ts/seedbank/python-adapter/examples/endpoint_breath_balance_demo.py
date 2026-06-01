# endpoint_breath_balance_demo.py — the body of
# vitality_service._breath_balance, captured as pure Python and compiled
# to a Form recipe.
#
# Breath balance: how evenly the three phase states (gas / water / ice)
# are distributed. Normalized Shannon entropy H / H_max, where H_max =
# ln(3) is the maximum entropy for three categories. Returns 1.0 for
# perfect balance (equal thirds), 0.0 when everything sits in one phase.
# It is the substrate's breath-rhythm signal.
#
# This is the first kernel-served route to use a transcendental native:
# math.log lowers to the kernel's math_log (natural log). The same value
# renders across all three runtimes — CPython, the Form-native walker,
# and form-kernel-rust — because all three carry an IEEE-754 ln and the
# inputs chosen here land on values whose ratio H/H_max prints identically.
#
# Edge discipline — the log-of-zero guard:
#   A proportion p contributes p*ln(p) to the entropy ONLY when p > 0.
#   ln(0) is undefined (−inf); Python guards `if p > 0` before the log,
#   and this recipe guards identically. A single-phase distribution
#   (one nonzero, two zero) therefore has H = 0 → balance 0.0, with no
#   ln(0) ever evaluated. The total == 0 guard returns 0.0 up front.

import math


def entropy(p_gas, p_water, p_ice):
    # Accumulate the (non-positive) terms p*ln(p) for p > 0, then negate
    # ONCE — exactly Python's `-sum(p*log(p) for p in props if p > 0)`.
    # Negating each term and summing (`h = h - term`) would round
    # differently in the last ULP; the single trailing negation matches
    # CPython to the bit. For a single nonzero phase the sum is +0.0 and
    # the negation yields -0.0 — same as `-sum([0.0])` in CPython.
    acc = 0.0
    if p_gas > 0.0:
        acc = acc + p_gas * math.log(p_gas)
    if p_water > 0.0:
        acc = acc + p_water * math.log(p_water)
    if p_ice > 0.0:
        acc = acc + p_ice * math.log(p_ice)
    return -1.0 * acc


def breath_balance(gas, water, ice):
    total = gas + water + ice
    if total <= 0:
        return 0.0
    # total + 0.0 forces IEEE-754 true division (the kernel's `div` is
    # integer division on two ints; Python's `/` is always float).
    total_f = total + 0.0
    p_gas = gas / total_f
    p_water = water / total_f
    p_ice = ice / total_f
    h = entropy(p_gas, p_water, p_ice)
    h_max = math.log(3.0)
    return h / h_max


# Endpoint's frozen sample input — perfectly balanced thirds: gas = water
# = ice = 1, total = 3. Each proportion is 1/3; H = -3 * (1/3) * ln(1/3) =
# -ln(1/3) = ln(3) = H_max, so the normalized balance is exactly 1.0.
gas = 1
water = 1
ice = 1

breath_balance(gas, water, ice)
