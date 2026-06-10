# endpoint_nodeid_compatibility_demo.py — the body of
# /api/utils/nodeid_compatibility, captured as pure Python and compiled to a
# Form recipe.
#
# Sibling of endpoint_nodeid_distance_demo: that measures L1 distance between
# two NodeIDs; this measures coordinate AGREEMENT — how many of the four
# coordinates (package, level, type, instance) two cells share, a 0..4 score.
# It is the kernel of the substrate's view-through-blueprint compatibility
# check: two NodeIDs sharing more coordinates are more structurally
# interchangeable. Pure integer comparison; the substrate stays a numeric
# lattice, not a query language.
#
# Three runtimes produce identical results:
#   - CPython
#   - kernel-bmf-run
#   - form-kernel-rust


def match1(x, y):
    if x == y:
        return 1
    return 0


def compatibility(a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst):
    c = match1(a_pkg, b_pkg) + match1(a_lvl, b_lvl)
    c = c + match1(a_type, b_type) + match1(a_inst, b_inst)
    return c


# Endpoint's frozen sample input — compatibility between two real lattice
# positions: a Memory cell at (1, 5, 4, 1) and another at (1, 4, 4, 7).
# package and type match, level and instance differ. Expected: 2.
a_pkg = 1
a_lvl = 5
a_type = 4
a_inst = 1
b_pkg = 1
b_lvl = 4
b_type = 4
b_inst = 7

compatibility(a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst)
