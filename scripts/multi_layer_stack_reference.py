#!/usr/bin/env python3
"""multi_layer_stack_reference.py — independent pure-libm fp64 reference for the
multi-layer causal llama decoder STACK (brick 3z, the depth structure under a real
local llama).

A real llama3.2:3b stacks 28 decoder blocks: x¹=block₀(x⁰), x²=block₁(x¹), … each
layer with its OWN weights and its OWN KV cache. This reference computes a 2-layer
causal stack with libm cos/sin/exp/sqrt and prints the pinned integer values
(round(v·1e6)) the four-way band tests/multi-layer-stack-band.fk asserts against.

It is the independent oracle: the Form recipes (ln-rmsnorm/rope/ln-swiglu/tb-attend-one
and the lblk-block-causal block) already match libm at 1e-6 four-way (#3365), so this
libm computation grounds the stacked magnitudes the band pins. Self-check FIRST: the
single-block (layer 0 only) output must reproduce causal-attention-band's published
pins (1893731, -1069281, 1648117) — only then are the 2-layer pins trustworthy.

Mirrors the recipe reduction order exactly: RMSNorm (mean of squares, no mean-subtract,
gain, eps inside sqrt), bias-free projections, RoPE adjacent-pair rotation
(θ=pos·10000^(-(i mod HD)/HD)), causal attention (softmax over the 0..i key prefix,
scale=1/√d, max-subtracted softmax), SwiGLU (silu(gate)·up) FFN, residuals.
"""
import math

# --- the causal-attention-band / llama-block-band fixture (layer 0) ---
G1 = [0.9, 1.1, 1.0, 0.95]
G2 = [1.05, 0.95, 1.0, 0.9]
WQ = [[0.5, -0.25, 0.1, 0.3], [0.2, 0.4, -0.3, 0.1], [-0.1, 0.2, 0.5, -0.2], [0.3, 0.0, -0.15, 0.25]]
WK = [[0.2, 0.4, -0.3, 0.1], [0.3, -0.2, 0.25, 0.5], [0.1, 0.15, -0.05, 0.2], [-0.25, 0.3, 0.4, -0.1]]
WV = [[0.3, -0.2, 0.25, 0.5], [0.6, 0.1, -0.2, 0.4], [0.05, -0.1, 0.3, 0.2], [0.15, 0.35, -0.25, 0.1]]
WO = [[0.6, 0.1, -0.2, 0.4], [-0.2, 0.4, 0.3, 0.1], [0.25, -0.15, 0.5, 0.05], [0.1, 0.2, -0.3, 0.45]]
WG = [[0.5, -0.3, 0.2, 0.1], [0.2, 0.7, -0.4, 0.3], [-0.1, 0.25, 0.4, -0.2], [0.3, 0.1, -0.15, 0.5]]
WU = [[0.25, -0.15, 0.3, 0.05], [0.1, 0.4, -0.2, 0.15], [0.35, 0.2, -0.1, 0.25], [-0.2, 0.3, 0.15, 0.4]]
WD = [[0.4, -0.2, 0.3, 0.1], [0.15, 0.5, -0.25, 0.2], [-0.3, 0.1, 0.45, -0.15], [0.2, -0.1, 0.35, 0.3]]

# --- a SECOND, distinct layer (layer 1): same architecture, different weights, so the
#     stack genuinely threads per-layer weights forward (not the same block applied twice) ---
G1b = [1.0, 0.9, 1.05, 1.1]
G2b = [0.95, 1.1, 0.9, 1.0]
WQb = [[0.1, 0.3, -0.2, 0.4], [-0.3, 0.2, 0.5, -0.1], [0.4, -0.1, 0.2, 0.3], [0.0, 0.25, -0.35, 0.15]]
WKb = [[0.3, -0.2, 0.4, 0.1], [0.15, 0.5, -0.1, 0.2], [-0.05, 0.3, 0.25, -0.15], [0.4, -0.25, 0.1, 0.35]]
WVb = [[0.2, 0.4, -0.15, 0.3], [0.5, -0.1, 0.2, 0.45], [-0.2, 0.35, 0.1, -0.05], [0.25, 0.15, -0.3, 0.2]]
WOb = [[0.4, -0.3, 0.2, 0.5], [0.1, 0.45, -0.15, 0.2], [-0.25, 0.3, 0.4, 0.05], [0.35, -0.1, 0.25, -0.2]]
WGb = [[0.3, 0.2, -0.4, 0.1], [0.5, -0.3, 0.15, 0.25], [-0.1, 0.4, 0.3, -0.2], [0.2, 0.05, -0.25, 0.45]]
WUb = [[0.15, 0.35, -0.2, 0.1], [0.4, -0.15, 0.25, 0.3], [-0.25, 0.2, 0.35, -0.1], [0.3, 0.1, -0.05, 0.4]]
WDb = [[0.35, -0.15, 0.25, 0.2], [0.2, 0.4, -0.3, 0.1], [-0.2, 0.15, 0.5, -0.25], [0.1, -0.05, 0.3, 0.45]]

EPS = 0.00001
HD = 4
SCALE = 1.0 / math.sqrt(4.0)


