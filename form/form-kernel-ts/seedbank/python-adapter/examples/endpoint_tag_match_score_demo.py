# endpoint_tag_match_score_demo.py — BELIEF-RESONANCE TAG SCORING over two already-
# deduped tag lists, the computational half of belief_service._score_tag_match in
# api/app/services/belief_service.py. This folds EXACT STRING MEMBERSHIP (str_eq
# over a list) — the equality counterpart to concept_match_score's substring
# (str_find) fold. Tags match on equality, not containment, so the membership test
# is str_eq, the COMPARE.EQ native (value-identical for ASCII across Rust/Go/TS).
#
# THE HONEST SEAM (mirrors how _score_tag_match decomposes). The function is:
#   contributor_tags = set(profile.interest_tags); idea_tag_set = set(idea_tags)
#   if not contributor_tags or not idea_tag_set: return 0.5
#   matched = contributor_tags & idea_tag_set
#   return max(0.0, min(1.0, len(matched) / len(contributor_tags)))
# Two capabilities welded together:
#   (a) FIELD EXTRACTION + DEDUP — pulling profile.interest_tags off the
#       BeliefProfile model (the bridge marshals model→dict→record) and reading
#       idea_tags off the idea node, then collapsing each to a set(). This is
#       host-side: Python set() is the cheap dedup, mirroring the filtering-stays-
#       host seam. The route dedups both lists before the recipe runs and passes
#       already-unique string lists in. The model field extraction dissolves at the
#       bridge — the recipe never sees a BeliefProfile.
#   (b) THE SCORING — given the two deduped string lists, the str_eq membership fold
#       (matched = how many unique contributor tags appear in idea_tags) + the ratio
#       + clamp + empty-guard. This is what the recipe runs.
#
# THE SCORING, source-verified against _score_tag_match (shape confirmed):
#   if len(contributor_tags) == 0 or len(idea_tags) == 0: return 0.5
#   matched = count of contributor tags that appear in idea_tags (str_eq)
#   return max(0.0, min(1.0, matched / len(contributor_tags)))
# The empty-guard returns 0.5 (NOT 0.0), the denominator is the deduped
# contributor-tag count (NOT len(idea_tags)), and the clamp is max(0.0, min(1.0, _)).
# These are read verbatim from the source.
#
# Why the hit counter seeds 0.0 (a float). Python's `/` is always float; the
# kernel's `div` is integer division on two ints and float division when either
# operand is a float. matched / len(contributor_tags) must be float division to
# match CPython, so the counter is a float accumulator (0.0 seed, + 1.0 per hit)
# and the ratio walks (float, int) → float. Same float-coercion discipline
# concept_match_score / simpson_diversity use.
#
# How the lists travel in: the route's bindings carry contributor_tags / idea_tags
# as STRING LISTS. The bridge marshals a list[str] to a kernel list via _fk_literal's
# list arm (each element a quoted string literal); an empty list marshals as `(list)`
# so `len` is 0 and the empty-guard fires. The recipe's nested fold (contains_exact
# inner str_eq fold, match_count outer fold) iterates via the head/tail fold the
# python-adapter lowers `for ... in ...` into.
#
# Three-way clean on VALUE: the str_eq native it calls is full three-way; the recipe
# path (the nested `for` fold) lowers to the adapter's _iter head/tail fold, which
# Go's kernel does not carry (Go has no _iter adapter native — the same Rust+TS
# recipe situation concept_match_score / idea_grounded_cost_sum already ship under).
# So: str_eq three-way; recipe Rust+TS value-exact == CPython. The frozen sample
# scores 0.5 (matched 2 of 4) — an exact float every kernel formats identically.


def contains_exact(needle, haystack):
    found = False
    for item in haystack:
        if str_eq(item, needle):
            found = True
    return found


def match_count(needles, haystack):
    hits = 0.0
    for needle in needles:
        if contains_exact(needle, haystack):
            hits = hits + 1.0
    return hits


def score(contributor_tags, idea_tags):
    if len(contributor_tags) == 0:
        return 0.5
    if len(idea_tags) == 0:
        return 0.5
    matched = match_count(contributor_tags, idea_tags)
    ratio = matched / len(contributor_tags)
    if ratio > 1.0:
        ratio = 1.0
    if ratio < 0.0:
        ratio = 0.0
    return ratio


# Endpoint's frozen sample input — two host-deduped tag lists for one
# (contributor, idea) pair.
#   contributor: energy / flow / coherence / field (4 unique tags)
#   idea:        energy / flow (2 unique tags)
#   matched: energy + flow appear → 2; ratio = 2/4 = 0.5
#   score = max(0.0, min(1.0, 0.5)) = 0.5
contributor_tags = ["energy", "flow", "coherence", "field"]
idea_tags = ["energy", "flow"]

score(contributor_tags, idea_tags)
