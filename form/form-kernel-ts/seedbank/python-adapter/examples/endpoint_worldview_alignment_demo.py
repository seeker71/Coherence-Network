# endpoint_worldview_alignment_demo.py — BELIEF-RESONANCE WORLDVIEW COSINE over two
# parallel float vectors, the computational core of belief_service._score_worldview_alignment
# in api/app/services/belief_service.py. This is COSINE SIMILARITY:
#   dot(a, b) / (||a|| * ||b||), clamped to [0.0, 1.0], with a 0.5 zero-denom guard.
# The geometric counterpart to tag_match_score's set-membership and concept_match_score's
# substring fold — here the two belief profiles are points in axis-space and the score is
# the cosine of the angle between them.
#
# THE HONEST SEAM (mirrors how _score_worldview_alignment decomposes). The function is:
#   raw_idea_axes = idea_props.get("worldview_axes") or {}
#   idea_axes = {k: float(v) for k, v in raw_idea_axes.items() if k in _DEFAULT_AXES}
#   if not idea_axes: return 0.5, []
#   dot = norm_contributor = norm_idea = 0.0
#   for axis in BeliefAxis:                       # FIXED enum, fixed order
#       cv = profile.worldview_axes.get(axis.value, 0.0)
#       iv = idea_axes.get(axis.value, 0.0)
#       dot += cv*iv; norm_contributor += cv*cv; norm_idea += iv*iv
#       if cv > 0.3 and iv > 0.3: matched_axes.append(axis.value)
#   denom = (norm_contributor ** 0.5) * (norm_idea ** 0.5)
#   score = dot / denom if denom > 0 else 0.5
#   return max(0.0, min(1.0, score)), matched_axes
# Two capabilities welded together:
#   (a) DICT→VECTOR PROJECTION + matched_axes NAMING — BeliefAxis is a FIXED enum
#       (scientific, spiritual, pragmatic, holistic, relational, systemic — verbatim from
#       api/app/models/belief.py). The host projects both dicts into PARALLEL float vectors
#       in that fixed axis order: contributor_vec[i] = profile.worldview_axes.get(axis_i, 0.0),
#       idea_vec[i] = idea_axes.get(axis_i, 0.0) (after the _DEFAULT_AXES filter + float()
#       coercion). This is host-side — dict-as-data, the filtering-adjacent seam. The
#       empty-idea_axes guard (→0.5) and the matched_axes naming (cv>0.3 AND iv>0.3, returns
#       string axis names) also stay host-side: matched_axes is a naming side-output, not the
#       scalar score. The dict projection dissolves at the bridge — the recipe never sees a dict.
#   (b) THE COSINE — given the two parallel float vectors, dot + both sums-of-squares in one
#       parallel index walk, sqrt each norm, guarded ratio (denom>0 else 0.5), clamp [0,1].
#       This is what the recipe runs.
#
# THE COSINE, source-verified against _score_worldview_alignment (shape confirmed):
#   dot = Σ a[i]*b[i]; norm_a = Σ a[i]*a[i]; norm_b = Σ b[i]*b[i]
#   denom = sqrt(norm_a) * sqrt(norm_b)
#   score = dot / denom  if denom > 0  else  0.5
#   return max(0.0, min(1.0, score))
# The zero-denom guard returns 0.5 (a zero-length vector → 0.5, matching the host); the
# clamp is max(0.0, min(1.0, _)). The empty-idea_axes → 0.5 branch lives host-side (it
# fires before any vector is built). These are read verbatim from the source.
#
# Why math.sqrt (not ** 0.5) in the recipe. The source writes norm**0.5; the recipe lowers
# math.sqrt(x) to the kernel's math_sqrt native — IEEE 754 correctly-rounded sqrt, which is
# bit-identical across CPython / form-kernel-rust / kernel-bmf (float-natives-band.fk proves
# sqrt(16)==4.0 tolerance-free; the 1-ULP cross-library caveat applies to math_pow, NOT
# math_sqrt). On the host, x**0.5 == math.sqrt(x) bit-for-bit for the chosen vectors, so the
# _py fallback (which keeps **0.5) and the recipe agree. Floats seed 0.0 so the dot / norm
# accumulators and the ratio are float division throughout — matching CPython's /.
#
# How the vectors travel in: the route's bindings carry contributor_vec / idea_vec as FLOAT
# LISTS (equal length, the fixed axis order). The bridge marshals each via _fk_literal's list
# arm (each element a float literal with a decimal point so the kernel reads it as f64). The
# parallel index walk (while i < n: ... a[i]*b[i] ... a[i]*a[i] ... b[i]*b[i]) lowers to the
# adapter's _get-indexed while fold — the same shape weighted_average ships under, three-way
# value-exact. (a[i]/b[i] are indexed inline rather than bound to loop-locals: the while-
# lowering threads every body-assigned name as loop state, so an `av = a[i]` local would be
# threaded-but-unbound on the initial call. Inlining the subscripts keeps only true loop
# state — dot, norm_a, norm_b, i — threaded, exactly as weighted_average does.)
#
# Three-way clean on VALUE: math_sqrt is full three-way (float-natives-band.fk); the parallel
# index walk lowers to the _get/_while fold weighted_average / cost_vector already ship under
# (Rust+TS value-exact == CPython; Go carries no _get/_iter adapter fold — the same recipe
# situation weighted_average ships under). The frozen sample's cosine is an exact rational
# (0.96) every kernel formats identically; the irrational-cosine edge (1/sqrt(2)) is verified
# bit-identical in the route's parity proof.

import math


def cosine(a, b):
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    i = 0
    n = len(a)
    while i < n:
        dot = dot + a[i] * b[i]
        norm_a = norm_a + a[i] * a[i]
        norm_b = norm_b + b[i] * b[i]
        i = i + 1
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom > 0.0:
        score = dot / denom
    else:
        score = 0.5
    if score > 1.0:
        score = 1.0
    if score < 0.0:
        score = 0.0
    return score


# Endpoint's frozen sample input — two parallel axis-vectors (6 axes, fixed BeliefAxis
# order: scientific, spiritual, pragmatic, holistic, relational, systemic). The vectors
# below give an exact rational cosine:
#   contributor = [0.6, 0.0, 0.8, 0.0, 0.0, 0.0]   (||a|| = 1.0)
#   idea        = [0.8, 0.0, 0.6, 0.0, 0.0, 0.0]   (||b|| = 1.0)
#   dot = 0.6*0.8 + 0.8*0.6 = 0.48 + 0.48 = 0.96
#   score = 0.96 / (1.0 * 1.0) = 0.96
contributor_vec = [0.6, 0.0, 0.8, 0.0, 0.0, 0.0]
idea_vec = [0.8, 0.0, 0.6, 0.0, 0.0, 0.0]

cosine(contributor_vec, idea_vec)
