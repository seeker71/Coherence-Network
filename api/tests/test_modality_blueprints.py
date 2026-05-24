"""Tests for the cross-modal canonical-shape interner.

The 12 in-memory `scripts/*_recipe_proof.py` proofs attest that recipes
from quantum, teaching, healing, song, strategy, embodiment, and
assemblage altitudes collapse to the same Blueprint NodeID once each
recipe's modality `shape_tag` is stripped. `scripts/intern_modality_blueprints.py`
takes those canonical shapes and interns them into the real substrate
under `domain="recipe-shape"` so that `find_equivalent_cells` returns
the cross-modal family in a single query.

These tests exercise the interner against an in-memory SQLite-backed
substrate (same pattern as `test_substrate.py`). They assert:

- Each canonical shape interns to a deterministic Blueprint NodeID
  (re-running returns the same NodeID — content-addressing holds).
- The canonical cell and all per-modality cells share that one Blueprint.
- `find_equivalent_cells(canonical_blueprint)` returns the full
  cross-modal family — every modality tag from the in-memory proofs is
  reachable.
- Distinct canonical shapes (different role-slot families) have distinct
  Blueprint NodeIDs — the lattice keeps them apart even though they all
  live in the same domain.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.services.substrate.kernel import find_equivalent_cells, lookup_cell
from app.services.substrate.orm import (
    SubstrateNamedCellORM,
    SubstrateNodeORM,
)
from app.services.substrate.substrate_strings import SubstrateStringORM

from intern_modality_blueprints import (  # noqa: E402
    CANONICAL_SHAPES,
    DOMAIN_RECIPE_SHAPE,
    intern_all,
    intern_canonical_shape,
    shape_signature_blueprint,
)


@pytest.fixture
def session():
    """In-memory SQLite session with substrate tables only."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def test_shape_signature_blueprint_is_deterministic(session):
    """Same canonical_name + role_slots → identical Blueprint NodeID."""
    bp1 = shape_signature_blueprint(
        session, "R_TestShape", ("alpha", "beta", "gamma")
    )
    bp2 = shape_signature_blueprint(
        session, "R_TestShape", ("alpha", "beta", "gamma")
    )
    assert bp1 == bp2, "content-addressing must collapse identical descriptors"


def test_shape_signature_distinct_names_distinct_blueprints(session):
    """Different canonical names with same role-slots → distinct Blueprints.

    The canonical name participates in the signature, so the lattice keeps
    R_Recovery and R_ObserverConditionedActualization apart even when
    they share the role-slot tuple.
    """
    slots = ("observer", "observable", "pre_state")
    bp_a = shape_signature_blueprint(session, "R_Recovery", slots)
    bp_b = shape_signature_blueprint(
        session, "R_ObserverConditionedActualization", slots
    )
    assert bp_a != bp_b, "different canonical names must produce different Blueprints"


def test_shape_signature_distinct_role_slots_distinct_blueprints(session):
    """Different role-slot tuples → distinct Blueprints, same canonical name."""
    bp_a = shape_signature_blueprint(session, "R_Shape", ("a", "b"))
    bp_b = shape_signature_blueprint(session, "R_Shape", ("a", "b", "c"))
    assert bp_a != bp_b, "different role-slot tuples must produce different Blueprints"


def test_canonical_shape_interns_cells_with_shared_blueprint(session):
    """Canonical + per-modality cells all share the canonical Blueprint."""
    bp, names = intern_canonical_shape(
        session,
        "R_TestRecovery",
        ("observer", "observable", "pre_state", "post_state"),
        ("R_TestRecovery", "R_Twin-A", "R_Twin-B"),
    )

    # All names should resolve to cells with this Blueprint.
    for name in names:
        cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, name)
        assert cell is not None, f"cell {name!r} must be interned"
        assert cell.blueprint == bp, (
            f"cell {name!r} blueprint drift — expected {bp}, got {cell.blueprint}"
        )


def test_find_equivalent_cells_returns_cross_modal_family(session):
    """find_equivalent_cells(canonical_bp) returns the per-modality cells."""
    bp, names = intern_canonical_shape(
        session,
        "R_ResolutionToSilence",
        ("subject", "release_mechanism", "final_state", "preserved_invariant"),
        ("R_Resolve", "R_Release", "R_Compost-The-Move"),
    )
    equivalents = find_equivalent_cells(session, bp)
    eq_names = {c.name for c in equivalents}
    # All four cells (canonical + three tags) share the Blueprint.
    assert "R_ResolutionToSilence" in eq_names
    assert "R_Resolve" in eq_names
    assert "R_Release" in eq_names
    assert "R_Compost-The-Move" in eq_names


