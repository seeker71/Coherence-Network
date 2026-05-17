"""Dimensional vocabulary and resonance-edge authoring for the coherence-substrate.

The geometric signature work in vision-kb (every concept carries a
`geometry:` block with 15 dimensions: arity, form, topology, polarity,
ordering, phase, ratio, spectral_band, temporal_band, scale, direction,
lineage_texture, embedding_dim, self_similarity, harmonic) needs a place
in the lattice to land. This module:

1. Exposes the five new BDomain Blueprint NodeIDs:
       SPECTRUM, HARMONIC, GEOMETRIC_FORM, POLARITY, TOPOLOGY
   Each is a Blueprint; each cell in the domain is one coordinate
   along that axis (Hz(741) is a cell in SPECTRUM; ~Triad is a cell
   in GEOMETRIC_FORM).

2. Provides idempotent cell-lookup/create helpers for each domain
   (hz_cell, geometric_form_cell, topology_cell, polarity_cell,
   harmonic_cell). Repeated calls with the same value return the
   same NamedCell.

3. Provides resonance-edge constructors that intern a Recipe NodeID
   binding a source cell to a dimensional coordinate cell via the
   new RBasic.RESONANCE category and its RResonance instance verbs
   (SHAPES, HARMONIC_AT, EMBEDS_IN, BRIDGES, NEAR, POLAR_TO,
   CARRIES_RATIO).

4. Provides the top-level author_geometry_signature(session, cell,
   geometry_dict) entry point. Walks a parsed `geometry:` block and
   authors all the resonance edges in one call. Idempotent — re-running
   on the same input produces the same Recipe NodeIDs (content-
   addressed dedup at the kernel layer).

Two concepts authored with identical geometry signatures end up sharing
edge-sets that intern to identical Recipe NodeIDs. The substrate's
content-addressing then surfaces cross-discipline bridges (Vedic gunas
+ Hegelian dialectic + Vasudev's triple temporal alliance all share
the same triad-tension Recipe NodeID, regardless of name).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    BBasic,
    BDomain,
    BReference,
    Level,
    RBasic,
    RResonance,
    RType,
)
from app.services.substrate.kernel import (
    NamedCell,
    NodeID,
    Recipe,
    lookup_cell,
    make_cell,
)


# ---------------------------------------------------------------------------
# Blueprint NodeIDs for the five new dimensional domains
# ---------------------------------------------------------------------------


def BID_spectrum() -> NodeID:
    """Spectrum domain blueprint — Hz bands and named tones."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.SPECTRUM)


def BID_harmonic() -> NodeID:
    """Harmonic domain blueprint — intervals and ratios (Octave, Fifth, Golden, ...)."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.HARMONIC)


def BID_geometric_form() -> NodeID:
    """Geometric-form domain blueprint — Triad, Pentad, Heptad, Dodecad, ..."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.GEOMETRIC_FORM)


def BID_polarity() -> NodeID:
    """Polarity domain blueprint — Unipolar, Triadic-Tension, ParallelFacets, ..."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.POLARITY)


def BID_topology() -> NodeID:
    """Topology domain blueprint — Cyclic-Closed, Parallel, Nested, Holographic, ..."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.TOPOLOGY)


# Domain short-names matching how cells store their `domain` field.
DOMAIN_SPECTRUM = "spectrum"
DOMAIN_HARMONIC = "harmonic"
DOMAIN_GEOMETRIC_FORM = "geometric_form"
DOMAIN_POLARITY = "polarity"
DOMAIN_TOPOLOGY = "topology"


# ---------------------------------------------------------------------------
# Cell-lookup-or-create helpers — one per dimensional domain
# ---------------------------------------------------------------------------


def _ensure_cell(
    session: Session,
    *,
    name: str,
    domain: str,
    blueprint: NodeID,
) -> NamedCell:
    """Idempotent: return the existing cell or create it."""
    existing = lookup_cell(session, domain=domain, name=name)
    if existing is not None:
        return existing
    return make_cell(
        session,
        name=name,
        domain=domain,
        blueprint=blueprint,
    )


def hz_cell(session: Session, hz: int) -> NamedCell:
    """Cell for a Solfeggio Hz band. `hz_cell(741)` returns Hz(741)."""
    return _ensure_cell(
        session,
        name=f"Hz-{hz}",
        domain=DOMAIN_SPECTRUM,
        blueprint=BID_spectrum(),
    )


