"""Sense the CTOR-shape neighborhood the Blueprint axis can't see.

Every concept in the body lands at the same Blueprint NodeID — `BID_concept()`
returns one constant. The `/substrate/equivalent` endpoint answers "who
shares this Blueprint?", which for concepts reduces to "who is also a
concept?" — 75-ish cells, indistinguishable.

The CTOR recipe tree carries the actual structural fingerprint. This
script walks each concept's CTOR to a chosen depth, builds a shape
signature, and shows how concepts cluster under the finer relation.

Run as a sensing breath — no kernel changes, no deploy. The question
is whether the geometry is real before we change the body's eyes.

Usage:
    python3 seedbank/ctor-shape-signature-v0/sense.py
    python3 seedbank/ctor-shape-signature-v0/sense.py --depth 1
    python3 seedbank/ctor-shape-signature-v0/sense.py --target lc-pulse

The script reads from the local substrate DB. To populate it first:
    python3 scripts/coh_substrate.py ingest --concepts --structured
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate.kernel import NodeID  # noqa: E402
from app.services.substrate.orm import (  # noqa: E402
    SubstrateNamedCellORM,
    SubstrateNodeORM,
)
from app.services.substrate.substrate_strings import (  # noqa: E402
    lookup_string_value,
)
from app.services.unified_db import session as session_scope  # noqa: E402


# ---------------------------------------------------------------------------
# Shape signature — walk a recipe tree to a chosen depth, build a hashable
# tuple of (category, [(child_category, [...]), ...]) per node.
# ---------------------------------------------------------------------------


def _node_row(session, nid: NodeID) -> Optional[SubstrateNodeORM]:
    return (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=nid.package, level=nid.level,
            type_=nid.type_, instance=nid.instance,
        )
        .one_or_none()
    )


def _parse_children(serialized: str) -> Tuple[NodeID, list[NodeID]]:
    chunks = serialized.split("+")
    parts = [tuple(int(x) for x in c.split(".")) for c in chunks]
    cat = NodeID(*parts[0])
    children = [NodeID(*p) for p in parts[1:]]
    return cat, children


def _category_key(nid: NodeID) -> Tuple[int, int, int]:
    """Identity of a category without its instance.

    Two recipes with the same (package, level, type_) but different
    instances share the same KIND — e.g. both are R_Block.LET pairs.
    This is the projection that produces the structural signature; if we
    kept the instance, every distinct string-value would split into its
    own bucket and the signature would equal the CTOR.
    """
    return (nid.package, nid.level, nid.type_)


def shape_signature(session, nid: NodeID, depth: int) -> Tuple:
    """Recursive depth-d signature for a recipe NodeID.

    At depth 0 the signature is just the category-kind of this node.
    Beyond that we descend into children, projecting each child onto its
    own depth-(d-1) signature. Trivial leaves stop the recursion.
    """
    cat_key = _category_key(nid)
    if depth <= 0:
        return (cat_key,)
    row = _node_row(session, nid)
    if row is None or not row.serialized:
        return (cat_key,)
    _, children = _parse_children(row.serialized)
    if not children:
        return (cat_key,)
    child_sigs = tuple(shape_signature(session, c, depth - 1) for c in children)
    return (cat_key, child_sigs)


def signature_size(sig: Tuple) -> int:
    """Count leaf entries in a signature — proxy for shape complexity."""
    if len(sig) == 1:
        return 1
    return sum(signature_size(c) for c in sig[1])


def format_signature_one_line(sig: Tuple, max_len: int = 120) -> str:
    s = repr(sig)
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


# ---------------------------------------------------------------------------
# Field-set signature — projects a CTOR onto the SET of keys it carries.
#
# The shape signature above bins by "what categorical sub-trees exist where",
# which over-distinguishes (any new field combination orphans a cell). The
# field-set signature bins by "what NAMED fields the CTOR has" — recovered
# from R_Block.LET recipes whose first child is the key-string. Same family
# regardless of value-encoding, order, or whether one field is optional.
#
# For Network concepts the CTOR is `R_Block.DO(let("id",...), let("hz",...),
# let("geometry",...), ...)`, so the set of keys IS the frontmatter schema
# the concept is honoring. Two concepts with the same key-set are
# structurally the same KIND of concept.
# ---------------------------------------------------------------------------


# R_Block category triple — (package, level, type_) for the BLOCK basic.
_R_BLOCK_KIND = (1, 4, 9)
# R_Block.LET = instance 3 (a (key, value) pair recipe)
_R_BLOCK_LET = 3
# R_Type.STRING for the leaf NodeID layout
_R_STRING_KIND = (1, 1, 6)


def _recover_string(session, nid: NodeID) -> Optional[str]:
    if (nid.package, nid.level, nid.type_) != _R_STRING_KIND:
        return None
    return lookup_string_value(session, nid.instance)


def field_set_signature(session, nid: NodeID) -> Tuple[str, ...]:
    """Walk the CTOR's direct children; for each LET pair, recover the key.

    Returns the sorted, deduplicated tuple of key-names. Two cells with the
    same field-set tuple have the same conceptual schema — the same kind
    of concept, regardless of how full their fields are or what order
    they were authored in.

    A LET recipe is recognized by its CATEGORY (instance 3 in the BLOCK
    basic), not by the child NodeID's type_ field — the child's NodeID is
    a content-addressed handle into substrate_nodes; the category lives
    inside that row's serialized form.
    """
    row = _node_row(session, nid)
    if row is None or not row.serialized:
        return ()
    _, children = _parse_children(row.serialized)
    keys: list[str] = []
    for child in children:
        let_row = _node_row(session, child)
        if let_row is None or not let_row.serialized:
            continue
        cat, let_children = _parse_children(let_row.serialized)
        if cat.instance != _R_BLOCK_LET:
            continue
        if not let_children:
            continue
        key = _recover_string(session, let_children[0])
        if key:
            keys.append(key)
    return tuple(sorted(set(keys)))


def cluster_concepts_field_set(session) -> dict[Tuple, list[SubstrateNamedCellORM]]:
    rows = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain="concept")
        .all()
    )
    clusters: dict[Tuple, list] = defaultdict(list)
    for row in rows:
        if row.ctor_recipe_node_id is None:
            sig: Tuple = ("no-ctor",)
        else:
            ctor_row = (
                session.query(SubstrateNodeORM)
                .filter_by(node_id=row.ctor_recipe_node_id)
                .one_or_none()
            )
            if ctor_row is None:
                sig = ("missing",)
            else:
                nid = NodeID(
                    ctor_row.package, ctor_row.level,
                    ctor_row.type_, ctor_row.instance,
                )
                sig = field_set_signature(session, nid)
        clusters[sig].append(row)
    return clusters


# ---------------------------------------------------------------------------
# Cluster all concepts by signature; report distribution.
# ---------------------------------------------------------------------------


def cluster_concepts(session, depth: int) -> dict[Tuple, list[SubstrateNamedCellORM]]:
    rows = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain="concept")
        .all()
    )
    clusters: dict[Tuple, list] = defaultdict(list)
    for row in rows:
        if row.ctor_recipe_node_id is None:
            sig = (("no-ctor",),)
        else:
            ctor_row = (
                session.query(SubstrateNodeORM)
                .filter_by(node_id=row.ctor_recipe_node_id)
                .one_or_none()
            )
            if ctor_row is None:
                sig = (("missing",),)
            else:
                nid = NodeID(
                    ctor_row.package, ctor_row.level,
                    ctor_row.type_, ctor_row.instance,
                )
                sig = shape_signature(session, nid, depth)
        clusters[sig].append(row)
    return clusters


def print_distribution(clusters: dict[Tuple, list]) -> None:
    sizes = Counter(len(cells) for cells in clusters.values())
    total = sum(len(cells) for cells in clusters.values())
    print(f"\n  {len(clusters)} distinct signatures across {total} concepts")
    print(f"  cluster sizes (size: count_of_clusters):")
    for size in sorted(sizes.keys(), reverse=True):
        print(f"    size {size}: {sizes[size]} cluster(s)")


def print_top_clusters(clusters: dict[Tuple, list], top: int = 8) -> None:
    print(f"\n  top {top} clusters by size:")
    items = sorted(clusters.items(), key=lambda kv: -len(kv[1]))[:top]
    for sig, cells in items:
        sample = ", ".join(c.name for c in cells[:4])
        more = f" +{len(cells) - 4} more" if len(cells) > 4 else ""
        print(f"    [{len(cells):>3} cells] {sample}{more}")
        print(f"              shape: {format_signature_one_line(sig, 100)}")


def print_target_neighbors(
    session, clusters: dict[Tuple, list], target_name: str, depth: int,
) -> None:
    target = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain="concept", name=target_name)
        .one_or_none()
    )
    if target is None:
        print(f"\n  target {target_name!r} not found in substrate")
        return
    target_sig = None
    for sig, cells in clusters.items():
        if any(c.name == target_name for c in cells):
            target_sig = sig
            break
    if target_sig is None:
        print(f"\n  target {target_name!r} has no signature (no CTOR?)")
        return
    neighbors = [c.name for c in clusters[target_sig] if c.name != target_name]
    print(f"\n  {target_name!r} at depth-{depth} cluster:")
    print(f"    signature: {format_signature_one_line(target_sig, 200)}")
    print(f"    cluster size: {len(clusters[target_sig])} cells")
    print(f"    neighbors ({len(neighbors)}):")
    for n in neighbors[:20]:
        print(f"      - {n}")
    if len(neighbors) > 20:
        print(f"      ... +{len(neighbors) - 20} more")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=2,
                    help="recursion depth for signature (0=root only, 2=default)")
    ap.add_argument("--target", default="lc-pulse",
                    help="concept whose neighbors to show")
    ap.add_argument("--top", type=int, default=8,
                    help="how many top clusters to show")
    args = ap.parse_args()

    with session_scope() as session:
        rows = (
            session.query(SubstrateNamedCellORM)
            .filter_by(domain="concept")
            .count()
        )
        if rows == 0:
            print(
                "no concept cells in local substrate. ingest first:\n"
                "  python3 scripts/coh_substrate.py ingest --concepts --structured"
            )
            return 1

        print(f"sensing CTOR-shape geometry across {rows} concept cells")
        for d in range(args.depth + 1):
            clusters = cluster_concepts(session, depth=d)
            print(f"\n=== depth {d} (categorical sub-tree shape) ===")
            print_distribution(clusters)
            if d == args.depth:
                print_top_clusters(clusters, top=args.top)
                print_target_neighbors(
                    session, clusters, args.target, depth=d,
                )

        print("\n=== field-set signature (key-set of named fields) ===")
        field_clusters = cluster_concepts_field_set(session)
        print_distribution(field_clusters)
        print_top_clusters(field_clusters, top=args.top)
        print_target_neighbors(session, field_clusters, args.target, depth=-1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
