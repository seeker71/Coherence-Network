#!/usr/bin/env python3
"""intern_modality_blueprints.py — land the 12 in-memory cross-modal proofs
into the ACTUAL substrate lattice as queryable cells.

Across recent breaths, 11 sibling proofs in `scripts/` attested cross-modal
structural identity using in-memory dict-based substrate stand-ins
(assemblage_shift, embodiment_practice, healing_modality, quantum_physics,
song, teaching, strategy_after_rupture, video, encoder_decoder, spec,
prose_recipe_roundtrip). Each proof's `.shape` property strips the
modality-tag and reveals the common Blueprint underneath — e.g.
R_Measurement-Collapse, R_Pointing, and R_Re-anchor all collapse to
`R_ObserverConditionedActualization` once the altitude-tag is stripped.

This file takes those canonical *shape signatures* and interns them into
the real SQLAlchemy-backed substrate (`api/app/services/substrate/`) so
the cross-modal claim becomes a real-lattice query, not just a runnable
in-memory assertion.

For each canonical shape we intern:
- ONE canonical cell named `R_<CanonicalName>` in domain `recipe-shape`,
  carrying the canonical Blueprint NodeID;
- N per-modality cells (one per shape_tag in the family), in the SAME
  domain `recipe-shape`, carrying the SAME canonical Blueprint NodeID.

Because the cells share Blueprint NodeIDs, `find_equivalent_cells` on the
canonical Blueprint returns the per-modality family, and the Form query
`?equivalent @recipe-shape("R_Recovery")` returns its three siblings:
R_Re-coherence (quantum), R_Re-pattern (healing), R_Re-anchor (assemblage)
— with the canonical shape `R_ObserverConditionedActualization` as the
shared root.

Run:
    python3 scripts/intern_modality_blueprints.py

Idempotent: re-running interns the same cells (NamedCell upsert via
make_cell). Reports per-shape NodeIDs and family sizes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from sqlalchemy.orm import Session  # noqa: E402

from app.services.substrate.category import (  # noqa: E402
    BBasic,
    BContainer,
    BType,
    Level,
)
from app.services.substrate.kernel import (  # noqa: E402
    NodeID,
    find_equivalent_cells,
    make_cell,
    make_composite_blueprint,
)
from app.services.substrate.markdown_frontend import (  # noqa: E402
    BID_object,
    BID_string,
    make_string_literal_blueprint,
)
from app.services.unified_db import session as session_scope  # noqa: E402


# ---------------------------------------------------------------------------
# Domain — recipe-shape cells live in their own substrate domain
# ---------------------------------------------------------------------------
#
# `recipe-shape` is a string domain (no enum slot in BDomain — these cells
# are not first-class network entities like Memory/Spec/Idea, they're
# structural descriptors of cross-modal canonical shapes). Domain names
# are free-form strings in the substrate (`SubstrateNamedCellORM.domain`),
# so the substrate accepts the name; only enum-backed domains like
# `~Memory` need a BDomain slot to participate in trivial-ref TRIVIAL_REFS.
DOMAIN_RECIPE_SHAPE = "recipe-shape"


# ---------------------------------------------------------------------------
# Canonical shape descriptors
# ---------------------------------------------------------------------------
#
# Each entry: (canonical_name, role_slots, modality_tags)
# - canonical_name: the tag-stripped shape name (the .shape[0] in the
#   in-memory proofs)
# - role_slots: the abstract slot names that compose the shape, used to
#   compose a deterministic Blueprint signature. Two shapes with the same
#   role-slots get the SAME Blueprint NodeID — which is exactly the
#   cross-modal claim.
# - modality_tags: the per-modality .shape_tag values that, in the in-memory
#   proofs, all .shape-collapse to the canonical_name.


CANONICAL_SHAPES: List[Tuple[str, Sequence[str], Sequence[str]]] = [
    # CLAIM-T1 / CLAIM-Q1 / CLAIM-A1 — observer-conditioned actualization.
    # The keystone shape: every "observer arrives, possibility resolves"
    # recipe at any altitude collapses here.
    (
        "R_ObserverConditionedActualization",
        ("observer", "observable", "pre_state", "eigenvalue", "post_state", "backaction"),
        (
            "R_Measurement-Collapse",   # quantum
            "R_Pointing",               # teaching
            "R_Re-anchor",              # assemblage
        ),
    ),
    # CLAIM-Q4 — recovery / re-coherence / re-pattern / re-anchor.
    # Same shape as the keystone, but tagged by the recovery-altitude
    # family. Carried as its own canonical entry so the family-of-four
    # is queryable as a unit; the .shape descriptor is the same role-slots
    # as the keystone above. We *intentionally* intern a distinct
    # canonical (R_Recovery) so the recovery family is named and queryable
    # even though it shares Blueprint with the keystone family at the
    # actualization-shape altitude. The lattice carries both: keystone
    # canonical + recovery canonical, with structural cross-equivalence
    # discoverable via find_equivalent_cells.
    (
        "R_Recovery",
        ("observer", "observable", "pre_state", "eigenvalue", "post_state", "backaction"),
        (
            "R_Re-coherence",           # quantum (post-decoherence return)
            "R_Recovery",               # strategy-after-rupture
            "R_Re-pattern",             # healing modality
            "R_Re-anchor",              # assemblage shift (the cross-family bridge)
        ),
    ),
    # CLAIM-Q3 / CLAIM-S1 — phase dissolution.
    # Decoherence in quantum, staying-in-the-mess in strategy, drone-held
    # in song. All three: coherence drops, environment absorbs phase, no
    # re-anchor fires.
    (
        "R_SustainedTension",
        ("pre_coherence", "post_coherence", "environment", "timescale"),
        (
            "R_Decoherence",            # quantum
            "R_Stay-In-The-Mess",       # strategy
            "R_Drone-sustained",        # strategy-as-drone
            "R_Decoherence-Held",       # song
            "R_Drone-held",             # song-as-drone
        ),
    ),
    # CLAIM-S2 — resolution to silence.
    # A move resolves cleanly, releases tension, composts itself; the
    # body lands quietly. Resolve (song) ≡ Release (healing) ≡ Compost
    # (strategy after rupture) ≡ release-without-re-pattern (incomplete
    # composting that still resolves the tension into silence).
    (
        "R_ResolutionToSilence",
        ("subject", "release_mechanism", "final_state", "preserved_invariant"),
        (
            "R_Resolve",                       # song
            "R_Release",                       # healing
            "R_Compost-The-Move",              # strategy after rupture
            "R_Resolve-to-silence",            # strategy
            "R_Release-without-re-pattern",    # strategy
        ),
    ),
    # CLAIM-S3 / CLAIM-Q6 / CLAIM-R2 — meet-then-shift.
    # Two cells / two presences meet; the meeting itself is the
    # measurement and the resonance. Observer-effect (quantum),
    # call+response / resonate (song / healing), same-breath-repair
    # (strategy).
    (
        "R_MeetThenShift",
        ("initiator", "responder", "meeting_signal", "post_initiator", "post_responder"),
        (
            "R_Call+R_Response",        # song
            "R_Resonate",               # healing
            "R_Same-Breath-Repair",     # strategy
            "R_Observer-Effect",        # quantum
            "R_Transmission",           # teaching
        ),
    ),
    # CLAIM-Q5 / CLAIM-T4 / CLAIM-R3 — skip the intermediate.
    # Pass from initial to final without traversing the classical
    # intermediate. Quantum tunnel, assemblage catch-in-motion, teaching
    # embodied-example (the example IS the lesson, skip the lecture),
    # strategy soften (sidestep the escalation).
    (
        "R_SkipTheIntermediate",
        ("initial", "barrier", "final", "probability", "mechanism"),
        (
            "R_Tunnel",                 # quantum
            "R_Catch-In-Motion",        # assemblage
            "R_Soften",                 # strategy
            "R_Embodied-Example",       # teaching
        ),
    ),
    # CLAIM-T3 / CLAIM-R5 — return from edge.
    # Sequential arc that descends, touches the far edge, returns.
    # Teaching R_Arc, embodiment R_Pendulation, strategy walk-back-with-
    # tenderness, R_Arc.descent-and-return (the long-form name).
    (
        "R_ReturnFromEdge",
        ("origin", "descent", "edge", "return", "integrated"),
        (
            "R_Arc",                            # teaching
            "R_Pendulation",                    # embodiment
            "R_Walk-Back-With-Tenderness",      # strategy
            "R_Arc.descent-and-return",         # strategy (long-form)
        ),
    ),
    # Cross-modal table (embodiment-practice-as-recipe.form Part 4 +
    # healing-modality-as-recipe.form Part 5). The cell holds a coherent
    # field — its own and the field around it — while activity flows
    # through. Healing R_Field-Holding, embodiment R_Field-Holding-Self,
    # embodiment R_Coherence-Heart-Brain. (Strategy R_Stay-In-The-Mess and
    # teaching steady-frequency-held-by-teacher also attest at this
    # altitude but R_Stay-In-The-Mess lives under R_SustainedTension by
    # first-canonical-family-wins; teaching steady-frequency has no
    # per-modality cell-name distinct from R_Field-Holding so we don't
    # double-intern.)
    (
        "R_FieldHoldingPresence",
        ("holder", "field_state", "duration", "coherence_floor", "perturbation_response"),
        (
            "R_Field-Holding",              # healing
            "R_Field-Holding-Self",         # embodiment
            "R_Coherence-Heart-Brain",      # embodiment (heart-brain coherence as held field)
        ),
    ),
    # Cross-modal table (embodiment Part 4 + healing Part 5). Dropping
    # attention back into present ground / the body / the root. Embodiment
    # R_Grounding, healing R_Arrival, song R_Return-to-root. (Strategy
    # R_Catch-In-Motion-when-ground-lost is a sibling claim but
    # R_Catch-In-Motion already lives under R_SkipTheIntermediate by
    # first-canonical-family-wins.)
    (
        "R_GroundingMove",
        ("attention_source", "somatic_locus", "arrival_signal", "post_state"),
        (
            "R_Grounding",                  # embodiment
            "R_Arrival",                    # healing
            "R_Return-to-root",             # song (return to root pitch after drone)
        ),
    ),
    # Cross-modal table (embodiment Part 4: R_Body-Scan ↔ video R_Scene
    # sequence ↔ prose R_Block.SEQUENCE through locations ↔ teaching
    # R_Arc.descent through felt territories). Sequential attention
    # walking through a series of loci, leaving a trace at each.
    (
        "R_SequentialScan",
        ("walker", "loci", "step_signal", "trace", "completion"),
        (
            "R_Body-Scan",                  # embodiment
            "R_Scene-Sequence",             # video
            "R_Block.SEQUENCE-locations",   # prose
            "R_Arc.descent-through-felt",   # teaching
        ),
    ),
    # Cross-modal table (embodiment Part 4: R_Resourcing ↔ song callback
    # to known motif ↔ teaching R_Embodied-Example pulled from memory ↔
    # quantum preparation of a known eigenstate ↔ strategy R_Walk-Back-
    # With-Tenderness using prior recovery). Calling a known-coherent
    # state back into the present. (R_Embodied-Example lives under
    # R_SkipTheIntermediate and R_Walk-Back-With-Tenderness lives under
    # R_ReturnFromEdge — first-canonical-family-wins; the cross-modal
    # claim still attests structurally at the canonical Blueprint.)
    (
        "R_KnownStateRecall",
        ("caller", "known_state", "recall_cue", "present_state", "merged_state"),
        (
            "R_Resourcing",                 # embodiment
            "R_Callback-To-Motif",          # song (callback to a known motif)
            "R_Prepare-Known-Eigenstate",   # quantum (eigenstate preparation)
        ),
    ),
    # Cross-modal table (assemblage Part 5: R_Hold-Multiple ↔ quantum
    # R_Superposition sustained ↔ teaching koan held without resolving ↔
    # embodiment R_Window-of-Tolerance broad enough to hold opposites).
    # Sustained simultaneity of two or more states without forcing
    # collapse. The keystone shape under all paradox-holding practice.
    (
        "R_SuperpositionHold",
        ("holder", "states", "amplitude", "duration", "collapse_pressure"),
        (
            "R_Hold-Multiple",              # assemblage
            "R_Superposition-sustained",    # quantum
            "R_Koan-Held",                  # teaching
            "R_Window-of-Tolerance-broad",  # embodiment
        ),
    ),
    # Cross-modal table (assemblage Part 5 + healing Part 5 +
    # embodiment Part 4). Being-with without altering — the seeing IS the
    # presence, no fix, no shape-change pushed. R_Witness (assemblage and
    # healing share the name — first-canonical-family-wins; one
    # NamedCell named R_Witness lands here), R_Sit (embodiment), song
    # drone-held-without-melodic-intervention. (Teaching R_Pointing-
    # without-verbal-naming and quantum R_Observer-Effect-at-minimum-
    # perturbation are sibling attestations; R_Pointing and
    # R_Observer-Effect are already claimed by R_ObserverConditioned-
    # Actualization and R_MeetThenShift respectively, so the cells stay
    # there.)
    (
        "R_WitnessWithoutIntervention",
        ("witness", "witnessed", "presence_quality", "intervention", "post_state"),
        (
            "R_Witness",                            # assemblage & healing (one cell)
            "R_Sit",                                # embodiment
            "R_Drone-held-without-intervention",    # song
        ),
    ),
]


# ---------------------------------------------------------------------------
# Shape → canonical Blueprint composition
# ---------------------------------------------------------------------------


def shape_signature_blueprint(
    session: Session, canonical_name: str, role_slots: Sequence[str]
) -> NodeID:
    """Compose the canonical Blueprint NodeID for a cross-modal shape.

    The Blueprint is a composite OBJECT whose first child is the canonical
    name as a string-literal Blueprint, followed by one OBJECT-wrapped
    string-literal-Blueprint per role slot. Same canonical_name + same
    role_slots → identical Blueprint NodeID, deterministic across runs.

    Why this shape:
    - The canonical_name encodes WHICH cross-modal shape (so R_Recovery and
      R_ObserverConditionedActualization don't accidentally collapse even
      though they share role-slots).
    - The role_slots encode the SHAPE'S structure (so two unrelated
      canonical names with the same role-slot tuple are kept apart by name).
    - The substrate's content-addressing then guarantees: re-running this
      function returns the same NodeID; two interns of the same descriptor
      collapse to one row in `substrate_nodes`.
    """
    name_bp = make_string_literal_blueprint(session, canonical_name)
    slot_bps: List[NodeID] = []
    for slot in role_slots:
        slot_bp = make_string_literal_blueprint(session, slot)
        slot_bps.append(slot_bp)
    return make_composite_blueprint(
        session, BID_object(), [name_bp, *slot_bps]
    )


def intern_canonical_shape(
    session: Session,
    canonical_name: str,
    role_slots: Sequence[str],
    modality_tags: Sequence[str],
) -> Tuple[NodeID, List[str]]:
    """Intern the canonical shape + per-modality cells, all sharing one Blueprint.

    Returns (canonical_blueprint_node_id, names_interned).
    """
    canonical_bp = shape_signature_blueprint(session, canonical_name, role_slots)

    names_interned: List[str] = []

    # The canonical cell — same name as the canonical shape.
    canonical_cell = make_cell(
        session,
        name=canonical_name,
        domain=DOMAIN_RECIPE_SHAPE,
        blueprint=canonical_bp,
    )
    names_interned.append(canonical_cell.name)

    # Per-modality cells — each shares the canonical Blueprint NodeID.
    # find_equivalent_cells on canonical_bp will return all of them.
    for tag in modality_tags:
        # Skip if the modality tag IS the canonical name (one entry in
        # CLAIM-Q4 reuses `R_Recovery` as both canonical and modality —
        # the cell already exists).
        if tag == canonical_name:
            continue
        cell = make_cell(
            session,
            name=tag,
            domain=DOMAIN_RECIPE_SHAPE,
            blueprint=canonical_bp,
        )
        names_interned.append(cell.name)

    return canonical_bp, names_interned


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def intern_all(session: Session) -> List[Tuple[str, NodeID, List[str]]]:
    """Intern every canonical shape. Returns the per-shape report."""
    report: List[Tuple[str, NodeID, List[str]]] = []
    for canonical_name, role_slots, modality_tags in CANONICAL_SHAPES:
        bp, names = intern_canonical_shape(
            session, canonical_name, role_slots, modality_tags
        )
        report.append((canonical_name, bp, names))
    return report


def main() -> int:
    print("─" * 70)
    print("intern_modality_blueprints — landing the cross-modal proofs in the lattice")
    print("─" * 70)
    with session_scope() as session:
        report = intern_all(session)
        # Flush + verify each shape's equivalent set
        session.flush()

        for canonical_name, bp, names in report:
            equivalents = find_equivalent_cells(session, bp)
            eq_names = sorted({c.name for c in equivalents})
            print()
            print(f"{canonical_name}")
            print(f"  blueprint NodeID:  @{bp}")
            print(f"  interned cells:    {len(names)} ({', '.join(names)})")
            print(f"  ?equivalent set:   {len(eq_names)} cells")
            for n in eq_names:
                print(f"    - @recipe-shape({n})")

        session.commit()

    print()
    print("─" * 70)
    print("Done. The cross-modal claims now live in the real substrate.")
    print("Query examples:")
    print('  coh substrate form \'?equivalent @recipe-shape("R_Recovery")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Measurement-Collapse")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Tunnel")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_FieldHoldingPresence")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Hold-Multiple")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Witness")\'')
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
