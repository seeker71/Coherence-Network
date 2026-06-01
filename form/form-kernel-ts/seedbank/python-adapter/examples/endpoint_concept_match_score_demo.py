# endpoint_concept_match_score_demo.py — STRING-MEMBERSHIP SCORING over already-
# tokenized keyword lists, the computational half of the concept-matching score
# in api/app/services/concept_auto_tagger.py::_score_concept. This opens the
# text-scoring family the kernel-served-route ledger named as the next gate: the
# prior routes fold INTEGER and FLOAT fields over records; this is the FIRST to
# fold STRING MEMBERSHIP — `kw in text` lowered to `str_find(text, kw, 0) >= 0`
# over the already-banked str_find native (three-way value-identical for ASCII
# across Rust/Go/TS; see string-natives-band.fk).
#
# THE HONEST SEAM (mirrors how compute_idea_metrics was decomposed). _score_concept
# is two capabilities welded together:
#   (a) TEXT PREPROCESSING — _extract_keywords runs `re.findall(r"\b[a-zA-Z]{3,}\b",
#       text.lower())` + stopword filtering + dedup; the score body also assembles
#       concept_text (a lowercased concatenation of name + description + keywords)
#       and idea_text (" ".join(keywords)), and lowercases the concept's own
#       keywords and name. This is REGEX + string preprocessing — text-shaping,
#       NOT a kernel computation. It stays host-side; forcing regex tokenization
#       into the kernel is the wrong build (the residual host-side capability the
#       ledger names precisely).
#   (b) THE SCORING — given the already-tokenized keyword lists and the assembled
#       strings, the bidirectional string-membership fold + the weighted combine.
#       This is what the recipe runs.
#
# THE SCORING, source-verified against _score_concept (constants confirmed):
#   forward_score = (count of idea keywords found in concept_text) / len(keywords)
#   reverse_score = (count of concept keywords found in idea_text) / len(concept_keywords)
#                   if concept_keywords else 0.0
#   name_bonus    = 0.3 if name_lower in idea_text else 0.0
#   score         = round(min(0.5*forward_score + 0.3*reverse_score + name_bonus, 1.0), 4)
# The forward/reverse weights (0.5, 0.3), the name bonus (0.3), the 1.0 ceiling,
# and the round(_, 4) are read verbatim from the source. The empty-keywords guard
# (`if not keywords: return 0.0`) stays host-side — match_concepts never reaches
# the scorer with empty keywords (it returns [] first), so the recipe is only
# ever called with len(keywords) > 0.
#
# Why the hit counters seed 0.0 (a float). Python's `/` is always float; the
# kernel's `div` is integer division on two ints and float division when either
# operand is a float. forward_hits / len(keywords) must be float division to match
# CPython, so the counter is a float accumulator (0.0 seed, + 1.0 per hit) and the
# ratio walks (float, int) → float. This is the same float-coercion discipline
# simpson_diversity / cost_vector use; mixed int/float div promotes three-way
# (verified [0.333…, 0, 0.333…] across Rust/Go/TS).
#
# How the lists travel in: the route's bindings carry keywords / concept_keywords
# as STRING LISTS and concept_text / idea_text / name_lower as STRINGS. The bridge
# marshals a list[str] to a kernel list via _fk_literal's list arm (each element a
# quoted string literal) and a str to a quoted scalar; the recipe iterates via the
# head/tail fold the python-adapter lowers `for needle in needles` into and tests
# membership with str_find. (Strings are scalars and lists are banked, so the
# string-list + string bindings marshal cleanly — verified end to end.)
#
# Three-way clean on VALUE: the frozen sample is chosen so the score is a NON-
# integer float (0.825), which every kernel formats identically. The recipe path
# itself (the `for needle in needles` fold) lowers to the adapter's _iter head/tail
# fold, which Go's kernel does not carry (Go has no _iter/_dict_* adapter natives —
# the same Rust+TS recipe situation idea_grounded_cost_sum / grounded_cost / etc.
# already ship under); the STRING NATIVES it calls (str_find, str_len) are full
# three-way. So: string-natives three-way (string-natives-band.fk); recipe
# Rust+TS value-exact == CPython.


def match_count(needles, haystack):
    hits = 0.0
    for needle in needles:
        if str_find(haystack, needle, 0) >= 0:
            hits = hits + 1.0
    return hits


def score(keywords, concept_text, concept_keywords, idea_text, name_lower):
    forward_hits = match_count(keywords, concept_text)
    forward_score = forward_hits / len(keywords)
    reverse_score = 0.0
    if len(concept_keywords) > 0:
        reverse_hits = match_count(concept_keywords, idea_text)
        reverse_score = reverse_hits / len(concept_keywords)
    name_bonus = 0.0
    if str_find(idea_text, name_lower, 0) >= 0:
        name_bonus = 0.3
    raw = 0.5 * forward_score + 0.3 * reverse_score + name_bonus
    if raw > 1.0:
        raw = 1.0
    return round(raw, 4)


# Endpoint's frozen sample input — host-tokenized keyword lists + assembled
# strings for one (idea, concept) pair.
#   forward: energy / flow / coherence appear in concept_text; xyz does not
#            → 3/4 = 0.75
#   reverse: energy appears in idea_text; tissue does not → 1/2 = 0.5
#   name:    "energy flow" appears contiguous in idea_text → bonus 0.3
#   raw = 0.5*0.75 + 0.3*0.5 + 0.3 = 0.375 + 0.15 + 0.3 = 0.825
#   score = round(min(0.825, 1.0), 4) = 0.825
keywords = ["energy", "flow", "coherence", "xyz"]
concept_text = "energy flows as coherence through the body field"
concept_keywords = ["energy", "tissue"]
idea_text = "energy flow coherence xyz"
name_lower = "energy flow"

score(keywords, concept_text, concept_keywords, idea_text, name_lower)
