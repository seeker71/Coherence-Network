#!/usr/bin/env python3
"""llama_penalize_generate_reference.py — independent pure-libm fp64 reference for the llama
(decoder-only, GQA) autoregressive PENALIZED-SAMPLED generation loop (brick: wire pen-apply into
lg-generate-sampled so a local llama stops looping).

The sampled generation loop is four-way (llama-sample-generate.fk, #3654, lg-generate-sampled): each
step the logits are shaped (temperature -> softmax -> top-k) and a token is DRAWN with a seeded MINSTD
counter PRNG. But the loop has NO memory: nothing discourages emitting the same token forever, so an
unshaped local llama degenerates into a loop (the greedy baseline on this fixture is [0,1,1,1,1] —
token 1 repeated). Serving's first defense is the penalty pass llama.cpp applies to the LOGITS BEFORE
temperature (llama_sampler_penalties_apply, == penalties.fk, #3677): for each token id whose count in
the penalty window (the last-n ids) is > 0, push its logit down

    count = occurrences of token id i in the last-n window
    if count > 0:
      repeat:  logit = (logit <= 0) ? logit * penalty_repeat : logit / penalty_repeat
      freq:    logit -= count * penalty_freq
      present: logit -= penalty_present

This reference grounds the WIRING that threads pen-apply into the sampled loop: at each step penalize
the logits over the last-n window of the running ids, THEN shape + draw, append, recurse.

The LOAD-BEARING law (core-abstraction-first): penalty (penalty_repeat=1, penalty_freq=0,
penalty_present=0) is the IDENTITY — pen-apply leaves every logit untouched, so the penalized loop
reduces EXACTLY to lg-generate-sampled (#3654); and with k=1 that further reduces to the greedy loop
lg-generate (#3649). The unpenalized loop is the (1,0,0) special case, not a parallel path. A penalty
window of last_n=0 is the empty window: no token is counted, so even big knobs are identity. These
reductions ground the whole penalized stack+logits+penalty+filter+selection by EQUIVALENCE to loops
already proven four-way — no new reference needed for them.

The genuine PENALTY path (the new behavior) is pinned here: with a repetition penalty active, the loop
that would emit [0,1,1,1,1] breaks the loop and emits different tokens. The PRNG is grounded against
MINSTD's PUBLISHED canonical sequence; the stack/logits reuse the already-four-way llama-generate-band
fixture (embed([0,1]) == the band's published x pins). Shared verbatim with llama_sample_generate_reference.py.
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
    ids = list(seed_ids)
    for _ in range(steps):
        ids.append(argmax(logits_at(ids, layers)))
    return ids


# === the SAMPLING DRAW half (== sampling.fk, #3651) ===
def temperature(logits, t):
    return [v / t for v in logits]


def softmax(logits):
    m = max(logits)
    es = [math.exp(v - m) for v in logits]
    z = sum(es)
    return [e / z for e in es]


def kth_largest(xs, k):
    work = list(xs)
    for _ in range(k):
        work.remove(max(work))
    return max(work)


def topk_mask(probs, k):
    thr = kth_largest(probs, k - 1)
    kept = [p if p >= thr else 0.0 for p in probs]
    z = sum(kept)
    return [p / z for p in kept]


def minstd(state):
    return (16807 * state) % 2147483647


def uniform(state):
    return state / 2147483647.0


def cdf_pick(probs, u):
    cum = 0.0
    for idx, p in enumerate(probs):
        cum += p
        if cum > u:
            return idx
    return len(probs) - 1


# === the PENALTY pass (== penalties.fk, #3677, == llama_sampler_penalties_apply) ===
def pen_count(ids, tid):
    return float(sum(1 for i in ids if i == tid))


def pen_one(logit, count, pr, pf, pp):
    if count > 0.0:
        rep = logit * pr if logit <= 0.0 else logit / pr
        return rep - (count * pf + pp)
    return logit


def pen_apply(logits, window_ids, pr, pf, pp):
    return [pen_one(logits[i], pen_count(window_ids, i), pr, pf, pp) for i in range(len(logits))]


def last_n(xs, n):
    if n >= len(xs):
        return list(xs)
    return list(xs[len(xs) - n:])


# === the WIRING: penalize the logits over the last-n window, THEN shape, THEN draw ===
def penalized_probs(ids, layers, t, k, pr, pf, pp, win):
    logits = logits_at(ids, layers)
    pen = pen_apply(logits, last_n(ids, win), pr, pf, pp)
    return topk_mask(softmax(temperature(pen, t)), k)


def generate_penalized(seed_ids, layers, t, k, pr, pf, pp, win, state, steps):
    """the PENALIZED-SAMPLED loop: penalize logits over the last-n window, shape, advance the PRNG
    once, draw, append, recurse — threading (ids, PRNG state)."""
    ids = list(seed_ids)
    for _ in range(steps):
        probs = penalized_probs(ids, layers, t, k, pr, pf, pp, win)
        state = minstd(state)
        ids.append(cdf_pick(probs, uniform(state)))
    return ids


def generate_sampled(seed_ids, layers, t, k, state, steps):
    """the unpenalized sampled loop (== lg-generate-sampled, #3654) for the equivalence checks."""
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

    s, seq = 1, []
    for _ in range(6):
        s = minstd(s)
        seq.append(s)
    assert seq == [16807, 282475249, 1622650073, 984943658, 1144108930, 470211272], seq
    print(f"PRNG SELF-CHECK PASS: MINSTD seq from seed 1 = {seq[:3]}...")

    # penalties identity self-check
    L = [1.0, 2.0, 0.0, -0.5, 0.5]
    assert pen_apply(L, [1, 1, 3, 2], 1.0, 0.0, 0.0) == L, "penalty identity broken"
    print("PENALTY IDENTITY SELF-CHECK PASS: pen_apply(L, win, 1.0, 0.0, 0.0) == L")

    layers2 = [L0, L1]
    seed = [0, 1]
    seed_b = [1, 0]
    V = len(TOKEN_EMBD)

    # --- greedy baseline: the degenerate loop [0,1,1,1,1] (token 1 forever) ---
    g3 = generate(seed, layers2, 3)
    print(f"\ngreedy generate(seed {seed}, 3) = {g3}  (degenerate: token 1 repeats)")

    # --- CONSOLIDATION (A): identity penalty == lg-generate-sampled (genuine draw k=V) ---
    for st in (1, 7, 12345):
        u = generate_sampled(seed, layers2, 1.0, V, st, 3)
        p = generate_penalized(seed, layers2, 1.0, V, 1.0, 0.0, 0.0, 64, st, 3)
        assert p == u, f"identity penalty k=V seed={st}: {p} != sampled {u}"
    print("CONSOLIDATION A PASS: identity penalty (1,0,0) == lg-generate-sampled, k=V, seeds {1,7,12345}")

    # --- CONSOLIDATION (B): identity penalty + k=1 == greedy ---
    for st in (1, 7, 12345):
        p1 = generate_penalized(seed, layers2, 1.0, 1, 1.0, 0.0, 0.0, 64, st, 3)
        assert p1 == g3, f"identity penalty k=1 seed={st}: {p1} != greedy {g3}"
    print("CONSOLIDATION B PASS: identity penalty + k=1 == greedy [0,1,1,1,1], seeds {1,7,12345}")

    # --- WINDOW: last_n=0 is the empty window -> identity even with big knobs ---
    for st in (1, 7):
        pw = generate_penalized(seed, layers2, 1.0, 1, 100.0, 5.0, 5.0, 0, st, 3)
        assert pw == g3, f"last_n=0 big knobs seed={st}: {pw} != greedy {g3} (empty window must be identity)"
    print("WINDOW PASS: last_n=0 (empty window) == greedy even with (pr=100,pf=5,pp=5)")

    # --- THE NON-LOOPING HEADLINE: k=1 + repeat penalty breaks [0,1,1,1,1] ---
    pr_big = 100.0
    pb = generate_penalized(seed, layers2, 1.0, 1, pr_big, 0.0, 0.0, 64, 1, 3)
    print(f"\nNON-LOOPING: penalized k=1 (pr={pr_big}) generate(seed {seed}, 3) = {pb}")
    assert pb != g3, f"penalty did not change the sequence: {pb} == greedy {g3}"
    gen = pb[len(seed):]
    assert not all(t == 1 for t in gen), f"penalized loop still collapsed to token 1: {gen}"
    print(f"  generated tokens {gen} — NOT all token 1; the repetition penalty broke the loop")
    # show the step-0 penalized logits / probs for the band's grounding
    lg0 = logits_at(seed, layers2)
    win0 = last_n(seed, 64)
    pen0 = pen_apply(lg0, win0, pr_big, 0.0, 0.0)
    print(f"  step0 logits   = {[pin(v) for v in lg0]}")
    print(f"  step0 window   = {win0}  (token 1 has count {pen_count(win0, 1)})")
    print(f"  step0 penalized= {[pin(v) for v in pen0]}  -> argmax {argmax(pen0)} (greedy was {argmax(lg0)})")

    # --- SINGLE-STEP COMPOSE: the loop's penalized step-1 draw == cdf_pick on the penalized probs ---
    probs0 = penalized_probs(seed, layers2, 1.0, V, 1.2, 0.1, 0.05, 64)
    u0 = uniform(minstd(100000))
    step1 = generate_penalized(seed, layers2, 1.0, V, 1.2, 0.1, 0.05, 64, 100000, 1)[-1]
    print(f"\nCOMPOSE: full-trio penalized probs0 = {[round(p, 6) for p in probs0]}  u0={round(u0,6)}")
    print(f"  loop step-1 draw {step1} == cdf_pick(probs0, u0) {cdf_pick(probs0, u0)}")
    assert step1 == cdf_pick(probs0, u0), "loop step-1 draw != cdf_pick(penalized probs, uniform(minstd(seed)))"

    # --- WINDOW-COUNT DEPENDENCE: more occurrences -> stronger frequency push.
    #     freq penalty subtracts count*pf, so a token appearing twice is pushed further than once. ---
    ids_one = [0, 1]          # token 1 count 1
    ids_two = [0, 1, 2, 1]    # token 1 count 2 (also token 2 once)
    lg_o = logits_at([0, 1], layers2)   # same logits position for comparison of the penalty math
    p_one = pen_apply(lg_o, ids_one, 1.0, 1.0, 0.0)[1]   # freq-only, count 1
    p_two = pen_apply(lg_o, ids_two, 1.0, 1.0, 0.0)[1]   # freq-only, count 2
    print(f"\nWINDOW-COUNT: logit[1]={pin(lg_o[1])} ; freq count1 -> {pin(p_one)} ; count2 -> {pin(p_two)}")
    assert p_two < p_one < lg_o[1], "frequency penalty must scale with the window count"
    print(f"  count2 pushed further than count1 (freq penalty scales with occurrences)")

    # --- INPUT-DEPENDENCE: same penalty + PRNG seed, different prompt -> different draw ---
    dA = generate_penalized(seed,   layers2, 1.0, V, 1.2, 0.1, 0.05, 64, 100000, 1)[-1]
    dB = generate_penalized(seed_b, layers2, 1.0, V, 1.2, 0.1, 0.05, 64, 100000, 1)[-1]
    print(f"\nINPUT-DEPENDENCE: prompt {seed} -> {dA} ; prompt {seed_b} -> {dB}  (differ: {dA != dB})")

    print("\nALL REFERENCE CHECKS PASS")
