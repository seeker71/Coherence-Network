"""List/string indexing + ternary expressions.

Two gaps surfaced by running Form against the live substrate:

- `do { let xs = [10, 20, 30]; xs[1] }` returned `[1]` instead of `20` —
  the parser treated `xs[1]` as two separate atoms (the list and a new
  list literal), making `xs[1]` semantically wrong.
- `5 > 3 ? "big" : "small"` was a SyntaxError — no ternary support.

Both close here. Postfix `[i]` chains through `parse_projection`'s postfix
loop; ternary `?:` sits at the top of the precedence ladder via
`_maybe_ternary`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.form_runtime import (
    form_execute_text,
    reset_runtime_registries,
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
# List indexing
# ---------------------------------------------------------------------------


def test_index_literal_list(session):
    assert form_execute_text(session, "[10, 20, 30][0]") == 10
    assert form_execute_text(session, "[10, 20, 30][2]") == 30


def test_index_via_let_binding(session):
    """The bug-fix case: `xs[1]` after a let-binding actually indexes."""
    assert form_execute_text(
        session, "do { let xs = [10, 20, 30]; xs[1] }"
    ) == 20


def test_nested_indexing(session):
    """`xs[1][0]` chains the postfix indexing."""
    assert form_execute_text(
        session, "do { let xs = [[1, 2], [3, 4]]; xs[1][0] }"
    ) == 3


def test_string_indexing(session):
    assert form_execute_text(session, '"hello"[0]') == "h"
    assert form_execute_text(session, '"hello"[4]') == "o"


def test_index_with_computed_index(session):
    assert form_execute_text(
        session, "do { let xs = [10, 20, 30]; xs[1 + 1] }"
    ) == 30


def test_index_out_of_range_raises(session):
    with pytest.raises(TypeError):
        form_execute_text(session, "[1, 2, 3][10]")


# ---------------------------------------------------------------------------
# Ternary
# ---------------------------------------------------------------------------


def test_ternary_true_branch(session):
    assert form_execute_text(
        session, '5 > 3 ? "big" : "small"'
    ) == "big"


def test_ternary_false_branch(session):
    assert form_execute_text(
        session, '5 < 3 ? "big" : "small"'
    ) == "small"


def test_ternary_with_computed_branches(session):
    assert form_execute_text(
        session, "do { let n = 5; n > 3 ? n * 2 : n }"
    ) == 10


def test_ternary_with_string_compare(session):
    assert form_execute_text(
        session, '"hello" == "hello" ? 1 : 0'
    ) == 1


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def test_ternary_with_indexing(session):
    """ternary's branch can be an indexed expression."""
    assert form_execute_text(
        session, 'do { let xs = [10, 20, 30]; xs[0] > 5 ? xs[1] : xs[2] }'
    ) == 20


def test_indexing_with_method_dispatch(session):
    """List indexing composes with the rest of expression syntax."""
    # `len(xs[1])` — index gives a sub-list, len returns its length.
    assert form_execute_text(
        session, "do { let xs = [[1, 2, 3], [4, 5]]; len(xs[1]) }"
    ) == 2
