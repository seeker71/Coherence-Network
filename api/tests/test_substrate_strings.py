"""Tests for the substrate string-table — cross-process-stable interning.

The previous hash-based string-instance allocation worked in-process
but was not cross-process stable. This test suite validates the
substrate-resident replacement: same string → same instance, regardless
of which process or session interned it.

The most important test simulates a process restart by clearing the
in-memory `_STRING_CACHE` and ensuring round-trip lookup still works
through the substrate.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import (
    SubstrateStringORM,
    intern_string_instance,
    list_strings,
    lookup_string_value,
)


@pytest.fixture
def session():
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
# Basic intern + lookup
# ---------------------------------------------------------------------------


def test_intern_returns_sequential_instances(session):
    """Each new string gets the next sequential instance."""
    a = intern_string_instance(session, "alpha")
    b = intern_string_instance(session, "beta")
    c = intern_string_instance(session, "gamma")
    # Distinct instances
    assert a != b
    assert b != c
    assert a != c


def test_intern_returns_same_instance_for_same_string(session):
    """The same string always gets the same instance — within a session."""
    a = intern_string_instance(session, "hello")
    b = intern_string_instance(session, "hello")
    assert a == b


def test_lookup_recovers_original_string(session):
    """Round-trip: intern, then look up the instance, get the string back."""
    inst = intern_string_instance(session, "round-trip-value")
    recovered = lookup_string_value(session, inst)
    assert recovered == "round-trip-value"


def test_lookup_unknown_instance_returns_none(session):
    """Looking up an instance that doesn't exist returns None."""
    assert lookup_string_value(session, 999999) is None


# ---------------------------------------------------------------------------
# Cross-session stability — the architectural payoff
# ---------------------------------------------------------------------------


def test_two_separate_sessions_share_string_table(session):
    """Two sessions on the same database see the same instance for the
    same string — the substrate is the source of truth, not the session."""
    # Intern in session 1
    inst_a = intern_string_instance(session, "shared-string")

    # Open a new session against the same DB (StaticPool keeps the
    # in-memory database alive across session boundaries)
    bind = session.get_bind()
    Session2 = sessionmaker(bind=bind, expire_on_commit=False)
    session2 = Session2()
    try:
        inst_b = intern_string_instance(session2, "shared-string")
        assert inst_a == inst_b
    finally:
        session2.close()


def test_string_recipe_id_uses_substrate_when_session_provided(session):
    """The form_rules helper, with session, allocates via the substrate."""
    from app.services.substrate.form_rules import _string_recipe_id

    nid_a = _string_recipe_id("test-value", session)
    nid_b = _string_recipe_id("test-value", session)
    assert nid_a == nid_b
    # The instance should be sequential, not hash-based
    # (hash-based instances are typically very large)
    assert nid_a.instance < 100  # sequential allocation starts at 1


def test_string_from_recipe_recovers_through_substrate(session):
    """The reverse-lookup goes through the substrate, not just the cache.
    Simulate process restart by clearing the cache mid-test."""
    from app.services.substrate.form_rules import _STRING_CACHE, _string_from_recipe, _string_recipe_id

    nid = _string_recipe_id("substrate-resident-string", session)

    # Clear the in-memory cache (simulates a fresh process)
    _STRING_CACHE.clear()

    recovered = _string_from_recipe(session, nid)
    assert recovered == "substrate-resident-string"


def test_pattern_round_trip_after_cache_clear(session):
    """The full pattern round-trip works after cache clear — the
    substrate string-table is sufficient for reconstruction."""
    from app.services.substrate import (
        Capture,
        Literal,
        Sequence,
        pattern_to_recipe,
        recipe_to_pattern,
    )
    from app.services.substrate.form_rules import _STRING_CACHE

    original = Sequence([
        Literal("IDENT", "unless"),
        Capture("cond"),
        Literal("IDENT", "then"),
        Capture("body"),
    ])
    rid = pattern_to_recipe(session, original)

    # Simulate process restart
    _STRING_CACHE.clear()

    rebuilt = recipe_to_pattern(session, rid)
    assert isinstance(rebuilt, Sequence)
    assert isinstance(rebuilt.parts[0], Literal)
    assert rebuilt.parts[0].kind == "IDENT"
    assert rebuilt.parts[0].value == "unless"
    assert isinstance(rebuilt.parts[1], Capture)
    assert rebuilt.parts[1].name == "cond"


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def test_list_strings_returns_all(session):
    """Enumerate every interned string."""
    intern_string_instance(session, "alpha")
    intern_string_instance(session, "beta")
    rows = list_strings(session)
    values = {v for _, v in rows}
    assert "alpha" in values
    assert "beta" in values