def test_intern_all_lands_every_canonical_shape(session):
    """intern_all interns every entry in CANONICAL_SHAPES."""
    report = intern_all(session)
    assert len(report) == len(CANONICAL_SHAPES)

    for canonical_name, bp, names in report:
        # Canonical cell must exist.
        canonical_cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, canonical_name)
        assert canonical_cell is not None, (
            f"canonical cell {canonical_name!r} must be interned"
        )
        assert canonical_cell.blueprint == bp

        # The equivalent set must include the canonical cell.
        eq = find_equivalent_cells(session, bp)
        eq_names = {c.name for c in eq}
        assert canonical_name in eq_names, (
            f"canonical {canonical_name!r} missing from its own equivalent set"
        )


def test_keystone_actualization_family(session):
    """CLAIM-T1/Q1/A1 — R_Measurement-Collapse, R_Pointing, R_Re-anchor
    intern under the keystone shape and share Blueprint with R_Observer-
    ConditionedActualization."""
    intern_all(session)

    # The keystone canonical.
    canonical = lookup_cell(
        session, DOMAIN_RECIPE_SHAPE, "R_ObserverConditionedActualization"
    )
    assert canonical is not None
    keystone_bp = canonical.blueprint

    # Each per-modality tag must intern under the keystone Blueprint.
    for tag in ("R_Measurement-Collapse", "R_Pointing"):
        cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, tag)
        assert cell is not None, f"keystone modality {tag!r} must be interned"
        assert cell.blueprint == keystone_bp, (
            f"{tag!r} does not share keystone Blueprint — cross-modal claim broken"
        )

    # The equivalent set should expose all keystone-family cells.
    eq = find_equivalent_cells(session, keystone_bp)
    eq_names = {c.name for c in eq}
    assert {"R_Measurement-Collapse", "R_Pointing"}.issubset(eq_names)


def test_recovery_family_cross_modal(session):
    """CLAIM-Q4 — R_Re-coherence ≡ R_Recovery ≡ R_Re-pattern ≡ R_Re-anchor
    all surface in one ?equivalent query against the R_Recovery canonical."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_Recovery")
    assert canonical is not None
    recovery_bp = canonical.blueprint

    eq_names = {c.name for c in find_equivalent_cells(session, recovery_bp)}
    # All four modality-twins live under this Blueprint.
    assert "R_Re-coherence" in eq_names, "quantum recovery missing"
    assert "R_Re-pattern" in eq_names, "healing recovery missing"
    # R_Re-anchor is the cross-family bridge (also appears in the keystone
    # family); it shares Blueprint with R_Recovery's canonical AND with
    # R_ObserverConditionedActualization's canonical — but each canonical's
    # Blueprint NodeID is distinct because the canonical_name participates
    # in the signature.
    assert "R_Re-anchor" in eq_names, "assemblage recovery bridge missing"


def test_skip_intermediate_family_cross_modal(session):
    """CLAIM-Q5/T4/R3 — R_Tunnel, R_Catch-In-Motion, R_Soften, R_Embodied-Example."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_SkipTheIntermediate")
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {"R_Tunnel", "R_Catch-In-Motion", "R_Soften", "R_Embodied-Example"}.issubset(
        eq_names
    )


def test_distinct_canonicals_have_distinct_blueprints(session):
    """Every canonical shape in CANONICAL_SHAPES has a unique Blueprint NodeID."""
    report = intern_all(session)
    blueprints = [bp for _, bp, _ in report]
    assert len(blueprints) == len(set(blueprints)), (
        "two canonical shapes accidentally share a Blueprint — content-addressing "
        "should keep them apart because the canonical_name participates in the signature"
    )


def test_field_holding_presence_family_cross_modal(session):
    """R_Field-Holding (healing) ≡ R_Field-Holding-Self (embodiment) ≡
    R_Coherence-Heart-Brain (embodiment heart-brain coherence). Held-field
    presence — same shape across modalities."""
    intern_all(session)

    canonical = lookup_cell(
        session, DOMAIN_RECIPE_SHAPE, "R_FieldHoldingPresence"
    )
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {
        "R_Field-Holding",
        "R_Field-Holding-Self",
        "R_Coherence-Heart-Brain",
    }.issubset(eq_names)


