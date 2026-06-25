#!/usr/bin/env python3
"""sampling_draw_reference.py — independent reference for sampling.fk's DRAW half.

The deterministic FILTER half of sampling (temperature/softmax/top-k/top-p) is
proven by sampling-band. What that band explicitly punts is the DRAW: turning a
filtered distribution into an actual token id. The claim "the RNG is not a
recipe" is false — a counter PRNG is pure integer arithmetic, fully
deterministic, and four-way provable. This reference pins:

  1. MINSTD (Park-Miller) — state' = (16807 * state) mod 2147483647 — against
     its PUBLISHED canonical sequence (an authoritative external reference, not
     a value we emitted from our own recipe).
  2. u(state) = state / 2147483647.0  in [0,1).
  3. inverse-CDF sample(probs, u): first index whose cumulative mass > u.
  4. the greedy-consolidation law: a peaked distribution draws its argmax for
     EVERY u — sampling reduces to greedy with no parallel path.

Integers are reduced ×1e6 and rounded for bit-exact equality pinning, exactly
as sampling-band does.
"""

MINSTD_A = 16807
MINSTD_M = 2147483647  # 2^31 - 1, Mersenne prime


def minstd(state):
    return (MINSTD_A * state) % MINSTD_M


def minstd_seq(seed, n):
    s = seed
    out = []
    for _ in range(n):
        s = minstd(s)
        out.append(s)
    return out


def u_of(state):
    return state / float(MINSTD_M)


def sample(probs, u):
    """First index i where cumulative sum probs[0..i] > u."""
    cum = 0.0
    for i, p in enumerate(probs):
        cum += p
        if cum > u:
            return i
    return len(probs) - 1  # u rounded up to total mass; last bucket


def draw_seq(probs, seed, n):
    """Advance MINSTD n times, draw a token each step. Returns (states, tokens)."""
    s = seed
    states, tokens = [], []
    for _ in range(n):
        s = minstd(s)
        states.append(s)
        tokens.append(sample(probs, u_of(s)))
    return states, tokens


def r6(x):
    return round(x * 1_000_000)


if __name__ == "__main__":
    # 1. MINSTD canonical sequence from seed 1 (published Park-Miller values)
    seq = minstd_seq(1, 6)
    print("minstd(seed=1) x6:", seq)
    assert seq[0] == 16807, seq
    assert seq[1] == 282475249, seq
    assert seq[2] == 1622650073, seq
    assert seq[3] == 984943658, seq
    assert seq[4] == 1144108930, seq
    assert seq[5] == 470211272, seq

    # 2. u values for those states, x1e6 rounded
    print("u x1e6:", [r6(u_of(s)) for s in seq])

    # 3. inverse-CDF on P = [0.1, 0.5, 0.3, 0.1], cumulative [0.1,0.6,0.9,1.0]
    P = [0.1, 0.5, 0.3, 0.1]
    states, tokens = draw_seq(P, 1, 6)
    print("draw_seq(P, seed=1) tokens:", tokens)
    # hand-check a couple
    # s1=16807   u=7.8e-6   -> cum[0]=0.1 > u -> 0
    # s2=282475249 u=0.13154 -> cum[1]=0.6 > u -> 1
    # s3=1622650073 u=0.75560 -> cum[2]=0.9 > u -> 2
    assert tokens[0] == 0, tokens
    assert tokens[1] == 1, tokens
    assert tokens[2] == 2, tokens

    # 4. greedy-consolidation: peaked dist [0,0,1,0] draws index 2 for every u
    PEAK = [0.0, 0.0, 1.0, 0.0]
    peak_tokens = [sample(PEAK, u_of(s)) for s in seq]
    print("peak draws (must all be 2 = argmax):", peak_tokens)
    assert all(t == 2 for t in peak_tokens), peak_tokens

    # 5. a 2-token distribution sweep to show u<0.5 -> 0, u>=0.5 -> 1
    B = [0.5, 0.5]  # cumulative [0.5, 1.0]
    print("binary draws:", [sample(B, u_of(s)) for s in seq])

    print("\nALL REFERENCE ASSERTS PASS")
    # Emit the band pins
    print("\n--- band pins ---")
    print("minstd6 =", seq)
    print("u6_x1e6 =", [r6(u_of(s)) for s in seq])
    print("drawP6  =", tokens)