def harmonic_cell(session: Session, name: str) -> NamedCell:
    """Cell for a named harmonic/ratio. `harmonic_cell(session, 'octave')`."""
    return _ensure_cell(
        session,
        name=name.lower().replace(" ", "-"),
        domain=DOMAIN_HARMONIC,
        blueprint=BID_harmonic(),
    )


def geometric_form_cell(session: Session, name: str) -> NamedCell:
    """Cell for a named geometric form. `geometric_form_cell(session, 'triad')`."""
    return _ensure_cell(
        session,
        name=name.lower().replace(" ", "-"),
        domain=DOMAIN_GEOMETRIC_FORM,
        blueprint=BID_geometric_form(),
    )


def polarity_cell(session: Session, name: str) -> NamedCell:
    """Cell for a polarity texture. `polarity_cell(session, 'triadic-tension')`."""
    return _ensure_cell(
        session,
        name=name.lower().replace(" ", "-"),
        domain=DOMAIN_POLARITY,
        blueprint=BID_polarity(),
    )


def topology_cell(session: Session, name: str) -> NamedCell:
    """Cell for a topology. `topology_cell(session, 'parallel-facets')`."""
    return _ensure_cell(
        session,
        name=name.lower().replace(" ", "-"),
        domain=DOMAIN_TOPOLOGY,
        blueprint=BID_topology(),
    )


# ---------------------------------------------------------------------------
# Resonance-edge constructors — intern a Recipe NodeID for each edge
# ---------------------------------------------------------------------------


def _ptr() -> NodeID:
    """Reference-Pointer blueprint — the type a cell-ID-as-child evaluates to."""
    return NodeID(1, Level.BASIC, BBasic.REFERENCE, BReference.POINTER)


def cell_ref(cell_db_id: int) -> NodeID:
    """Encode a NamedCell's database row id as a substrate NodeID (RType.REF).

    NamedCells don't carry a per-instance NodeID — their identity lives in
    SQLite/Postgres as an autoincrement primary key. To use them as children of
    resonance recipes, we lift the int into the trivial reference space:
    `(package=1, level=TRIVIAL, type_=RType.REF, instance=cell_db_id)`. The
    recipe kernel hashes children by NodeID, so two edges with the same source
    + target cells dedupe to the same Recipe NodeID.
    """
    return NodeID(1, Level.TRIVIAL, RType.REF, cell_db_id)


def _resonance_recipe(verb: RResonance, source: NodeID, target: NodeID) -> Recipe:
    """Build the Recipe shape (verb, [source-ref, target-ref]) for an edge.

    `source` and `target` are NodeIDs (typically from `cell_ref(cell.cell_id)`).
    Each is wrapped as a leaf Recipe so the kernel's `make_self_id` walk
    produces `(verb_node, [source_node, target_node])` for content-addressing.
    """
    ptr = _ptr()
    return Recipe(
        category=NodeID(1, Level.BASIC, RBasic.RESONANCE, verb),
        blueprint=ptr,
        children=[
            Recipe(category=source, blueprint=ptr),
            Recipe(category=target, blueprint=ptr),
        ],
    )


def _edge(session: Session, verb: RResonance, source_db_id: int, target_db_id: int) -> NodeID:
    return _resonance_recipe(
        verb, cell_ref(source_db_id), cell_ref(target_db_id)
    ).make_self_id(session)


def shapes_edge(session: Session, source_db_id: int, target_db_id: int) -> NodeID:
    """source -SHAPES-> geometric_form / topology / polarity. Returns interned Recipe NodeID."""
    return _edge(session, RResonance.SHAPES, source_db_id, target_db_id)


def harmonic_at_edge(session: Session, source_db_id: int, hz_db_id: int) -> NodeID:
    """source -HARMONIC_AT-> spectrum_cell. Returns interned Recipe NodeID."""
    return _edge(session, RResonance.HARMONIC_AT, source_db_id, hz_db_id)


def embeds_in_edge(session: Session, source_db_id: int, dim_db_id: int) -> NodeID:
    """source -EMBEDS_IN-> dimension_cell. Returns interned Recipe NodeID."""
    return _edge(session, RResonance.EMBEDS_IN, source_db_id, dim_db_id)


