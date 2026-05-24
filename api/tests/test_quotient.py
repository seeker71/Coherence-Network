"""Tests for the QUOTIENT arm — Python kernel.

Mirrors ``form/form-kernel-ts/src/quotient.test.ts``. The core
promise: two representatives equivalent under a quotient's relation
receive the SAME NodeID — content-addressing IS the quotient.

Coverage:
- ``RBasic.QUOTIENT`` is slot 70 (cross-kernel agreement)
- Integer-from-nat-pair: equivalence classes share NodeID
- Rational-from-int-pair: reduction + sign normalization
- Commutative-pair: order-invariance
- Round-trip: canonical form decodes back to a valid representative
- Substrate-cell content-addressing for equivalence-recipes
- Decidability policy: cheap → EAGER, heavy/undecidable → LAZY
- Lazy strategy: raw NodeIDs differ; canonical_form merges
- quotient_parts inspection
- Handler registry queryable
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.category import Level, RBasic, RType, Triv
from app.services.substrate.kernel import DOMAIN_RECIPE, NodeID, intern_node
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.quotient import (
    CanonStrategy,
    Decidability,
    build_quotient_library,
    canonical_form,
    get_handler,
    intern_quotient_value,
    make_equivalence,
    make_quotient_recipe,
    quotient_equal,
    quotient_parts,
    register_handler,
    resolve_equivalence,
)
from app.services.substrate.substrate_strings import SubstrateStringORM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """In-memory SQLite session with the substrate tables."""
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


def _placeholder_carrier(session) -> NodeID:
    """A throwaway recipe-shape we use as the carrier in tests. The
    content of the carrier doesn't matter — only its NodeID identity."""
    # A LIST-shaped recipe with one trivial child so it's a real composite
    # row (not just a returned category).
    marker = NodeID(1, Level.TRIVIAL, RType.STRING, 9991)
    category = NodeID(1, Level.BASIC, RBasic.BLOCK, 99)
    return intern_node(session, DOMAIN_RECIPE, category, [marker])


def _int(v: int) -> NodeID:
    """Build a sign-bijective integer trivial NodeID matching the
    encoding used inside quotient.py."""
    if v >= 0:
        instance = 2 * v + 1
    else:
        instance = 2 * (-v)
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, instance)


