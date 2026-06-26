#!/usr/bin/env python3
"""penalties_reference.py — the parity oracle for penalties.fk (the token repetition penalty set).

Mirrors llama.cpp's llama_sampler_penalties_apply (llama-sampling.cpp) exactly: for each token id i
whose occurrence count in the penalty window is > 0,

    repeat:  logit = (logit <= 0) ? logit * penalty_repeat : logit / penalty_repeat
    freq:    logit -= count * penalty_freq
    present: logit -= penalty_present

penalty_repeat=1, penalty_freq=0, penalty_present=0 is the identity (penalties off — llama.cpp default).
The token id IS the logit's position: position i in the logits list is token id i, so count[i] is just
"how many times does i appear in the history ids". The reference is libc fp64 (Python float == IEEE-754
double), the same arithmetic the four-way recipe folds — so the band can pin the values bit-for-bit.

Self-checks a tiny hand-verified case, then emits the expected ×1e6 integers for tests/penalties-band.fk.
"""


def count_occurs(ids, tok):
    return sum(1 for x in ids if x == tok)


def last_n(xs, n):
    if n >= len(xs):
        return list(xs)
    return list(xs[len(xs) - n:])


def penalize(logits, ids, penalty_repeat, penalty_freq, penalty_present):
    out = []
    for i, logit in enumerate(logits):
        c = count_occurs(ids, i)
        if c == 0:
            out.append(logit)
            continue
        if logit <= 0.0:
            logit = logit * penalty_repeat
        else:
            logit = logit / penalty_repeat
        logit = logit - (c * penalty_freq + penalty_present)
        out.append(logit)
    return out


def ints(v):
    return [round(x * 1000000.0) for x in v]


def main():
    # --- fixtures (strange-minimal, every branch covered) ---
    # ids 0..4; L mixes positive (divide branch), exactly-zero (<=0 → multiply branch), and negative.
    L = [1.0, 2.0, 0.0, -0.5, 0.5]
    # history: token 1 twice (count 2 → freq scales), token 2 once (logit 0 boundary), token 3 once;
    # tokens 0 and 4 absent (count 0 → untouched).
    H = [1, 1, 3, 2]
    pr, pf, pp = 1.2, 0.1, 0.05

    # --- claim 0: occurrence counts of ids 0..4 in H ---
    counts = [count_occurs(H, i) for i in range(len(L))]
    assert counts == [0, 2, 1, 1, 0], counts

    # --- claim 1: identity (penalties off) leaves logits unchanged ---
    ident = penalize(L, H, 1.0, 0.0, 0.0)
    assert ints(ident) == ints(L), ident

    # --- claim 2: pure repetition penalty (freq/present off) ---
    rep = penalize(L, H, pr, 0.0, 0.0)
    # id1: 2.0/1.2 ; id2: 0.0*1.2 ; id3: -0.5*1.2 ; id0,id4 untouched
    assert ints(rep) == [1000000, round(2.0 / 1.2 * 1e6), 0, -600000, 500000], ints(rep)

    # --- claim 3: the full trio ---
    full = penalize(L, H, pr, pf, pp)

    # --- claim 4: penalty window (last-n) selection ---
    win2 = last_n(H, 2)          # [3, 2]
    assert win2 == [3, 2], win2
    winAll = last_n(H, 9)        # n >= len → whole list
    assert winAll == H, winAll

    # --- claim 5: full trio over the last-2 window only (id1 now count 0 → untouched) ---
    fullw = penalize(L, win2, pr, pf, pp)

    print("counts        =", counts)
    print("identity x1e6 =", ints(ident))
    print("repeat   x1e6 =", ints(rep))
    print("full     x1e6 =", ints(full))
    print("last_n(H,2)   =", win2)
    print("full_win x1e6 =", ints(fullw))


if __name__ == "__main__":
    main()
