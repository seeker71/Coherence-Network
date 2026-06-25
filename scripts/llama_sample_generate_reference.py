#!/usr/bin/env python3
"""llama_sample_generate_reference.py — independent pure-libm fp64 reference for the llama
(decoder-only, GQA) autoregressive SAMPLED generation loop (brick: wire smp-draw into the loop).

The greedy generation loop is four-way (llama-generate.fk, #3649, lg-generate); the token-SAMPLING
draw is four-way (sampling.fk, #3651: temperature/softmax/top-k/top-p + a MINSTD counter PRNG +
inverse-CDF). This reference grounds the WIRING that threads them: at each step compute the logits
(the same stack as greedy), shape them (temperature -> softmax -> top-k), advance the PRNG state ONCE,
draw a token by inverse-CDF, append, recurse:

    logits  : same as greedy (embed -> multi-layer GQA decode stack -> final RMSNorm -> tied unembed)
    shape   : probs = topk_mask(softmax(temperature(logits, t)), k)
    draw    : state = minstd(state) ; u = state / (2^31-1) ; next = first bucket whose cumulative > u
    repeat, threading the advanced state alongside the ids.

The LOAD-BEARING law (core-abstraction-first): with k=1 and a unique argmax, top-k=1 yields a one-hot
distribution, so the draw returns the argmax for EVERY u -> the sampled loop reduces EXACTLY to the
greedy loop lg-generate (#3649). Greedy is the k=1 special case, not a parallel path. Temperature is a
monotone positive scaling, so it never changes the k=1 winner -> k=1 is temperature-invariant too.

The PRNG is grounded against MINSTD's PUBLISHED canonical sequence from seed 1
(16807, 282475249, 1622650073, ...) — an authority OUTSIDE our own folds (matches sampling-band).
The stack/logits reuse the already-four-way llama-generate-band fixture (embed([0,1]) == the band's
published x pins). The fixture and stack are shared verbatim with llama_generate_reference.py; this
file self-checks the same 1-layer pins before trusting any sampled token.
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

# --- the tied embed/unembed table (V=4). row0,row1 == the band's x fixture so the stack reuses the
#     published pins; rows 2,3 are two further vocabulary tokens. ---
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
    """ties -> lowest index (strictly-greater, matching greedy-decode gd-argmax / gd-token)."""
    bi, bv = 0, xs[0]
    for i in range(1, len(xs)):
        if xs[i] > bv:
            bi, bv = i, xs[i]
    return bi


def logits_at(ids, layers):
    xs = [TOKEN_EMBD[i] for i in ids]
    hs = stack_causal(xs, layers)
    normed = rmsnorm(hs[-1], G_FINAL, EPS)
    return matvec(TOKEN_EMBD, normed)


def generate(seed_ids, layers, steps):
    """the greedy loop (== lg-generate, #3649): ids -> ids + `steps` greedy token ids."""
    ids = list(seed_ids)
    for _ in range(steps):
        ids.append(argmax(logits_at(ids, layers)))
    return ids


# === the SAMPLING DRAW half (== sampling.fk, #3651), matched bit-for-bit ===
def temperature(logits, t):
    return [v / t for v in logits]


def softmax(logits):
    m = max(logits)
    es = [math.exp(v - m) for v in logits]
    z = sum(es)
    return [e / z for e in es]


def kth_largest(xs, k):
    """value at rank k (0-based) descending; ties consumed one occurrence per rank (smp-kth-largest)."""
    work = list(xs)
    for _ in range(k):
        work.remove(max(work))  # drop ONE occurrence of the running max (smp-drop-one)
    return max(work)


def topk_mask(probs, k):
    thr = kth_largest(probs, k - 1)
    kept = [p if p >= thr else 0.0 for p in probs]   # smp-topk-keep (boundary ties kept)
    z = sum(kept)
    return [p / z for p in kept]                      # smp-renorm


def minstd(state):
    return (16807 * state) % 2147483647               # Park-Miller, state' = 16807*state mod 2^31-1


def uniform(state):
    return state / 2147483647.0


def cdf_pick(probs, u):
    """inverse-CDF: first bucket whose CUMULATIVE mass STRICTLY exceeds u (smp-cdf-pick / smp-sample)."""
    cum = 0.0
    for idx, p in enumerate(probs):
        cum += p
        if cum > u:
            return idx
    return len(probs) - 1


def generate_sampled(seed_ids, layers, t, k, state, steps):
    """the SAMPLED loop: thread (ids, PRNG state). Advance the state ONCE per step (the smp-draw-seq
    discipline), draw the next token from the shaped distribution, append, recurse."""
    ids = list(seed_ids)
    for _ in range(steps):
        probs = topk_mask(softmax(temperature(logits_at(ids, layers), t)), k)
        state = minstd(state)
        ids.append(cdf_pick(probs, uniform(state)))
    return ids


def pin(v):
    return round(v * 1000000.0)


if __name__ == "__main__":
    # --- SELF-CHECK: the 1-layer stack reproduces causal-attention-band's published pins ---
    one = stack_causal([[1.0, -0.5, 0.5, 2.0], [-1.0, 0.25, 1.5, -0.75]], [L0])
    assert pin(one[0][0]) == 1893731, f"self-check token0 {pin(one[0][0])}"
    assert pin(one[1][0]) == -1069281, f"self-check last0 {pin(one[1][0])}"
    assert pin(one[1][2]) == 1648117, f"self-check last2 {pin(one[1][2])}"
    print("SELF-CHECK PASS: 1-layer stack == causal-attention-band pins (1893731, -1069281, 1648117)")

    # --- PRNG self-check: MINSTD's published canonical sequence from seed 1 ---
    s, seq = 1, []
    for _ in range(6):
        s = minstd(s)
        seq.append(s)
    assert seq == [16807, 282475249, 1622650073, 984943658, 1144108930, 470211272], seq
    print(f"PRNG SELF-CHECK PASS: MINSTD seq from seed 1 = {seq[:3]}...")

    layers2 = [L0, L1]
    seed = [0, 1]    # embeds to the band's x fixture exactly
    seed_b = [1, 0]  # the x fixture with rows swapped

    # --- greedy baseline (== lg-generate, #3649) ---
    g3 = generate(seed, layers2, 3)
    print(f"\ngreedy generate(seed {seed}, 3) = {g3}")

    # --- argmax must be STRICTLY unique at each greedy step (so k=1 consolidates to greedy cleanly) ---
    ids = list(seed)
    for _ in range(3):
        lg = logits_at(ids, layers2)
        srt = sorted(lg, reverse=True)
        assert srt[0] != srt[1], f"argmax tie at logits {lg} — k=1 consolidation needs a strict argmax"
        ids.append(argmax(lg))
    print("argmax strict at every step -> k=1 top-k is a clean one-hot")

    # --- CONSOLIDATION: k=1 (any seed, any t>0) == greedy, token-for-token ---
    for st in (1, 7, 12345):
        for t in (1.0, 0.5, 2.0):
            s1 = generate_sampled(seed, layers2, t, 1, st, 3)
            assert s1 == g3, f"k=1 t={t} seed={st}: {s1} != greedy {g3}"
    print("CONSOLIDATION PASS: k=1 sampled == greedy for t in {1.0,0.5,2.0}, seeds {1,7,12345}")

    # --- the genuine DRAW path: k=V=4 (no masking), t=1.0, MINSTD seed 1 ---
    V = len(TOKEN_EMBD)
    smp_s1 = generate_sampled(seed, layers2, 1.0, V, 1, 3)
    print(f"\nSAMPLED generate(seed {seed}, t=1.0, k={V}, prng_seed=1, 3) = {smp_s1}")

    # show the first step's shaped distribution + the draw, for the band's grounding
    probs0 = topk_mask(softmax(temperature(logits_at(seed, layers2), 1.0)), V)
    u0 = uniform(minstd(1))
    print(f"  step0 probs = {[round(p, 6) for p in probs0]}  u0 = {round(u0, 6)}  -> token {cdf_pick(probs0, u0)}")

    # --- single-step draw == the sampling.fk primitive (smp-sample) on the same shaped probs ---
    first_tok = generate_sampled(seed, layers2, 1.0, V, 1, 1)[-1]
    assert first_tok == cdf_pick(probs0, u0), "loop's step-1 draw != smp-sample(probs, uniform(minstd(seed)))"
    print(f"  step-1 draw {first_tok} == smp-sample(probs0, uniform(minstd(1)))  (no double-advance)")

    # --- seed-dependence: a different PRNG seed yields a different sampled sequence ---
    smp_s7 = generate_sampled(seed, layers2, 1.0, V, 7, 3)
    print(f"\nseed-dependence: prng_seed 1 -> {smp_s1} ; prng_seed 7 -> {smp_s7}  (differ: {smp_s1 != smp_s7})")

    # --- input-dependence: a different PROMPT yields a different sampled sequence (same prng seed) ---
    smp_b1 = generate_sampled(seed_b, layers2, 1.0, V, 1, 3)
    print(f"input-dependence: prompt {seed} -> {smp_s1} ; prompt {seed_b} -> {smp_b1}  (differ: {smp_s1[2:] != smp_b1[2:]})")

    # --- prefix stability: a longer sampled gen (same seed) extends the shorter one ---
    smp_s1_2 = generate_sampled(seed, layers2, 1.0, V, 1, 2)
    print(f"\nprefix-stable: sampled(3)[:4] = {smp_s1[:4]} ; sampled(2) = {smp_s1_2}  "
          f"(extends: {smp_s1[:len(smp_s1_2)] == smp_s1_2})")
    assert smp_s1[:len(smp_s1_2)] == smp_s1_2, "sampled prefix instability"

    print("\nALL REFERENCE CHECKS PASS")
