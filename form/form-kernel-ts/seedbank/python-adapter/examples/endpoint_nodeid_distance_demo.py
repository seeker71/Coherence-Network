# endpoint_nodeid_distance_demo.py — the body of /api/utils/nodeid_distance,
# captured as pure Python and compiled to a Form recipe.
#
# Second endpoint transmuted under the @serve_via_kernel habit. The
# substrate locates every cell at a NodeID(package, level, type, instance).
# Manhattan distance over those four coordinates is the cheapest
# structural-proximity signal — useful for "what's near this cell?"
# without crossing a graph traversal. Pure integer arithmetic; the
# substrate stays a numeric lattice, not a query language.
#
# Three runtimes produce identical results:
#   - CPython
#   - TS evalPython
#   - form-kernel-rust


def manhattan(a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst):
    d = abs(a_pkg - b_pkg) + abs(a_lvl - b_lvl)
    d = d + abs(a_type - b_type) + abs(a_inst - b_inst)
    return d


# Endpoint's frozen sample input — distance between two real lattice
# positions: a Memory cell at (1, 5, 4, 1) and another at (1, 4, 4, 7).
# Expected: |0| + |1| + |0| + |6| = 7.
a_pkg = 1
a_lvl = 5
a_type = 4
a_inst = 1
b_pkg = 1
b_lvl = 4
b_type = 4
b_inst = 7

manhattan(a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst)
