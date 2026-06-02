"""form_native.py — Python implementations that mirror Form recipes literally.

Each function here follows its sibling Form recipe in
docs/coherence-substrate/cosine.form and cell-numerics.form by
*composition*, not by reaching for Python's stdlib math. The
discipline:

  - sqrt is Newton-Raphson iteration, not math.sqrt
  - exp is Taylor series with argument reduction, not math.exp
  - tanh is (exp(2x) - 1) / (exp(2x) + 1), not math.tanh
  - vector_add is recursive concat(head + head, recurse(tail, tail)),
    not [a[i] + b[i] for i in range(...)]
  - matvec is recursive dot_product per row, not numpy

The point is to verify the *Form recipe semantics*. If form_native.cosine
matches organ._cosine for many inputs (within tolerance for the
iterative parts), then the Form recipes in cosine.form and
cell-numerics.form are structurally faithful to the Python originals —
they would produce the same numbers when executed by the substrate's
Form evaluator.

This module is what `substrate_dispatch.register_recipe(...)` registers
when "form-native by default" is enabled. The decorator-wrapped host
functions in organ.py then route through these implementations.

Mirrors these recipes:
  - dot_product, sum_of_squares (cosine.form Parts 2-3)
  - sqrt_newton, sqrt (cosine.form Part 4)
  - norm (cosine.form Part 5)
  - cosine (cosine.form Part 6)
  - pairwise_multiply (cosine.form Part 2)
  - vector_add, vector_sub, scalar_mul (cell-numerics.form Part 1)
  - matvec (cell-numerics.form Part 2)
  - factorial, pow_int, exp_term, exp_series_accum, exp_series, exp
    (cell-numerics.form Part 3)
  - tanh, sigmoid (cell-numerics.form Part 4)
  - strategy_score (cell-numerics.form Part 5)
"""

from __future__ import annotations

import math  # used only by pair_angle (temporary host execution for form_cli driver parity; the Form recipe + kernel math_acos provide the native path)

# ─── cosine.form Part 2-3 — pairwise_multiply / dot_product / sum_of_squares ─

def pairwise_multiply(a, b):
    if len(a) == 0 or len(b) == 0:
        return []
    return [a[0] * b[0]] + pairwise_multiply(a[1:], b[1:])


def dot_product(a, b):
    products = pairwise_multiply(a, b)
    # sum is a primitive in Form's stdlib (sum_of_list); Python's
    # builtin sum is the natural mirror.
    return sum(products)


def sum_of_squares(a):
    return dot_product(a, a)


# ─── cosine.form Part 4 — sqrt via Newton's method ──────────────────────────

def sqrt_newton(n, guess, iterations):
    if iterations <= 0:
        return guess
    return sqrt_newton(n, (guess + n / guess) / 2, iterations - 1)


def sqrt(n):
    if n <= 0:
        return 0
    return sqrt_newton(n, n / 2 + 0.5, 16)


# ─── cosine.form Part 5 — Euclidean norm ────────────────────────────────────

def norm(a):
    return sqrt(sum_of_squares(a))


# ─── cosine.form Part 6 — cosine similarity ─────────────────────────────────

def cosine(a, b):
    dot = dot_product(a, b)
    norm_a = norm(a)
    norm_b = norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)


# ─── cell-numerics.form Part 1 — vector arithmetic ──────────────────────────

def vector_add(a, b):
    if len(a) == 0 or len(b) == 0:
        return []
    return [a[0] + b[0]] + vector_add(a[1:], b[1:])


def vector_sub(a, b):
    if len(a) == 0 or len(b) == 0:
        return []
    return [a[0] - b[0]] + vector_sub(a[1:], b[1:])


def scalar_mul(s, v):
    if len(v) == 0:
        return []
    return [s * v[0]] + scalar_mul(s, v[1:])


# ─── cell-numerics.form Part 2 — matrix-vector multiply ─────────────────────

def matvec(matrix, x):
    if len(matrix) == 0:
        return []
    return [dot_product(matrix[0], x)] + matvec(matrix[1:], x)


# ─── cell-numerics.form Part 3 — exp via Taylor expansion ───────────────────

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def pow_int(base, n):
    if n <= 0:
        return 1
    return base * pow_int(base, n - 1)


def exp_term(x, n):
    return pow_int(x, n) / factorial(n)


def exp_series_accum(x, n, count, acc):
    if n >= count:
        return acc
    return exp_series_accum(x, n + 1, count, acc + exp_term(x, n))


def exp_series(x):
    # Argument reduction: exp(x) = exp(x/4)^4 for |x| > 2.
    if x > 2 or x < -2:
        return pow_int(exp_series_accum(x / 4, 0, 20, 0), 4)
    return exp_series_accum(x, 0, 20, 0)


def exp(x):
    return exp_series(x)


# ─── cell-numerics.form Part 4 — tanh and sigmoid ───────────────────────────

def tanh(x):
    if x > 5:
        return 1
    if x < -5:
        return -1
    e2x = exp(2 * x)
    return (e2x - 1) / (e2x + 1)


def sigmoid(x):
    if x > 50:
        return 1
    if x < -50:
        return 0
    return 1 / (1 + exp(-x))


# ─── cell-numerics.form Part 5 — strategy_score ─────────────────────────────

def strategy_score(strategy, spectrum, total_desire=None):
    """Mirror of strategy_score from cell-numerics.form Part 5.

    The Python intrinsic in organ.py takes (strategy, spectrum, total_desire).
    The Form recipe is (strategy, spectrum); total_desire is unused by the
    score itself (it's used downstream by pick_strategy for fallback).
    Accept the third arg for signature parity.
    """
    fa = pairwise_multiply(list(strategy.frequency), list(strategy.angle))
    return cosine(spectrum, fa)


# ─── normalize (cell-numerics.form Part 6) ──────────────────────────────────

def normalize(v):
    n = norm(v)
    if n == 0:
        return v
    return scalar_mul(1 / n, v)


# ─── geometry projection (trace-symbol-spaces.form Part 6) ─────────────────
# pair_cosine provides a named, reusable entrypoint for the geometry lens
# ("blueprint as invariant center; recipes as vectors through band space").
# It composes strictly over the existing cosine / dot_product / norm
# already present in this module (no new stdlib math). This is the
# Form-native operator surface that makes the "make-geometry-projection-executable"
# gap closure recipe in the .form directly callable on any 8-band spectra
# (live efficacy-probe vectors supplied at call time).

def pair_cosine(a, b):
    """Named geometry projection operator — thin composition over cosine.
    Returns the cosine similarity between two 8-band (or N-band) vectors.
    Used for the DMT-laser symbol space thruline and future windows.
    """
    return cosine(a, b)


def pair_angle(a, b):
    """Geometry projection: angle in radians between two vectors.
    Used for the full thruline + orbit analysis on live efficacy-probe spectra.
    """
    c = pair_cosine(a, b)
    if c > 1.0:
        c = 1.0
    if c < -1.0:
        c = -1.0
    return math.acos(c)


# dominant_band_delta — small helper for richer geometry readout.
# Given two vectors, returns (index, delta) of the band with the largest
# absolute difference. Directly supports the "155.4° opposing change on band 3"
# observation from the 02:56:35 live traces (without embedding the data here).
def dominant_band_delta(a, b):
    if len(a) == 0 or len(b) == 0:
        return (0, 0.0)
    n = min(len(a), len(b))
    max_delta = 0.0
    max_idx = 0
    for i in range(n):
        d = abs(a[i] - b[i])
        if d > max_delta:
            max_delta = d
            max_idx = i
    return (max_idx, max_delta)
