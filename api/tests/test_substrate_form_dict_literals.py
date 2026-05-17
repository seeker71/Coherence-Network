"""Dict literals + field access on dicts.

Real gap: `{a: 1, b: 2}` raised SyntaxError "unexpected LBRACE". Form had
no dict-literal syntax, so structured records had no surface expression.
This adds `DictExpr` (parser + runtime) and extends `_resolve_access` so
`m.a` works on Python dicts.

The runtime yields Python dicts for ergonomics; honoring the structural
composition discipline at the substrate-recipe layer (interning as
R_Block.SEQUENCE of LET pairs) is a follow-on layer.
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
# Dict literals
# ---------------------------------------------------------------------------


def test_simple_dict_literal(session):
    assert form_execute_text(session, "{a: 1, b: 2}") == {"a": 1, "b": 2}


def test_empty_dict(session):
    assert form_execute_text(session, "{}") == {}


def test_dict_with_computed_values(session):
    assert form_execute_text(session, "{a: 1 + 2, b: 5 * 3}") == {"a": 3, "b": 15}


def test_dict_with_string_keys(session):
    assert form_execute_text(session, '{"x": 100, "y": 200}') == {"x": 100, "y": 200}


def test_dict_with_mixed_value_types(session):
    v = form_execute_text(session, '{a: 1, b: "hello", c: true}')
    assert v == {"a": 1, "b": "hello", "c": True}


# ---------------------------------------------------------------------------
# Field access on dicts
# ---------------------------------------------------------------------------


def test_dict_field_access(session):
    assert form_execute_text(session, "{a: 1, b: 2}.a") == 1
    assert form_execute_text(session, "{a: 1, b: 2}.b") == 2


def test_dict_field_via_let(session):
    assert form_execute_text(
        session, "do { let m = {x: 10, y: 20}; m.x + m.y }"
    ) == 30


def test_dict_missing_field_raises(session):
    with pytest.raises(AttributeError):
        form_execute_text(session, "{a: 1}.missing")


# ---------------------------------------------------------------------------
# Composition with lists, indexing, methods
# ---------------------------------------------------------------------------


def test_list_of_dicts_with_indexed_field(session):
    """The composition test: lists hold dicts, index gives one, field gives value."""
    assert form_execute_text(
        session,
        "do { let xs = [{a: 1}, {a: 2}, {a: 3}]; xs[1].a }"
    ) == 2


def test_map_extracting_fields(session):
    """`map(fn, [dicts])` works because field access works on dict elements."""
    v = form_execute_text(
        session,
        'do { defn get_a(d) = d.a; map(get_a, [{a: 1}, {a: 2}, {a: 3}]) }'
    )
    assert v == [1, 2, 3]


def test_nested_dict(session):
    """`{a: {b: 1}}.a.b` chains field access."""
    assert form_execute_text(
        session, "{a: {b: 42}}.a.b"
    ) == 42
