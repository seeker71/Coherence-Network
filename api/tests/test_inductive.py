"""Tests for INDUCTIVE / CONSTRUCTOR / CHOICE — Python kernel.

Mirrors ``form/form-kernel-ts/src/inductive.test.ts``. The core
promise: structurally identical inductive definitions share NodeIDs
through content-addressing, and pattern matches are total-checked at
walk time.

Coverage:
- RBasic slot agreement (INDUCTIVE=71, CONSTRUCTOR=72, CHOICE_MATCH=35)
- Nat round-trip 0..5
- List length
- Option match-covers vs match-missing-arm raises
- CHOICE recipe — walker totality check
- Custom Color inductive with NodeID-equality across structurally-identical
  definitions
- Arm-number sanity
- Compose with QUOTIENT: Z := (Nat × Nat) / equiv example
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.category import Level, RBasic, RType, Triv
from app.services.substrate.inductive import (
    BuiltinInductives,
    ConstructorDef,
    CtorValue,
    constructor_index,
    constructor_names,
    install_builtin_inductives,
    is_total,
    list_cons,
    list_length,
    list_nil,
    make_choice,
    make_constructor,
    make_inductive,
    match_value,
    nat_of,
    nat_to_int,
    walk_constructor,
    walk_choice,
    walk_value,
)
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.quotient import (
    Decidability,
    build_quotient_library,
    intern_quotient_value,
    make_quotient_recipe,
)
from app.services.substrate.substrate_strings import (
    SubstrateStringORM,
    intern_string_instance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """In-memory SQLite session with substrate tables."""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(v: int) -> NodeID:
    """Sign-bijective integer trivial NodeID."""
    if v >= 0:
        instance = 2 * v + 1
    else:
        instance = 2 * (-v)
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, instance)


# ---------------------------------------------------------------------------
# Slot constants — cross-kernel agreement
# ---------------------------------------------------------------------------


def test_rbasic_inductive_slot_71():
    assert int(RBasic.INDUCTIVE) == 71


def test_rbasic_constructor_slot_72():
    assert int(RBasic.CONSTRUCTOR) == 72


def test_rbasic_choice_match_slot_35():
    assert int(RBasic.CHOICE_MATCH) == 35


def test_triv_constructor_tag_slot_15():
    assert int(Triv.CONSTRUCTOR_TAG) == 15


def test_legacy_bml_choice_unchanged():
    """The pre-existing BML angelic-nondeterminism CHOICE (slot 20) is
    untouched by the additive INDUCTIVE/CONSTRUCTOR/CHOICE_MATCH port."""
    assert int(RBasic.CHOICE) == 20


# ---------------------------------------------------------------------------
# Nat — round trip
# ---------------------------------------------------------------------------


def test_nat_walks_to_ctor(session):
    inds = install_builtin_inductives(session)
    two = nat_of(session, inds, 2)
    v = walk_value(session, two)
    assert isinstance(v, CtorValue)


def test_nat_round_trip_0_through_5(session):
    inds = install_builtin_inductives(session)
    for i in range(6):
        node = nat_of(session, inds, i)
        v = walk_value(session, node)
        assert nat_to_int(v) == i, f"nat_of({i}) should round-trip to {i}"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_walks_and_length(session):
    inds = install_builtin_inductives(session)
    one = _int(1)
    two = _int(2)
    lst = list_cons(
        session, inds, one, list_cons(session, inds, two, list_nil(session, inds))
    )
    v = walk_value(session, lst)
    assert isinstance(v, CtorValue)
    assert list_length(v) == 2


# ---------------------------------------------------------------------------
# Option totality
# ---------------------------------------------------------------------------


def test_option_match_covers_some(session):
    inds = install_builtin_inductives(session)
    some_five = make_constructor(session, inds.Option, "some", (_int(5),))
    v = walk_value(session, some_five)
    r = match_value(
        session,
        v,
        [
            ("none", lambda args: -1),
            ("some", lambda args: args[0]),
        ],
    )
    # arg passed through as the trivial NodeID we constructed it from
    assert r == _int(5)


def test_option_match_covers_none(session):
    inds = install_builtin_inductives(session)
    none = make_constructor(session, inds.Option, "none", ())
    v = walk_value(session, none)
    r = match_value(
        session,
        v,
        [
            ("none", lambda args: -1),
            ("some", lambda args: 0),
        ],
    )
    assert r == -1


def test_option_match_missing_arm_raises(session):
    inds = install_builtin_inductives(session)
    some_five = make_constructor(session, inds.Option, "some", (_int(5),))
    v = walk_value(session, some_five)
    with pytest.raises(ValueError, match="missing: none"):
        match_value(session, v, [("some", lambda args: args[0])])


# ---------------------------------------------------------------------------
# CHOICE recipe — walker totality check
# ---------------------------------------------------------------------------


def test_choice_recipe_rejects_missing_arm(session):
    inds = install_builtin_inductives(session)
    some_five = make_constructor(session, inds.Option, "some", (_int(5),))
    ninety_nine = _int(99)
    choice = make_choice(session, some_five, [("some", ninety_nine)])
    with pytest.raises(ValueError, match="missing constructor"):
        walk_choice(session, choice)


def test_choice_recipe_total_dispatches(session):
    inds = install_builtin_inductives(session)
    some_five = make_constructor(session, inds.Option, "some", (_int(5),))
    ninety_nine = _int(99)
    zero_lit = _int(0)
    choice = make_choice(
        session,
        some_five,
        [("some", ninety_nine), ("none", zero_lit)],
    )
    v = walk_choice(session, choice)
    assert v == ninety_nine


def test_choice_dispatches_correct_arm_for_none(session):
    inds = install_builtin_inductives(session)
    none = make_constructor(session, inds.Option, "none", ())
    a = _int(7)
    b = _int(13)
    choice = make_choice(
        session, none, [("some", a), ("none", b)]
    )
    v = walk_choice(session, choice)
    assert v == b


# ---------------------------------------------------------------------------
# Custom inductive — Color := red | green | blue
# ---------------------------------------------------------------------------


def test_custom_color_constructor_names(session):
    Color = make_inductive(
        session,
        "Color",
        (),
        (
            ConstructorDef("red", 0, ()),
            ConstructorDef("green", 1, ()),
            ConstructorDef("blue", 2, ()),
        ),
    )
    assert constructor_names(session, Color) == ["red", "green", "blue"]


def test_custom_color_totality(session):
    Color = make_inductive(
        session,
        "Color",
        (),
        (
            ConstructorDef("red", 0, ()),
            ConstructorDef("green", 1, ()),
            ConstructorDef("blue", 2, ()),
        ),
    )
    assert is_total(session, Color, ["red", "green", "blue"])
    assert not is_total(session, Color, ["red", "green"])


def test_custom_color_structural_identity(session):
    """Two structurally identical Color definitions intern to the SAME NodeID."""
    Color1 = make_inductive(
        session,
        "Color",
        (),
        (
            ConstructorDef("red", 0, ()),
            ConstructorDef("green", 1, ()),
            ConstructorDef("blue", 2, ()),
        ),
    )
    Color2 = make_inductive(
        session,
        "Color",
        (),
        (
            ConstructorDef("red", 0, ()),
            ConstructorDef("green", 1, ()),
            ConstructorDef("blue", 2, ()),
        ),
    )
    assert Color1 == Color2, "structurally identical Color → same NodeID"


def test_color_constructor_index_sanity(session):
    Color = make_inductive(
        session,
        "Color",
        (),
        (
            ConstructorDef("red", 0, ()),
            ConstructorDef("green", 1, ()),
            ConstructorDef("blue", 2, ()),
        ),
    )
    assert constructor_index(session, Color, "red") == 0
    assert constructor_index(session, Color, "green") == 1
    assert constructor_index(session, Color, "blue") == 2
    assert constructor_index(session, Color, "yellow") == -1


# ---------------------------------------------------------------------------
# Arm-number sanity — ctor-index round trips through the walker
# ---------------------------------------------------------------------------


def test_ctor_index_round_trips_through_walker(session):
    inds = install_builtin_inductives(session)
    some_five = make_constructor(session, inds.Option, "some", (_int(5),))
    v = walk_constructor(session, some_five)
    assert v.ctor_name == "some"
    assert v.ctor_index == 1


def test_constructor_rejects_unknown_name(session):
    inds = install_builtin_inductives(session)
    with pytest.raises(ValueError, match="not a constructor"):
        make_constructor(session, inds.Nat, "not-a-real-ctor", ())


# ---------------------------------------------------------------------------
# Built-in inductives are content-addressed across install calls
# ---------------------------------------------------------------------------


def test_install_builtin_inductives_idempotent(session):
    a = install_builtin_inductives(session)
    b = install_builtin_inductives(session)
    assert a.Nat == b.Nat
    assert a.Bool == b.Bool
    assert a.Option == b.Option
    assert a.Result == b.Result
    assert a.List == b.List


# ---------------------------------------------------------------------------
# Compose with QUOTIENT — Z := (Nat × Nat) / (a,b) ~ (c,d) ⇔ a+d = b+c
#
# This exercises the cross-arm composition: an INDUCTIVE carrier (Nat
# values built from succ/zero) projected through a QUOTIENT equivalence.
# Two Nat-pair representatives of the same integer must share a NodeID.
# ---------------------------------------------------------------------------


def test_inductive_quotient_composition_z_from_nat_pair(session):
    """Z := (Nat × Nat) / equivalence — composing INDUCTIVE + QUOTIENT.

    The integer-from-nat-pair equivalence canonicalizes pairs to (a-b, 0).
    We use Nat representatives (built via the inductive Nat) but feed
    integer trivials through the QUOTIENT's canonicalizer, demonstrating
    that the two arms compose at the substrate layer.
    """
    inds = install_builtin_inductives(session)
    lib = build_quotient_library(session)

    # Carrier — a placeholder LIST recipe (Nat × Nat as a 2-element list).
    nat_3 = nat_of(session, inds, 3)
    nat_1 = nat_of(session, inds, 1)
    # The carrier is the inductive Nat (use the inductive's NodeID as carrier).
    Q = make_quotient_recipe(
        session, inds.Nat, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    # Two raw integer-pair representatives of +2.
    v31 = intern_quotient_value(session, Q, [_int(3), _int(1)])
    v53 = intern_quotient_value(session, Q, [_int(5), _int(3)])
    assert v31 == v53, "(3,1) and (5,3) both represent +2 — same NodeID"


def test_nat_inductive_and_quotient_carrier_distinct_recipes(session):
    """The Nat inductive recipe and a QUOTIENT recipe over Nat are distinct
    NodeIDs (different category arms), even though one references the other."""
    inds = install_builtin_inductives(session)
    lib = build_quotient_library(session)
    Q = make_quotient_recipe(
        session, inds.Nat, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )
    assert Q != inds.Nat
    assert Q.type_ == int(RBasic.QUOTIENT)
    assert inds.Nat.type_ == int(RBasic.INDUCTIVE)
