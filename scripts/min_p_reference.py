#!/usr/bin/env python3
"""min_p_reference.py — the grounding authority for sampling.fk's min-p mask (smp-minp-mask).

min-p is llama.cpp's relative-to-peak sampler (`llama_sampler_min_p_apply`): keep every token whose
probability is at least `p_min` times the PEAK probability, zero the rest, renormalize. Unlike top-k
(by rank) or top-p (by cumulative mass), the cutoff scales with the most-likely token — a flat
distribution keeps many candidates, a peaked one keeps few.

This is the authority OUTSIDE the Form folds that grounds the band's pinned ×1e6 integers (the same
discipline as penalties_reference.py / sampling_draw_reference.py). It self-checks the two consolidation
laws the recipe relies on (p=0 is identity, p=1 keeps only the peak) so the four-way band cannot drift
from llama.cpp's definition.
"""


def min_p_mask(probs, p):
    """threshold = p * max(probs); keep prob >= threshold (inclusive); renormalize over kept mass."""
    thr = p * max(probs)
    kept = [x if x >= thr else 0.0 for x in probs]
    s = sum(kept)
    return [x / s for x in kept]


def ints(v):
    return [round(x * 1e6) for x in v]


def main():
    P = [0.1, 0.5, 0.3, 0.1]  # the sampling-band fixture: a distribution summing to 1, peak 0.5 at idx1

    rows = {
        "minp(P,0.0)": ints(min_p_mask(P, 0.0)),
        "minp(P,0.3)": ints(min_p_mask(P, 0.3)),
        "minp(P,0.7)": ints(min_p_mask(P, 0.7)),
        "minp(P,0.3) sum": round(sum(min_p_mask(P, 0.3)) * 1e6),
        "minp(P,1.0)": ints(min_p_mask(P, 1.0)),
    }
    for k, v in rows.items():
        print(f"{k:18s} = {v}")

    # --- self-checks: the consolidation laws the recipe leans on ---
    assert ints(min_p_mask(P, 0.0)) == ints(P), "p=0 must be the identity (keep all, already normalized)"
    assert ints(min_p_mask(P, 1.0)) == [0, 1000000, 0, 0], "p=1 must keep only the peak (→ greedy)"
    assert rows["minp(P,0.3)"] == [0, 625000, 375000, 0], "thr 0.15 drops both 0.1 tails, renorm by 0.8"
    assert rows["minp(P,0.7)"] == [0, 1000000, 0, 0], "thr 0.35 drops 0.3 too — relative-to-peak"
    assert rows["minp(P,0.3) sum"] == 1000000, "the mask output is a renormalized distribution"
    print("\nall self-checks pass — band pins match llama.cpp min_p definition")


if __name__ == "__main__":
    main()
