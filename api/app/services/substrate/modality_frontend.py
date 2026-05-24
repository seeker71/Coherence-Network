"""Modality frontend — the shared infrastructure for non-text extractions.

prose-as-recipe.form proved that words can be cells and sentences can be
Recipes. modality-as-recipe.form generalizes: a source admits MANY parallel
extractions, each producing its own Recipe over its own leaf-cells, all
attaching to the source as siblings. Cross-modal Blueprint equivalence
comes for free — content-addressing recognizes shape regardless of modality.

This module is the substrate-side enabler for that claim. Per-modality
encoders (song_encoder, teaching_encoder, strategy_encoder, ...) compose
structured input into a Recipe; this module attaches it as an extraction
cell whose CTOR carries (source-ref, modality-slug, track-recipe).

The pattern an encoder follows:

    track_dict = {"kind": "song", "phrases": [...], "arc": "ascending"}
    extraction = intern_extraction(
        session, source_cell, modality="song", track=track_dict
    )

Two extractions with structurally-identical tracks intern to the SAME
NodeID regardless of source or modality. A R_Recovery shape found in a
song is the same NodeID as one found in a strategy or a teaching.

Closes GAP-M2 from docs/coherence-substrate/modality-as-recipe.form.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.services.substrate.kernel import (
    DOMAIN_RECIPE,
    NamedCell,
    NodeID,
    Recipe,
    intern_node,
    lookup_cell,
    make_cell,
)
from app.services.substrate.markdown_frontend import (
    BID_resource,
    frontmatter_to_structured_ctor,
    named_field_recipe,
    structured_value_recipe,
)
from app.services.substrate.category import RBasic, Level

# RBasic.BLOCK + RBlock.DO row id for the do-block that wraps a CTOR
def _RID_block_do() -> NodeID:
    from app.services.substrate.category import BBasic, RBlock
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def intern_extraction(
    session: Session,
    source_cell: NamedCell,
    modality: str,
    track: Union[Dict[str, Any], Recipe, NodeID],
) -> NamedCell:
    """Attach a modality-specific extraction to a source cell.

    The extraction is itself a NamedCell in domain "extraction" whose CTOR
    composes three substrate-resident fields:

        source:    (domain, name) of the source cell, as a substrate string-leaf
        modality:  the modality slug (e.g. "song", "teaching", "strategy")
        track:     the extraction's recipe (built by the modality encoder)

    The extraction's name follows `extraction:{source_domain}:{source_name}:{modality}`,
    so the same source can carry many sibling extractions and each is
    addressable. Idempotent: identical track → identical CTOR NodeID; same
    source+modality → identical cell row.

    `track` accepts either a structured dict (passed through
    frontmatter_to_structured_ctor) or an already-built Recipe / NodeID.
    """
    track_id = _coerce_track_to_node_id(session, track)

    source_marker = structured_value_recipe(
        session, {"domain": source_cell.domain, "name": source_cell.name}
    )
    modality_marker = structured_value_recipe(session, modality)
    track_marker = _wrap_as_recipe_ref(session, track_id)

    ctor_children = [
        named_field_recipe(session, "source", source_marker),
        named_field_recipe(session, "modality", modality_marker),
        named_field_recipe(session, "track", track_marker),
    ]
    ctor = intern_node(session, DOMAIN_RECIPE, _RID_block_do(), ctor_children)

    name = f"extraction:{source_cell.domain}:{source_cell.name}:{modality}"
    return make_cell(
        session,
        name=name,
        domain="extraction",
        blueprint=BID_resource(),
        ctor=ctor,
        source_path=source_cell.source_path,
    )


def lookup_extraction(
    session: Session,
    source_cell: NamedCell,
    modality: str,
) -> Optional[NamedCell]:
    """Look up a single extraction by (source_cell, modality)."""
    name = f"extraction:{source_cell.domain}:{source_cell.name}:{modality}"
    return lookup_cell(session, "extraction", name)


# ---------------------------------------------------------------------------
# Encoder registry — discovered, not hard-coded
# ---------------------------------------------------------------------------


_ENCODER_REGISTRY: Dict[str, Any] = {}


def register_encoder(modality: str, encoder_fn: Any) -> None:
    """Register a modality encoder. `encoder_fn(session, raw) -> dict | Recipe`."""
    _ENCODER_REGISTRY[modality] = encoder_fn


def lookup_encoder(modality: str) -> Optional[Any]:
    """Resolve a modality's encoder function, or None."""
    return _ENCODER_REGISTRY.get(modality)


def known_modalities() -> List[str]:
    """List the modalities the body has encoders for, in registration order."""
    return list(_ENCODER_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _coerce_track_to_node_id(
    session: Session, track: Union[Dict[str, Any], Recipe, NodeID]
) -> NodeID:
    if isinstance(track, NodeID):
        return track
    if isinstance(track, Recipe):
        return track.make_self_id(session)
    if isinstance(track, dict):
        # An empty dict still yields a usable CTOR (frontmatter_to_structured_ctor
        # returns None on empty; we wrap it with a placeholder).
        ctor = frontmatter_to_structured_ctor(session, track)
        if ctor is not None:
            return ctor
        # Empty track — intern an empty DO node so downstream code has a
        # NodeID to work with.
        return intern_node(session, DOMAIN_RECIPE, _RID_block_do(), [])
    raise TypeError(
        f"track must be dict, Recipe, or NodeID; got {type(track).__name__}"
    )


def _wrap_as_recipe_ref(session: Session, recipe_node: NodeID) -> NodeID:
    """A track-recipe is referenced from inside the extraction's CTOR.

    We wrap it as a structured-value so the CTOR's LET pair carries the
    reference verbatim without flattening through string-repr.
    """
    return recipe_node
