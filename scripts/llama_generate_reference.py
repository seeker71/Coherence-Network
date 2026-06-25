#!/usr/bin/env python3
"""llama_generate_reference.py — independent pure-libm fp64 reference for the llama
(decoder-only, GQA) autoregressive GENERATION LOOP (brick 3zn).

The body proves every piece of real llama3.2 decode four-way and on the M4 GPU: the
multi-layer GQA decode stack (gqa-multi-layer-stack.fk, #3616), greedy argmax
(greedy-decode.fk, #3402), RMSNorm (llama-numerics.fk, #3308), matvec (transformer-block.fk).
This reference grounds the LOOP that wires them into actual TOKEN ids:

    embed     : xs = [token_embd[id] for id in ids]      (no positional — RoPE is in attention)
    states    : hs = multi-layer GQA decode stack over xs
    final     : normed = RMSNorm(hs[last], g_final, eps)  (the model's output norm)
    logits    : tb_matvec(unembed, normed)                (output projection; tied unembed = token_embd)
    next id   : argmax(logits)  (ties -> lowest, matching greedy-decode's strictly-greater rule)
    repeat, appending next id.

This is the LAST recipe-altitude piece before wiring real GGUF weights into the proven loop.
It is grounded for the single-head base-10000 case (n_q=1, n_kv=1, HD=4), where the GQA stack
reduces EXACTLY to the MHA stack (gqa-multi-layer-stack.fk claim 128) — so this libm MHA stack
is the correct oracle. Self-check FIRST: the 1-layer stack must reproduce causal-attention-band's
published pins (1893731, -1069281, 1648117); only then are the generated token ids trustworthy.

The embed table is chosen so embed([0,1]) == the band's published x fixture
([[1,-0.5,0.5,2],[-1,0.25,1.5,-0.75]]) — so the stack output reuses the already-four-way pins.
"""
import math

# --- layer 0: the causal-attention-band / llama-block-band fixture (d=4) ---
G1 = [0.9, 1.1, 1.0, 0.95]
G2 = [1.05, 0.95, 1.0, 0.9]
WQ = [[0.5, -0.25, 0.1, 0.3], [0.2, 0.4, -0.3, 0.1], [-0.1, 0.2, 0.5, -0.2], [0.3, 0.0, -0.15, 0.25]]
WK = [[0.2, 0.4, -0.3, 0.1], [0.3, -0.2, 0.25, 0.5], [0.1, 0.15, -0.05, 0.2], [-0.25, 0.3, 0.4, -0.1]]
WV = [[0.3, -0.2, 0.25, 0.5], [0.6, 0.1, -0.2, 0.4], [0.05, -0.1, 0.3, 0.2], [0.15, 0.35, -0.25, 0.1]]
WO = [[0.6, 0.1, -0.2, 0.4], [-0.2, 0.4, 0.3, 0.1], [0.25, -0.15, 0.5, 0.05], [0.1, 0.2, -0.3, 0.45]]
WG = [[0.5, -0.3, 0.2, 0.1], [0.2, 0.7, -0.4, 0.3], [-0.1, 0.25, 0.4, -0.2], [0.3, 0.1, -0.15, 0.5]]
WU = [[0.25, -0.15, 0.3, 0.05], [0.1, 0.4, -0.2, 0.15], [0.35, 0.2, -0.1, 0.25], [-0.2, 0.3, 0.15, 0.4]]
WD = [[0.4, -0.2, 0.3, 0.1], [0.15, 0.5, -0.25, 0.2], [-0.3, 0.1, 0.45, -0.15], [0.2, -0.1, 0.35, 0.3]]

# --- layer 1: a SECOND, distinct bundle (same architecture, different weights) ---
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

