"""Auto-firing reactive subscriptions.

The subscription engine shipped in PR #1676 registered subscriptions but
required manual `fire_subscriptions(s)` calls to push reactive bodies. For
a *reactive* lens to be reactive, mutations should auto-fire. This closes
that gap by wiring kernel's `intern_node` and `make_cell` to a callback
registry that `form_runtime` plugs into on module import.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import BID_concept, make_cell
from app.services.substrate.form_runtime import (
    _SUBSCRIPTIONS,
    form_execute_text,
    reset_runtime_registries,
)
from app.services.substrate.kernel import (
    register_mutation_callback,
    unregister_mutation_callback,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(eng, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(eng, checkfirst=True)
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(eng, checkfirst=True)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    reset_runtime_registries()
    try:
        yield s
        s.commit()
    finally:
        s.close()
        reset_runtime_registries()


# ---------------------------------------------------------------------------
# Mutation callback registry (kernel-level)
# ---------------------------------------------------------------------------


def test_mutation_callback_fires_on_make_cell(session):
    """A registered callback runs after every make_cell mutation."""
    fires = []
    cb = lambda sess: fires.append("called")
    register_mutation_callback(cb)
    try:
        make_cell(session, name="lc-a", domain="concept", blueprint=BID_concept())
        session.commit()
        assert len(fires) >= 1
    finally:
        unregister_mutation_callback(cb)


def test_mutation_callback_can_be_unregistered(session):
    """unregister stops the callback firing on later mutations."""
    fires = []
    cb = lambda sess: fires.append("called")
    register_mutation_callback(cb)
    make_cell(session, name="lc-a", domain="concept", blueprint=BID_concept())
    first_count = len(fires)
    unregister_mutation_callback(cb)
    make_cell(session, name="lc-b", domain="concept", blueprint=BID_concept())
    assert len(fires) == first_count


# ---------------------------------------------------------------------------
# Auto-firing subscriptions
# ---------------------------------------------------------------------------


def test_subscription_auto_fires_on_mutation(session):
    """After make_cell mutation, the subscription's `last` value updates
    without manual fire_subscriptions() call — the kernel callback fires it."""
    make_cell(session, name="lc-a", domain="concept", blueprint=BID_concept())
    session.commit()
    form_execute_text(session, '?on_change ?cells where domain == "concept" { 42 }')
    initial_count = len(_SUBSCRIPTIONS[0]["last"])

    # Mutate — add a new concept cell. Auto-fire should detect the change.
    make_cell(session, name="lc-b", domain="concept", blueprint=BID_concept())
    new_count = len(_SUBSCRIPTIONS[0]["last"])
    assert new_count > initial_count


def test_idempotent_mutation_does_not_trigger_change(session):
    """Re-creating a cell with same (domain, name) doesn't change ?cells output."""
    make_cell(session, name="lc-x", domain="concept", blueprint=BID_concept())
    session.commit()
    form_execute_text(session, '?on_change ?cells where domain == "concept" { 42 }')
    initial_last = _SUBSCRIPTIONS[0]["last"]
    initial_count = len(initial_last)

    # Re-create same cell — update path, no new cell row created.
    make_cell(session, name="lc-x", domain="concept", blueprint=BID_concept())
    assert len(_SUBSCRIPTIONS[0]["last"]) == initial_count


def test_auto_fire_does_not_recursively_loop(session):
    """A subscription whose body interns a new recipe must not recursively
    trigger itself forever (the _FIRING guard prevents re-entry)."""
    make_cell(session, name="lc-a", domain="concept", blueprint=BID_concept())
    session.commit()
    # Body computes 1 + 2 which interns a math recipe — that's a mutation.
    # Without the re-entry guard this would loop infinitely.
    form_execute_text(session, '?on_change ?cells where domain == "concept" { 1 + 2 }')
    # Mutate — the subscription auto-fires; body's `1 + 2` may intern math
    # recipes. The _FIRING guard prevents recursive re-entry.
    make_cell(session, name="lc-b", domain="concept", blueprint=BID_concept())
    # If we got here without stack overflow, the guard worked.
    assert True