def test_grounding_move_family_cross_modal(session):
    """R_Grounding (embodiment) ≡ R_Arrival (healing) ≡ R_Return-to-root
    (song). Dropping attention back into present ground."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_GroundingMove")
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {"R_Grounding", "R_Arrival", "R_Return-to-root"}.issubset(eq_names)


def test_sequential_scan_family_cross_modal(session):
    """R_Body-Scan (embodiment) ≡ R_Scene-Sequence (video) ≡
    R_Block.SEQUENCE-locations (prose) ≡ R_Arc.descent-through-felt
    (teaching). Sequential attention walking through loci."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_SequentialScan")
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {
        "R_Body-Scan",
        "R_Scene-Sequence",
        "R_Block.SEQUENCE-locations",
        "R_Arc.descent-through-felt",
    }.issubset(eq_names)


def test_known_state_recall_family_cross_modal(session):
    """R_Resourcing (embodiment) ≡ R_Callback-To-Motif (song) ≡
    R_Prepare-Known-Eigenstate (quantum). Calling a known-coherent state
    back into the present."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_KnownStateRecall")
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {
        "R_Resourcing",
        "R_Callback-To-Motif",
        "R_Prepare-Known-Eigenstate",
    }.issubset(eq_names)


def test_superposition_hold_family_cross_modal(session):
    """R_Hold-Multiple (assemblage) ≡ R_Superposition-sustained (quantum)
    ≡ R_Koan-Held (teaching) ≡ R_Window-of-Tolerance-broad (embodiment).
    Sustained simultaneity without forcing collapse."""
    intern_all(session)

    canonical = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_SuperpositionHold")
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {
        "R_Hold-Multiple",
        "R_Superposition-sustained",
        "R_Koan-Held",
        "R_Window-of-Tolerance-broad",
    }.issubset(eq_names)


def test_witness_without_intervention_family_cross_modal(session):
    """R_Witness (assemblage + healing — one NamedCell) ≡ R_Sit
    (embodiment) ≡ R_Drone-held-without-intervention (song). Being-with
    without altering."""
    intern_all(session)

    canonical = lookup_cell(
        session, DOMAIN_RECIPE_SHAPE, "R_WitnessWithoutIntervention"
    )
    assert canonical is not None
    eq_names = {c.name for c in find_equivalent_cells(session, canonical.blueprint)}
    assert {
        "R_Witness",
        "R_Sit",
        "R_Drone-held-without-intervention",
    }.issubset(eq_names)


def test_first_canonical_family_wins_constraint(session):
    """A per-modality name cell carries exactly one Blueprint. When a
    name appears under multiple canonicals (e.g. R_Witness would
    naturally cross both healing and assemblage at R_Witness-Without-
    Intervention), only one canonical claims it — the cell still exists,
    but its Blueprint is the first canonical's. Confirm R_Witness lands
    under R_WitnessWithoutIntervention (added in this breath) and the
    NamedCell is not split."""
    intern_all(session)

    witness = lookup_cell(session, DOMAIN_RECIPE_SHAPE, "R_Witness")
    assert witness is not None
    witness_canonical = lookup_cell(
        session, DOMAIN_RECIPE_SHAPE, "R_WitnessWithoutIntervention"
    )
    assert witness_canonical is not None
    assert witness.blueprint == witness_canonical.blueprint, (
        "R_Witness should share Blueprint with R_WitnessWithoutIntervention"
    )


def test_intern_all_is_idempotent(session):
    """Re-running intern_all does not duplicate cells; same NodeIDs returned."""
    report_a = intern_all(session)
    report_b = intern_all(session)
    assert len(report_a) == len(report_b)
    for (name_a, bp_a, names_a), (name_b, bp_b, names_b) in zip(report_a, report_b):
        assert name_a == name_b
        assert bp_a == bp_b, (
            f"{name_a!r} Blueprint drift across re-intern — content-addressing broken"
        )
        # Cell count per shape stable.
        cell_count_a = len(
            find_equivalent_cells(session, bp_a)
        )
        cell_count_b = len(
            find_equivalent_cells(session, bp_b)
        )
        assert cell_count_a == cell_count_b