def bridges_edge(session: Session, source_db_id: int, discipline_db_id: int) -> NodeID:
    """source -BRIDGES-> discipline_cell. Returns interned Recipe NodeID."""
    return _edge(session, RResonance.BRIDGES, source_db_id, discipline_db_id)


def near_edge(session: Session, source_db_id: int, target_db_id: int) -> NodeID:
    """source -NEAR-> target (within 15D signature tolerance). Returns interned Recipe NodeID."""
    return _edge(session, RResonance.NEAR, source_db_id, target_db_id)


def polar_to_edge(session: Session, source_db_id: int, target_db_id: int) -> NodeID:
    """source -POLAR_TO-> target (paired across a polarity axis). Returns interned Recipe NodeID."""
    return _edge(session, RResonance.POLAR_TO, source_db_id, target_db_id)


def carries_ratio_edge(session: Session, source_db_id: int, harmonic_db_id: int) -> NodeID:
    """source -CARRIES_RATIO-> harmonic_cell. Returns interned Recipe NodeID."""
    return _edge(session, RResonance.CARRIES_RATIO, source_db_id, harmonic_db_id)


# ---------------------------------------------------------------------------
# Symmetric (commutative) edges — same NodeID regardless of (a, b) order
# ---------------------------------------------------------------------------


def commutative_edge(
    session: Session,
    *,
    verb: RResonance,
    cell_a_db_id: int,
    cell_b_db_id: int,
) -> NodeID:
    """Symmetric resonance edge — same Recipe NodeID regardless of (a, b) order.

    The substrate is not commutative by default: `shapes_edge(s, a, b)` and
    `shapes_edge(s, b, a)` produce different NodeIDs because children are
    ordered. For relations that ARE symmetric (NEAR-in-signature-space,
    BRIDGES between two disciplines, POLAR_TO across a polarity axis), that
    asymmetry is noise — the relation has no direction.

    `commutative_edge` canonicalizes by sorting cell ids before authoring,
    so `(a, b)` and `(b, a)` intern to the same Recipe NodeID. Verbs that
    are naturally symmetric (NEAR, BRIDGES, POLAR_TO) should use this; verbs
    that ARE directed (SHAPES, HARMONIC_AT, CARRIES_RATIO, EMBEDS_IN) should
    use the directed edge constructors.
    """
    lo, hi = sorted([cell_a_db_id, cell_b_db_id])
    return _edge(session, verb, lo, hi)


def bridges_symmetric(session: Session, cell_a_db_id: int, cell_b_db_id: int) -> NodeID:
    """Convenience: symmetric BRIDGES edge (canonicalized)."""
    return commutative_edge(
        session, verb=RResonance.BRIDGES,
        cell_a_db_id=cell_a_db_id, cell_b_db_id=cell_b_db_id,
    )


def near_symmetric(session: Session, cell_a_db_id: int, cell_b_db_id: int) -> NodeID:
    """Convenience: symmetric NEAR edge (canonicalized)."""
    return commutative_edge(
        session, verb=RResonance.NEAR,
        cell_a_db_id=cell_a_db_id, cell_b_db_id=cell_b_db_id,
    )


def polar_to_symmetric(session: Session, cell_a_db_id: int, cell_b_db_id: int) -> NodeID:
    """Convenience: symmetric POLAR_TO edge (canonicalized)."""
    return commutative_edge(
        session, verb=RResonance.POLAR_TO,
        cell_a_db_id=cell_a_db_id, cell_b_db_id=cell_b_db_id,
    )


# ---------------------------------------------------------------------------
# Top-level: walk a `geometry:` dict and author every resonance edge
# ---------------------------------------------------------------------------