def _int_value(nid: NodeID) -> int:
    """Decode a sign-bijective integer trivial NodeID."""
    assert nid.level == Level.TRIVIAL and nid.type_ == RType.INTEGER
    inst = nid.instance
    if inst == 0:
        return 0
    if inst % 2 == 1:
        return (inst - 1) // 2
    return -(inst // 2)


# ---------------------------------------------------------------------------
# Test 1 — RBasic.QUOTIENT constant value (cross-kernel slot agreement)
# ---------------------------------------------------------------------------


def test_rbasic_quotient_is_slot_70():
    """The QUOTIENT slot value matches the TS kernel for cross-kernel
    NodeID agreement."""
    assert int(RBasic.QUOTIENT) == 70


def test_triv_quotient_leaf_is_slot_14():
    """Reserved trivial-leaf slot for the QUOTIENT_LEAF future encoding."""
    assert int(Triv.QUOTIENT_LEAF) == 14


# ---------------------------------------------------------------------------
# Test 2 — Integer-from-nat-pair: (3,1) and (5,3) share NodeID
# ---------------------------------------------------------------------------


def test_integer_from_nat_pair_equivalence_classes_share_node_id(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    v31 = intern_quotient_value(session, Q, [_int(3), _int(1)])
    v53 = intern_quotient_value(session, Q, [_int(5), _int(3)])
    v97 = intern_quotient_value(session, Q, [_int(9), _int(7)])

    assert v31 == v53, (
        f"(3,1) and (5,3) both represent +2 — should share NodeID; "
        f"got {v31} vs {v53}"
    )
    assert v31 == v97, "transitivity: (3,1) ≡ (9,7)"


def test_integer_from_nat_pair_negative_class(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    vn13 = intern_quotient_value(session, Q, [_int(1), _int(3)])
    vn24 = intern_quotient_value(session, Q, [_int(2), _int(4)])
    assert vn13 == vn24, "(1,3) and (2,4) both represent -2"


def test_integer_from_nat_pair_distinct_classes_distinct_node_ids(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    v_plus2 = intern_quotient_value(session, Q, [_int(3), _int(1)])
    v_minus2 = intern_quotient_value(session, Q, [_int(1), _int(3)])
    assert v_plus2 != v_minus2, "+2 and -2 must occupy different NodeIDs"


def test_quotient_equal_helper(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    v31 = intern_quotient_value(session, Q, [_int(3), _int(1)])
    v53 = intern_quotient_value(session, Q, [_int(5), _int(3)])
    assert quotient_equal(session, v31, v53)


# ---------------------------------------------------------------------------
# Test 3 — Rational-from-int-pair: (2,4) and (1,2) share NodeID
# ---------------------------------------------------------------------------


def test_rational_from_int_pair_reduces_equivalent_fractions(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_RATIONAL_FROM_INT_PAIR.node_id
    )

    v24 = intern_quotient_value(session, Q, [_int(2), _int(4)])
    v12 = intern_quotient_value(session, Q, [_int(1), _int(2)])
    v36 = intern_quotient_value(session, Q, [_int(3), _int(6)])

    assert v24 == v12, "2/4 ≡ 1/2"
    assert v36 == v12, "3/6 ≡ 1/2 (gcd reduction)"


def test_rational_from_int_pair_sign_normalization(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_RATIONAL_FROM_INT_PAIR.node_id
    )

    v_neg2_4 = intern_quotient_value(session, Q, [_int(-2), _int(4)])
    v_2_neg4 = intern_quotient_value(session, Q, [_int(2), _int(-4)])
    assert v_neg2_4 == v_2_neg4, "-2/4 ≡ 2/-4 (sign in numerator)"


def test_rational_from_int_pair_distinct_signs(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_RATIONAL_FROM_INT_PAIR.node_id
    )

    v_pos = intern_quotient_value(session, Q, [_int(1), _int(2)])
    v_neg = intern_quotient_value(session, Q, [_int(-1), _int(2)])
    assert v_pos != v_neg, "1/2 ≠ -1/2"


def test_rational_from_int_pair_rejects_zero_denominator(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_RATIONAL_FROM_INT_PAIR.node_id
    )

    with pytest.raises(ValueError, match="zero denominator"):
        intern_quotient_value(session, Q, [_int(1), _int(0)])


# ---------------------------------------------------------------------------
# Test 4 — Commutative-pair: (a,b) ≡ (b,a)
# ---------------------------------------------------------------------------


def test_commutative_pair_order_invariant(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_COMMUTATIVE_PAIR.node_id
    )

    a, b = _int(7), _int(42)
    v_ab = intern_quotient_value(session, Q, [a, b])
    v_ba = intern_quotient_value(session, Q, [b, a])
    assert v_ab == v_ba, "(7, 42) ≡ (42, 7)"


def test_commutative_pair_distinct_contents_distinct_ids(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_COMMUTATIVE_PAIR.node_id
    )

    a, b, c = _int(7), _int(42), _int(99)
    v_ab = intern_quotient_value(session, Q, [a, b])
    v_ac = intern_quotient_value(session, Q, [a, c])
    assert v_ab != v_ac, "(7,42) and (7,99) are different equivalence classes"


# ---------------------------------------------------------------------------
# Test 5 — Round-trip: canonical form decodes to valid representative
# ---------------------------------------------------------------------------


def test_canonical_form_round_trip_shape(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    v = intern_quotient_value(session, Q, [_int(7), _int(2)])
    canon = canonical_form(session, v)

    from app.services.substrate.quotient import _node_children  # type: ignore

    kids = _node_children(session, canon)
    # canon's children: [quotient_recipe, canonical-a, canonical-b]
    assert len(kids) == 3, (
        f"canonical form expected 3 children, got {len(kids)}"
    )
    assert _int_value(kids[1]) == 5, "canonical-a == diff (7-2=5)"
    assert _int_value(kids[2]) == 0, "canonical-b == 0"


def test_canonical_reintern_is_idempotent(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )

    v = intern_quotient_value(session, Q, [_int(7), _int(2)])
    # Re-intern from the canonical pair lands at the same NodeID.
    v2 = intern_quotient_value(session, Q, [_int(5), _int(0)])
    assert v == v2, "(7,2) and (5,0) both represent +5"


# ---------------------------------------------------------------------------
# Test 6 — Substrate-cell content-addressing for equivalence-recipes
# ---------------------------------------------------------------------------


def test_equivalence_cells_are_content_addressed_across_calls(session):
    a = build_quotient_library(session)
    b = build_quotient_library(session)
    assert a.EQUIV_INTEGER_FROM_NAT_PAIR.node_id == b.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    assert a.EQUIV_RATIONAL_FROM_INT_PAIR.node_id == b.EQUIV_RATIONAL_FROM_INT_PAIR.node_id


def test_resolve_equivalence_round_trip(session):
    lib = build_quotient_library(session)
    resolved = resolve_equivalence(
        session, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )
    assert resolved.equivalence_name == "integer-from-nat-pair"
    assert resolved.decidability == Decidability.DECIDABLE_CHEAP
    assert resolved.handler_name == "integer-from-nat-pair"
    assert resolved.is_decidable is True


# ---------------------------------------------------------------------------
# Test 7 — Decidability policy: cheap → EAGER, heavy/undecidable → LAZY
# ---------------------------------------------------------------------------


def test_decidability_policy(session):
    register_handler("test-heavy", lambda s, raw: list(raw))
    register_handler("test-undecidable", lambda s, raw: list(raw))

    heavy = make_equivalence(
        session,
        equivalence_name="test-heavy",
        decidability=Decidability.DECIDABLE_HEAVY,
        handler_name="test-heavy",
    )
    undec = make_equivalence(
        session,
        equivalence_name="test-undecidable",
        decidability=Decidability.UNDECIDABLE,
        handler_name="test-undecidable",
    )

    assert heavy.strategy == CanonStrategy.LAZY
    assert undec.strategy == CanonStrategy.LAZY
    assert undec.is_decidable is False
    assert heavy.is_decidable is True


# ---------------------------------------------------------------------------
# Test 8 — Lazy strategy still produces equal canonical forms
# ---------------------------------------------------------------------------


def test_lazy_canonicalization_merges_on_demand(session):
    """Under LAZY strategy, raw NodeIDs differ pre-canonicalization but
    ``canonical_form`` / ``quotient_equal`` merge them."""

    def lazy_integer_pair(s, raw):
        # Same logic as the eager integer-from-nat-pair handler — just
        # registered as DECIDABLE_HEAVY so the policy chooses LAZY.
        a = _int_value(raw[0])
        b = _int_value(raw[1])
        return [_int(a - b), _int(0)]

    register_handler("lazy-integer-pair", lazy_integer_pair)
    lazy_eq = make_equivalence(
        session,
        equivalence_name="lazy-integer-pair",
        decidability=Decidability.DECIDABLE_HEAVY,
        handler_name="lazy-integer-pair",
    )
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(session, carrier, lazy_eq.node_id)

    v31 = intern_quotient_value(session, Q, [_int(3), _int(1)])
    v53 = intern_quotient_value(session, Q, [_int(5), _int(3)])

    # Raw NodeIDs differ (different inst=3 entries with different children).
    assert v31 != v53, "lazy: raw representatives keep distinct NodeIDs"

    # But canonical_form merges them.
    assert canonical_form(session, v31) == canonical_form(session, v53)

    # And quotient_equal works regardless of strategy.
    assert quotient_equal(session, v31, v53)


# ---------------------------------------------------------------------------
# Test 9 — quotient_parts inspection
# ---------------------------------------------------------------------------


def test_quotient_parts_inspection(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q = make_quotient_recipe(
        session, carrier, lib.EQUIV_COMMUTATIVE_PAIR.node_id
    )

    extracted_carrier, extracted_equiv = quotient_parts(session, Q)
    assert extracted_carrier == carrier
    assert extracted_equiv == lib.EQUIV_COMMUTATIVE_PAIR.node_id


def test_quotient_parts_rejects_non_quotient(session):
    """A non-QUOTIENT recipe NodeID raises ValueError."""
    carrier = _placeholder_carrier(session)
    with pytest.raises(ValueError, match="not a QUOTIENT recipe"):
        quotient_parts(session, carrier)


# ---------------------------------------------------------------------------
# Test 10 — Handler registry is queryable
# ---------------------------------------------------------------------------


def test_handler_registry_lookup(session):
    build_quotient_library(session)  # force bootstrap
    assert get_handler("integer-from-nat-pair") is not None
    assert get_handler("rational-from-int-pair") is not None
    assert get_handler("commutative-pair") is not None
    assert get_handler("associative-left-fold") is not None
    assert get_handler("does-not-exist") is None


def test_make_equivalence_rejects_unregistered_handler(session):
    with pytest.raises(ValueError, match="not registered"):
        make_equivalence(
            session,
            equivalence_name="bogus",
            decidability=Decidability.DECIDABLE_CHEAP,
            handler_name="this-handler-does-not-exist-xyz",
        )


# ---------------------------------------------------------------------------
# Test 11 — Quotient recipes themselves are content-addressed
# ---------------------------------------------------------------------------


def test_quotient_recipes_are_content_addressed(session):
    lib = build_quotient_library(session)
    carrier = _placeholder_carrier(session)
    Q1 = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )
    Q2 = make_quotient_recipe(
        session, carrier, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id
    )
    assert Q1 == Q2, "same (carrier, equivalence) should intern to same NodeID"

    # Different equivalence relations produce different quotient recipes.
    Q_other = make_quotient_recipe(
        session, carrier, lib.EQUIV_COMMUTATIVE_PAIR.node_id
    )
    assert Q1 != Q_other
