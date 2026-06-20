# endpoint_view_history_order_demo.py — the body of
# translation_cache_service.list_history's ordering, captured as pure Python
# and compiled to a Form recipe.
#
# Contract: order a concept's language views canonical-first, then newest-first.
# Inputs are two parallel lists in the views' original (DB) order:
#   ranks[i] — 0 if view i is the canonical view, 1 otherwise
#   keys[i]  — view i's updated_at as a comparable integer (e.g. epoch micros)
# Output: the original indices reordered so that the canonical view comes first,
# then superseded views by descending key (newest first). The original index is
# the final tiebreak, so the order is TOTAL and deterministic — there is no
# hash-seed-dependent comparison, which is the bug class this recipe removes
# (a hash-dependent order cannot be byte-identical four-way, so it cannot pass
# the witness gate).
#
# Implemented as insertion sort over an index list (no index-store, no pop —
# each insert builds a fresh list via the append-accumulator idiom the kernel
# value-walk carries), keeping the recipe inside the compiled Python subset.


# Comparator: 1 if row a should come before row b, else 0. Written with flat
# `if` statements (no `else`, no compound boolean) so it stays inside the
# python-bmf compiler's currently-supported lift subset. Total order:
# rank ascending, then key descending, then original index ascending.
def view_before(ra, rb, ka, kb, ia, ib):
    b = 0
    if ra < rb:
        b = 1
    if ra == rb:
        if ka > kb:
            b = 1
    if ra == rb:
        if ka == kb:
            if ia < ib:
                b = 1
    return b


def view_history_order(ranks, keys):
    n = len(ranks)
    order = []
    i = 0
    while i < n:
        # Insert i into `order` at the first position whose row is worse than i.
        newlist = []
        inserted = 0
        j = 0
        m = len(order)
        while j < m:
            oj = order[j]
            if inserted == 0:
                if view_before(ranks[i], ranks[oj], keys[i], keys[oj], i, oj) == 1:
                    newlist.append(i)
                    inserted = 1
            newlist.append(oj)
            j = j + 1
        if inserted == 0:
            newlist.append(i)
        order = newlist
        i = i + 1
    return order


# Frozen sample: three views in DB order — a superseded view (ts 300), the
# canonical view (ts 100), and another superseded view (ts 200). Canonical
# first despite its older timestamp (the exact inversion that broke the Python
# sort), then superseded newest-first: [1, 0, 2].
ranks = [1, 0, 1]
keys = [300, 100, 200]

view_history_order(ranks, keys)