def matvec(rows, x):
    return [sum(r[j] * x[j] for j in range(len(x))) for r in rows]


def vec_add(a, b):
    return [a[i] + b[i] for i in range(len(a))]


def rmsnorm(x, g, eps):
    ms = sum(v * v for v in x) / len(x)
    inv = 1.0 / math.sqrt(ms + eps)
    return [x[i] * inv * g[i] for i in range(len(x))]


def rope(x, pos, HD):
    out = [0.0] * len(x)
    for i in range(0, len(x), 2):
        hd = i % HD
        a = pos * (10000.0 ** (-hd / HD))
        q0, q1 = x[i], x[i + 1]
        out[i] = q0 * math.cos(a) - q1 * math.sin(a)
        out[i + 1] = q0 * math.sin(a) + q1 * math.cos(a)
    return out


def silu(x):
    return x / (1.0 + math.exp(-x))


def attend_one(q, ks, vs, scale):
    scores = [sum(q[j] * k[j] for j in range(len(q))) * scale for k in ks]
    m = max(scores)
    es = [math.exp(s - m) for s in scores]
    z = sum(es)
    alphas = [e / z for e in es]
    d = len(vs[0])
    acc = [0.0] * d
    for a, v in zip(alphas, vs):
        for j in range(d):
            acc[j] += v[j] * a
    return acc


def block_causal(xs, g1, eps, wq, wk, wv, wo, scale, HD, g2, wg, wu, wd):
    """one causal llama decoder block over a whole sequence (the full recompute)."""
    n1 = [rmsnorm(x, g1, eps) for x in xs]
    qs = [rope(matvec(wq, n), i, HD) for i, n in enumerate(n1)]
    ks = [rope(matvec(wk, n), i, HD) for i, n in enumerate(n1)]
    vs = [matvec(wv, n) for n in n1]
    attn = []
    for i in range(len(xs)):
        a = attend_one(qs[i], ks[:i + 1], vs[:i + 1], scale)  # causal prefix 0..i
        attn.append(matvec(wo, a))
    h = [vec_add(xs[i], attn[i]) for i in range(len(xs))]
    n2 = [rmsnorm(hi, g2, eps) for hi in h]
    ffn = []
    for n in n2:
        g = matvec(wg, n)
        u = matvec(wu, n)
        sg = [silu(g[j]) * u[j] for j in range(len(g))]
        ffn.append(matvec(wd, sg))
    return [vec_add(h[i], ffn[i]) for i in range(len(xs))]


L0 = (G1, EPS, WQ, WK, WV, WO, SCALE, HD, G2, WG, WU, WD)
L1 = (G1b, EPS, WQb, WKb, WVb, WOb, SCALE, HD, G2b, WGb, WUb, WDb)


def stack_causal(xs, layers):
    for L in layers:
        xs = block_causal(xs, *L)
    return xs


def pin(v):
    return round(v * 1000000.0)


x2 = [[1.0, -0.5, 0.5, 2.0], [-1.0, 0.25, 1.5, -0.75]]
x3 = [[1.0, -0.5, 0.5, 2.0], [-1.0, 0.25, 1.5, -0.75], [0.5, 1.0, -0.5, 0.25]]

# --- SELF-CHECK: layer-0-only stack must reproduce causal-attention-band's published pins ---
one = stack_causal(x2, [L0])
assert pin(one[0][0]) == 1893731, f"self-check token0 {pin(one[0][0])}"
assert pin(one[1][0]) == -1069281, f"self-check last0 {pin(one[1][0])}"
assert pin(one[1][2]) == 1648117, f"self-check last2 {pin(one[1][2])}"
print("SELF-CHECK PASS: 1-layer stack == causal-attention-band pins (1893731, -1069281, 1648117)")

# --- the 2-layer stack: the independent libm pins the band asserts ---
two2 = stack_causal(x2, [L0, L1])
two3 = stack_causal(x3, [L0, L1])
print(f"\n2-layer stack, S=2:")
print(f"  stack2[0][0] = {pin(two2[0][0])}")
print(f"  stack2[1][0] = {pin(two2[1][0])}")
print(f"  stack2[1][2] = {pin(two2[1][2])}")
print(f"2-layer stack, S=3:")
print(f"  stack3[0][0] = {pin(two3[0][0])}")
print(f"  stack3[1][0] = {pin(two3[1][0])}")
print(f"  stack3[2][0] = {pin(two3[2][0])}")

# --- depth is NOT a no-op: 2-layer differs from 1-layer at the same position ---
print(f"\ndepth-not-noop: 1-layer[0][0]={pin(one[0][0])} vs 2-layer[0][0]={pin(two2[0][0])} "
      f"(differ: {pin(one[0][0]) != pin(two2[0][0])})")

# --- AR invariant THROUGH depth: appending a future token leaves earlier tokens' STACKED output unchanged ---
inv0 = pin(two3[0][0]) == pin(two2[0][0])
inv1 = pin(two3[1][0]) == pin(two2[1][0])
print(f"AR-invariant-through-depth: stack3[0]==stack2[0] {inv0}; stack3[1]==stack2[1] {inv1}")
