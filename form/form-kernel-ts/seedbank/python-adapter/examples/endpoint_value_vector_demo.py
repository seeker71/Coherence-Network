# endpoint_value_vector_demo.py — the body of idea_scoring._build_value_vector,
# captured as pure Python and compiled to a Form recipe.
#
# Value vector: decompose an idea's potential_value into CC value types.
# Each component is a fixed fraction of the total, rounded to 4 places:
#   adoption_cc          = round(pv * 0.50, 4)
#   lineage_cc           = round(pv * 0.30, 4)
#   friction_avoided_cc  = round(pv * 0.20, 4)
#   revenue_cc           = 0.0   (reserved — no decomposition rule yet)
#   total_cc             = round(pv, 4)
#
# Sibling of cost_vector — same round_ndigits unlock (PR #2320). The
# adapter lowers Python's two-arg `round(x, 4)` to the kernel native
# `round_ndigits`, which replicates CPython's round() for floats EXACTLY.
# The 0.x25-tail values that exposed the round-half-up divergence now match
# the bit across CPython, the Form-native walker, and form-kernel-rust.
#
# The result is a LIST of the five components in struct order; the FastAPI
# route assembles the named ValueVector from the positional list.


def value_vector(potential_value):
    adoption_cc = round(potential_value * 0.50, 4)
    lineage_cc = round(potential_value * 0.30, 4)
    friction_avoided_cc = round(potential_value * 0.20, 4)
    revenue_cc = 0.0
    total_cc = round(potential_value, 4)
    return [
        adoption_cc,
        lineage_cc,
        friction_avoided_cc,
        revenue_cc,
        total_cc,
    ]


# Endpoint's frozen sample input — a decimal value that exercises round's
# half-to-even tie-break. potential_value = 9.205:
#   adoption_cc         = round(4.6025,   4) = 4.6025
#   lineage_cc          = round(2.7615,   4) = 2.7615
#   friction_avoided_cc = round(1.841,    4) = 1.841
#   total_cc            = round(9.205,    4) = 9.205
potential_value = 9.205

value_vector(potential_value)
