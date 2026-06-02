# endpoint_coherence_summary_score_demo.py — the COVERAGE/SCORE REDUCTION of
# collective_health_service._coherence_summary, transmuted to a Form recipe.
# Another per-slice scoring transmutation built entirely from banked
# capabilities: the guarded ratio (safe_ratio's `if denom > 0 else default`),
# the neutral-score guard (`if task_count <= 0 → 0.5 else clamp01`), the
# two-sided clamp via comparison-branches, and round_ndigits. Nothing new
# crosses the kernel boundary — this folds the same shapes grounded_value and
# tag_match_score already prove into the collective-health domain.
#
# THE HONEST DECOMPOSITION. _coherence_summary derives, over the task list:
#   (a) the COUNTS — task_count, target_state_count, evidence_count,
#       task_card_count, and the task_card_scores list (its sum + len). Each is
#       produced by walking the heterogeneous `context` dicts on each task and
#       counting / accumulating presence conditions. This dict-walk over a
#       collection is the filtering-adjacent capability that stays HOST-SIDE BY
#       DESIGN — the host produces the scalar counts and the scores sum/len.
#   (b) the NUMERIC REDUCTION — given those counts, the four coverage ratios
#       (each a guarded ratio over task_count, the quality over the scores len),
#       the weighted-sum score with the task_count==0 neutral guard and the
#       [0.0, 1.0] clamp, and round(_, 4) on each output. This recipe runs (b).
#
# Given the host-derived counts the recipe computes EXACTLY what
# _coherence_summary computes (verified against the source — the _safe_ratio
# guard `denominator <= 0 → default`, _score_with_neutral `task_count <= 0 →
# 0.5 else _clamp01`, the 0.35/0.30/0.20/0.15 weights, and round(_, 4) on the
# four coverages + score):
#   target_state_coverage = safe_ratio(target_state_count, task_count)
#   evidence_coverage      = safe_ratio(evidence_count, task_count)
#   task_card_coverage     = safe_ratio(task_card_count, task_count)
#   task_card_quality      = safe_ratio(task_card_scores_sum, task_card_scores_len)
#   score = 0.5 if task_count == 0 else clamp01(
#       0.35*target_state_coverage + 0.30*task_card_quality
#       + 0.20*task_card_coverage + 0.15*evidence_coverage)
#   → [round(score, 4), round(target_state_coverage, 4),
#      round(task_card_coverage, 4), round(task_card_quality, 4),
#      round(evidence_coverage, 4)]
#
# The seam: the kernel keeps the most NUMERIC computation (ratios + score +
# round); the host keeps the dict-walk over the task collection that produces
# the counts — held host-side BY DESIGN, the heterogeneous-dict-over-collection
# extraction, not a missing kernel native. _safe_ratio's guard is `denominator
# <= 0`; the recipe's `if denom > 0` is its exact complement (the host never
# passes a negative count, so > 0 and the <= 0 default-branch agree). The float
# force `(num + 0.0) / (denom + 0.0)` mirrors shannon_entropy's div quirk so an
# integer-count ratio still divides as a float across all three kernels.
#
# Banked capabilities this folds together:
#   - the guarded ratio (safe_ratio: `if denom > 0 else default`)
#   - the neutral-score guard (`if task_count <= 0 → 0.5`)
#   - the two-sided [0.0, 1.0] clamp as nested max2/min2 comparison-branches
#   - a four-term weighted sum and round_ndigits on each output
#
# Three-way clean on VALUE and PRINT: the frozen sample (task_count=10) yields
# all non-integer floats so every kernel formats identically:
#   target_state_coverage = 7/10  = 0.7
#   evidence_coverage      = 5/10  = 0.5
#   task_card_coverage     = 6/10  = 0.6
#   task_card_quality      = 4.5/6 = 0.75
#   score = clamp01(0.35*0.7 + 0.30*0.75 + 0.20*0.6 + 0.15*0.5)
#         = clamp01(0.245 + 0.225 + 0.12 + 0.075) = 0.665
# The final list is [0.665, 0.7, 0.6, 0.75, 0.5].


def min2(a, b):
    if a > b:
        return b
    return a


def max2(a, b):
    if a > b:
        return a
    return b


def clamp01(x):
    return max2(0.0, min2(x, 1.0))


def safe_ratio(num, denom):
    if denom > 0:
        return (num + 0.0) / (denom + 0.0)
    return 0.0


def coherence_summary_score(task_count, target_state_count, evidence_count, task_card_count, task_card_scores_sum, task_card_scores_len):
    target_state_coverage = safe_ratio(target_state_count, task_count)
    evidence_coverage = safe_ratio(evidence_count, task_count)
    task_card_coverage = safe_ratio(task_card_count, task_count)
    task_card_quality = safe_ratio(task_card_scores_sum, task_card_scores_len)
    combination = 0.35 * target_state_coverage + 0.30 * task_card_quality + 0.20 * task_card_coverage + 0.15 * evidence_coverage
    score = clamp01(combination) if task_count > 0 else 0.5
    return [
        round(score, 4),
        round(target_state_coverage, 4),
        round(task_card_coverage, 4),
        round(task_card_quality, 4),
        round(evidence_coverage, 4),
    ]


# Endpoint's frozen sample input — host-derived counts for one task slice.
task_count = 10
target_state_count = 7
evidence_count = 5
task_card_count = 6
task_card_scores_sum = 4.5
task_card_scores_len = 6

coherence_summary_score(task_count, target_state_count, evidence_count, task_card_count, task_card_scores_sum, task_card_scores_len)
