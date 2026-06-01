# endpoint_cost_vector_demo.py — the body of idea_scoring._build_cost_vector,
# captured as pure Python and compiled to a Form recipe.
#
# Cost vector: decompose an idea's estimated_cost into CC resource types.
# Each component is a fixed fraction of the total, rounded to 4 places:
#   compute_cc          = round(ec * 0.60, 4)
#   infrastructure_cc   = round(ec * 0.15, 4)
#   human_attention_cc  = round(ec * 0.25, 4)
#   opportunity_cc      = 0.0   (reserved — no decomposition rule yet)
#   external_cc         = 0.0   (reserved — no decomposition rule yet)
#   total_cc            = round(ec, 4)
#
# This route is unlocked by the round_ndigits native (PR #2320): the
# adapter lowers Python's two-arg `round(x, 4)` to the kernel native
# `round_ndigits`, which replicates CPython's round() for floats EXACTLY
# (rounds the exact decimal value half-to-even at n places). The prior
# round-half-up shim diverged from CPython on 71,860 of 4M cost/value
# components; round_ndigits diverges 0/4M. The decimal cases that exposed
# the divergence — e.g. ec=33.333 → ec*0.25 = 8.33325 → 8.3332 (NOT
# 8.3333) — now match the bit across all runtimes.
#
# The result is a LIST of the six components in struct order; the FastAPI
# route assembles the named CostVector from the positional list. Same
# list-returning shape as softmax_weights, now carrying round().


def cost_vector(estimated_cost):
    compute_cc = round(estimated_cost * 0.60, 4)
    infrastructure_cc = round(estimated_cost * 0.15, 4)
    human_attention_cc = round(estimated_cost * 0.25, 4)
    opportunity_cc = 0.0
    external_cc = 0.0
    total_cc = round(estimated_cost, 4)
    return [
        compute_cc,
        infrastructure_cc,
        human_attention_cc,
        opportunity_cc,
        external_cc,
        total_cc,
    ]


# Endpoint's frozen sample input — the decimal value that EXPOSED the
# round-half-up divergence. estimated_cost = 33.333:
#   compute_cc         = round(19.9998,   4) = 19.9998
#   infrastructure_cc  = round(4.99995,   4) = 4.9999  (half-to-even down)
#   human_attention_cc = round(8.33325,   4) = 8.3332  (half-to-even down)
#   total_cc           = round(33.333,    4) = 33.333
estimated_cost = 33.333

cost_vector(estimated_cost)
