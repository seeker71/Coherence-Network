"""Runtime semantics for the eleven AST nodes form_runtime didn't yet handle.

Walks the constructs that interned at the form layer (PRs #1670–#1672) and
activates them in the runtime: state stack, exceptions, delegate dispatch,
method def/invoke, common-base peer dispatch, reactive subscriptions,
spatial projection, reverse semantics.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import BID_concept, make_cell
from app.services.substrate.form_runtime import (
    RaiseSignal,
    fire_subscriptions,
    form_execute_text,
    register_coord_fn,
    reset_runtime_registries,
    _SUBSCRIPTIONS,
)
from app.services.substrate.kernel import NodeID
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
    for n in ["lc-a", "lc-b", "lc-c"]:
        make_cell(s, name=n, domain="concept", blueprint=BID_concept())
    s.commit()
    try:
        yield s
        s.commit()
    finally:
        s.close()
        reset_runtime_registries()


# ---------------------------------------------------------------------------
# State stack — save / restore / discard
# ---------------------------------------------------------------------------


def test_save_restore_round_trips_bindings(session):
    """save → mutate → restore → original value back."""
    v = form_execute_text(
        session, "do { let x = 1; save; let x = 99; restore; x }"
    )
    assert v == 1


def test_discard_drops_snapshot_without_restoring(session):
    v = form_execute_text(
        session, "do { let x = 1; save; let x = 99; discard; x }"
    )
    assert v == 99


def test_restore_empty_stack_raises(session):
    with pytest.raises(IndexError):
        form_execute_text(session, "restore")


# ---------------------------------------------------------------------------
# Exception flow — raise / resume
# ---------------------------------------------------------------------------


def test_raise_raises_raise_signal(session):
    with pytest.raises(RaiseSignal):
        form_execute_text(session, "raise")


def test_resume_alone_returns_none(session):
    # resume outside a try-frame is a marker; yields None until try-frames land
    assert form_execute_text(session, "resume") is None


# ---------------------------------------------------------------------------
# Method def + invoke
# ---------------------------------------------------------------------------


def test_method_def_then_invoke(session):
    form_execute_text(session, "method greet on @concept(lc-a) { 1 + 2 }")
    assert form_execute_text(session, "invoke greet on @concept(lc-a)") == 3


def test_method_self_binds_to_target(session):
    """The method body sees .self as the target cell."""
    form_execute_text(session, "method who_am_i on @concept(lc-a) { .self }")
    result = form_execute_text(session, "invoke who_am_i on @concept(lc-a)")
    assert result.name == "lc-a"


def test_method_missing_raises_attribute_error(session):
    with pytest.raises(AttributeError):
        form_execute_text(session, "invoke nonexistent on @concept(lc-a)")


# ---------------------------------------------------------------------------
# Delegation chain dispatch
# ---------------------------------------------------------------------------


def test_delegate_chain_walks_to_method_holder(session):
    """invoke on lc-b delegates to lc-a, which holds the method."""
    form_execute_text(session, "method greet on @concept(lc-a) { 1 + 2 }")
    form_execute_text(session, "delegate @concept(lc-b) to @concept(lc-a)")
    assert form_execute_text(session, "invoke greet on @concept(lc-b)") == 3


def test_delegate_self_binds_to_original_target(session):
    """Even when dispatch walks the chain, .self stays the original target."""
    form_execute_text(session, "method who_am_i on @concept(lc-a) { .self }")
    form_execute_text(session, "delegate @concept(lc-b) to @concept(lc-a)")
    result = form_execute_text(session, "invoke who_am_i on @concept(lc-b)")
    assert result.name == "lc-b"  # original target, not the delegate


# ---------------------------------------------------------------------------
# Common-base peer dispatch
# ---------------------------------------------------------------------------


def test_common_peer_dispatch(session):
    """invoke on a cell with no direct method or delegation finds a common peer."""
    form_execute_text(session, "method greet on @concept(lc-a) { 1 + 2 }")
    form_execute_text(session, "common @concept(lc-c) @concept(lc-a)")
    assert form_execute_text(session, "invoke greet on @concept(lc-c)") == 3


def test_common_groups_merge_transitively(session):
    """common @a @b then common @b @c puts {a, b, c} in one group."""
    form_execute_text(session, "method greet on @concept(lc-a) { 7 }")
    form_execute_text(session, "common @concept(lc-a) @concept(lc-b)")
    form_execute_text(session, "common @concept(lc-b) @concept(lc-c)")
    assert form_execute_text(session, "invoke greet on @concept(lc-c)") == 7


# ---------------------------------------------------------------------------
# Reactive subscription
# ---------------------------------------------------------------------------


def test_on_change_records_subscription(session):
    initial_count = len(_SUBSCRIPTIONS)
    form_execute_text(session, "?on_change @concept(lc-a) { 42 }")
    assert len(_SUBSCRIPTIONS) == initial_count + 1


def test_fire_subscriptions_no_change_returns_empty(session):
    form_execute_text(session, "?on_change @concept(lc-a) { 42 }")
    assert fire_subscriptions(session) == []


def test_fire_subscriptions_on_change_fires_body(session):
    form_execute_text(session, "?on_change @concept(lc-a) { 42 }")
    # Force a "change" by mutating the recorded last-value snapshot.
    _SUBSCRIPTIONS[-1]["last"] = "stale-marker"
    assert fire_subscriptions(session) == [42]


# ---------------------------------------------------------------------------
# Spatial projection — ?project @cell @coord_fn
# ---------------------------------------------------------------------------


def test_project_with_registered_coord_fn(session):
    register_coord_fn("lc-b", lambda cell: f"<<{cell.name}>>")
    v = form_execute_text(session, "?project @concept(lc-a) @concept(lc-b)")
    assert v == "<<lc-a>>"


def test_project_with_unregistered_coord_fn_passes_through(session):
    """When no coord_fn is registered, project returns (cell, coord_fn) tuple."""
    v = form_execute_text(session, "?project @concept(lc-a) @concept(lc-b)")
    assert isinstance(v, tuple) and len(v) == 2


# ---------------------------------------------------------------------------
# Reverse semantics — undo / inverse
# ---------------------------------------------------------------------------


def test_undo_runs_inner(session):
    """`undo (1 + 2)` evaluates the inner expression (pure-computation case)."""
    assert form_execute_text(session, "undo (1 + 2)") == 3


def test_inverse_returns_recipe_nodeid(session):
    v = form_execute_text(session, "inverse(1 + 2)")
    assert isinstance(v, NodeID)