# --- the embed/unembed table (tied). row0,row1 == the band's x fixture so the stack reuses
#     the published pins; row2 == x3's third row; row3 a fourth distinct token. V=4. ---
TOKEN_EMBD = [
    [1.0, -0.5, 0.5, 2.0],
    [-1.0, 0.25, 1.5, -0.75],
    [0.5, 1.0, -0.5, 0.25],
    [0.25, -1.0, 0.75, -0.5],
]
G_FINAL = [1.1, 0.9, 1.0, 1.05]


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
    n1 = [rmsnorm(x, g1, eps) for x in xs]
    qs = [rope(matvec(wq, n), i, HD) for i, n in enumerate(n1)]
    ks = [rope(matvec(wk, n), i, HD) for i, n in enumerate(n1)]
    vs = [matvec(wv, n) for n in n1]
    attn = []
    for i in range(len(xs)):
        a = attend_one(qs[i], ks[:i + 1], vs[:i + 1], scale)
        attn.append(matvec(wo, a))
    h = [vec_add(xs[i], attn[i]) for i in range(len(xs))]
    n2 = [rmsnorm(hi, g2, eps) for hi in h]
    ffn = []
    for n in n2:
        gg = matvec(wg, n)
        uu = matvec(wu, n)
        sg = [silu(gg[j]) * uu[j] for j in range(len(gg))]
        ffn.append(matvec(wd, sg))
    return [vec_add(h[i], ffn[i]) for i in range(len(xs))]


L0 = (G1, EPS, WQ, WK, WV, WO, SCALE, HD, G2, WG, WU, WD)
L1 = (G1b, EPS, WQb, WKb, WVb, WOb, SCALE, HD, G2b, WGb, WUb, WDb)


def stack_causal(xs, layers):
    for L in layers:
        xs = block_causal(xs, *L)
    return xs


def argmax(xs):
    """ties -> lowest index (strictly-greater replacement, matching greedy-decode gd-argmax)."""
    bi, bv = 0, xs[0]
    for i in range(1, len(xs)):
        if xs[i] > bv:
            bi, bv = i, xs[i]
    return bi


def generate(seed_ids, layers, steps):
    """the autoregressive greedy loop: ids -> ids + `steps` generated token ids."""
    ids = list(seed_ids)
    for _ in range(steps):
        xs = [TOKEN_EMBD[i] for i in ids]            # embed
        hs = stack_causal(xs, layers)                 # multi-layer decode stack
        normed = rmsnorm(hs[-1], G_FINAL, EPS)        # final RMSNorm on the last position
        logits = matvec(TOKEN_EMBD, normed)           # unembed (tied) -> logits over the vocab
        ids.append(argmax(logits))                    # greedy next token
    return ids


def pin(v):
    return round(v * 1000000.0)


# --- SELF-CHECK: the 1-layer stack reproduces causal-attention-band's published pins ---
one = stack_causal([[1.0, -0.5, 0.5, 2.0], [-1.0, 0.25, 1.5, -0.75]], [L0])
assert pin(one[0][0]) == 1893731, f"self-check token0 {pin(one[0][0])}"
assert pin(one[1][0]) == -1069281, f"self-check last0 {pin(one[1][0])}"
assert pin(one[1][2]) == 1648117, f"self-check last2 {pin(one[1][2])}"
print("SELF-CHECK PASS: 1-layer stack == causal-attention-band pins (1893731, -1069281, 1648117)")

layers2 = [L0, L1]
seed = [0, 1]   # embeds to the band's x fixture exactly

gen1 = generate(seed, layers2, 1)
gen2 = generate(seed, layers2, 2)
gen3 = generate(seed, layers2, 3)
print(f"\nsingle-head cfg10, 2-layer llama generation from seed {seed}:")
print(f"  generate(seed, 1) = {gen1}")
print(f"  generate(seed, 2) = {gen2}")
print(f"  generate(seed, 3) = {gen3}")
print(f"  -> the band pins the generated tokens: t1={gen1[-1]}, t2={gen2[-1]}, t3={gen3[-1]}")

# --- prefix stability: a longer generation never rewrites earlier tokens (greedy appends) ---
assert gen2[:len(gen1)] == gen1, "prefix stability broken"
assert gen3[:len(gen2)] == gen2, "prefix stability broken"
print("\nprefix-stable: generate(seed, k+1) extends generate(seed, k) (greedy appends, never rewrites)")

# --- input-dependence: a DIFFERENT seed yields a DIFFERENT first generated token (argmax is not
#     stuck — the loop responds to the prompt). seed [1,0] is the band's x with the rows swapped. ---
seed_b = [1, 0]
genb1 = generate(seed_b, layers2, 1)
print(f"\ninput-dependence: first token from seed {seed} = {gen1[-1]}; "
      f"from seed {seed_b} = {genb1[-1]}  (differ: {gen1[-1] != genb1[-1]})")
assert gen1[-1] != genb1[-1], "expected input-dependence"