# Maps each geometry-block key to (target-cell-resolver, edge-constructor).
# `target-cell-resolver` returns the cell ID for the dimensional coordinate
# the value names. `edge-constructor` interns the resonance Recipe.
_GEOMETRY_FIELD_HANDLERS: Dict[str, Tuple[str, str]] = {
    # frontmatter key       (target-domain,           resonance-verb)
    "form":                 ("geometric_form",        "shapes"),
    "topology":             ("topology",              "shapes"),
    "polarity":             ("polarity",              "shapes"),
    "harmonic":             ("spectrum",              "harmonic_at"),
    "ratio":                ("harmonic",              "carries_ratio"),
    "embedding_dim":        ("geometric_form",        "embeds_in"),
    "self_similarity":      ("topology",              "shapes"),
    # The following fields are signature coordinates we author as form-shapes
    # too — they carry distinct topology when read structurally.
    "ordering":             ("topology",              "shapes"),
    "phase":                ("polarity",              "shapes"),
    "spectral_band":        ("spectrum",              "shapes"),
    "temporal_band":        ("topology",              "shapes"),
    "scale":                ("topology",              "shapes"),
    "direction":            ("topology",              "shapes"),
    "lineage_texture":      ("topology",              "shapes"),
}


def _resolve_target_cell_db_id(session: Session, domain: str, value: Any) -> Optional[int]:
    """Resolve (or create) the target cell for a geometry field value.

    Returns the cell's database row id (int), suitable for the edge constructors.
    Returns None when the value is missing/unknown and should be skipped.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"none", "null", "unknown", "tbd"}:
        return None
    if domain == "spectrum":
        try:
            hz = int(raw)
        except (TypeError, ValueError):
            # Named band (e.g. "foundation") — author as a non-numeric cell in spectrum.
            cell = _ensure_cell(
                session, name=raw.lower(), domain=DOMAIN_SPECTRUM, blueprint=BID_spectrum()
            )
            return cell.cell_id
        return hz_cell(session, hz).cell_id
    if domain == "harmonic":
        return harmonic_cell(session, raw).cell_id
    if domain == "geometric_form":
        return geometric_form_cell(session, raw).cell_id
    if domain == "polarity":
        return polarity_cell(session, raw).cell_id
    if domain == "topology":
        return topology_cell(session, raw).cell_id
    return None


def _author_edge(
    session: Session,
    verb: str,
    source_db_id: int,
    target_db_id: int,
) -> NodeID:
    if verb == "shapes":
        return shapes_edge(session, source_db_id, target_db_id)
    if verb == "harmonic_at":
        return harmonic_at_edge(session, source_db_id, target_db_id)
    if verb == "carries_ratio":
        return carries_ratio_edge(session, source_db_id, target_db_id)
    if verb == "embeds_in":
        return embeds_in_edge(session, source_db_id, target_db_id)
    if verb == "near":
        return near_edge(session, source_db_id, target_db_id)
    if verb == "polar_to":
        return polar_to_edge(session, source_db_id, target_db_id)
    if verb == "bridges":
        return bridges_edge(session, source_db_id, target_db_id)
    raise ValueError(f"Unknown resonance verb: {verb!r}")


def find_cells_via_resonance(
    session: Session,
    *,
    verb: RResonance,
    target_db_id: int,
) -> List[int]:
    """Walk resonance edges in reverse — return source cell DB ids whose
    `verb` edge points at the cell with `target_db_id`.

    Example: `find_cells_via_resonance(session, verb=RResonance.SHAPES,
    target_db_id=triad_cell.cell_id)` returns every concept that authored a
    SHAPES edge to ~Triad — the cross-discipline triadic family.

    Implementation walks `substrate_nodes.serialized`: a SHAPES edge serializes
    as `"1.2.21.1+1.1.9.<src>+1.1.9.<tgt>"` where 1.2.21.1 is the SHAPES verb
    category and 1.1.9.<id> is a cell_ref. The query matches verb-prefix +
    target-suffix, then parses the source ref out.
    """
    from app.services.substrate.orm import SubstrateNodeORM
    from app.services.substrate.kernel import DOMAIN_RECIPE

    # Category prefix is the verb's NodeID stringified, plus the child separator.
    verb_category = NodeID(1, Level.BASIC, RBasic.RESONANCE, verb)
    verb_prefix = f"{verb_category}+"
    # Target suffix is the cell_ref for the target.
    target_ref = cell_ref(target_db_id)
    target_suffix = f"+{target_ref}"

    rows = (
        session.query(SubstrateNodeORM)
        .filter(
            SubstrateNodeORM.domain == DOMAIN_RECIPE,
            SubstrateNodeORM.type_ == RBasic.RESONANCE,
            SubstrateNodeORM.serialized.like(f"{verb_prefix}%{target_suffix}"),
        )
        .all()
    )

    source_db_ids: List[int] = []
    for row in rows:
        # serialized = "<verb_category>+<source_ref>+<target_ref>"
        parts = row.serialized.split("+")
        if len(parts) != 3:
            continue
        src_ref_str = parts[1]  # "1.1.9.<src_db_id>"
        try:
            src_db_id = int(src_ref_str.split(".")[-1])
        except ValueError:
            continue
        source_db_ids.append(src_db_id)
    return source_db_ids


def find_cells_shaping(session: Session, target_db_id: int) -> List[int]:
    """Convenience: cells whose SHAPES edge targets `target_db_id`."""
    return find_cells_via_resonance(session, verb=RResonance.SHAPES, target_db_id=target_db_id)


def find_cells_harmonic_at(session: Session, target_db_id: int) -> List[int]:
    """Convenience: cells whose HARMONIC_AT edge targets `target_db_id`."""
    return find_cells_via_resonance(session, verb=RResonance.HARMONIC_AT, target_db_id=target_db_id)


def author_geometry_signature(
    session: Session,
    source_db_id: int,
    geometry: Dict[str, Any],
    *,
    arity_hz: Optional[int] = None,
) -> List[Tuple[str, NodeID]]:
    """Author every resonance edge implied by a `geometry:` frontmatter block.

    Args:
        session: SQLAlchemy session bound to the substrate tables.
        source_db_id: NamedCell.cell_id of the source concept/cell.
        geometry: the parsed `geometry:` block from the source's frontmatter.
        arity_hz: when the source carries a top-level `hz:` field (Solfeggio
            band), pass it here so a HARMONIC_AT edge to Hz(N) is authored too.

    Returns a list of (field_name, edge_recipe_id) tuples for inspection /
    logging. Idempotent: repeated calls with the same inputs produce the same
    Recipe NodeIDs through the kernel's content-addressing.
    """
    authored: List[Tuple[str, NodeID]] = []

    # 1) Top-level hz (the band the concept resonates at).
    if arity_hz is not None:
        hz = hz_cell(session, int(arity_hz))
        edge = harmonic_at_edge(session, source_db_id, hz.cell_id)
        authored.append(("hz", edge))

    # 2) Walk each geometry field and author the matching edge.
    for field, value in geometry.items():
        if field == "arity":
            # Arity is structural to the source cell (it's the children-count of
            # the source's Blueprint), not a separate edge target. Skip.
            continue
        handler = _GEOMETRY_FIELD_HANDLERS.get(field)
        if handler is None:
            continue
        target_domain, verb = handler
        target_db_id = _resolve_target_cell_db_id(session, target_domain, value)
        if target_db_id is None:
            continue
        edge = _author_edge(session, verb, source_db_id, target_db_id)
        authored.append((field, edge))

    return authored


__all__ = [
    # Blueprint NodeID constructors
    "BID_spectrum",
    "BID_harmonic",
    "BID_geometric_form",
    "BID_polarity",
    "BID_topology",
    # Cell-ref helper (lifts NamedCell.cell_id into substrate NodeID space)
    "cell_ref",
    # Domain short-names
    "DOMAIN_SPECTRUM",
    "DOMAIN_HARMONIC",
    "DOMAIN_GEOMETRIC_FORM",
    "DOMAIN_POLARITY",
    "DOMAIN_TOPOLOGY",
    # Cell-ensure helpers
    "hz_cell",
    "harmonic_cell",
    "geometric_form_cell",
    "polarity_cell",
    "topology_cell",
    # Edge constructors
    "shapes_edge",
    "harmonic_at_edge",
    "embeds_in_edge",
    "bridges_edge",
    "near_edge",
    "polar_to_edge",
    "carries_ratio_edge",
    # Top-level entry
    "author_geometry_signature",
    # Resonance walks (edges in reverse — the question Form couldn't ask before)
    "find_cells_via_resonance",
    "find_cells_shaping",
    "find_cells_harmonic_at",
    # Symmetric (commutative) edge constructors
    "commutative_edge",
    "bridges_symmetric",
    "near_symmetric",
    "polar_to_symmetric",
]
