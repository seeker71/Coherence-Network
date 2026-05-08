"""Tests for Form — the substrate-native language.

Covers lexer, parser, and evaluator end-to-end against an in-memory
SQLite substrate.
"""
from __future__ import annotations

import textwrap

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    NodeID,
    form_evaluate_text,
    form_parse,
    form_serialize_cell,
    form_serialize_node_id,
    ingest_memory_file,
)
from app.services.substrate.form import (
    CellRef,
    NodeIDLit,
    Projection,
    Query,
    TrivialRef,
    tokenize,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


def test_lexer_basic_tokens():
    toks = tokenize("@1.2.3.4 ~Memory |> ?equivalent")
    kinds = [t.kind for t in toks if t.kind != "EOF"]
    assert "AT" in kinds
    assert "INT" in kinds
    assert "DOT" in kinds
    assert "TILDE" in kinds
    assert "IDENT" in kinds
    assert "PROJECT" in kinds
    assert "QMARK" in kinds


def test_lexer_string_with_spaces():
    toks = tokenize('@memory("User biographical arc")')
    string_toks = [t for t in toks if t.kind == "STRING"]
    assert len(string_toks) == 1
    assert "User biographical arc" in string_toks[0].value


def test_lexer_skips_comments():
    toks = tokenize("# comment\n~Memory")
    kinds = [t.kind for t in toks if t.kind != "EOF"]
    assert "TILDE" in kinds
    assert "IDENT" in kinds


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parse_node_id_literal():
    ast = form_parse("@1.5.4.11")
    assert isinstance(ast, NodeIDLit)
    assert (ast.package, ast.level, ast.type_, ast.instance) == (1, 5, 4, 11)


def test_parse_trivial_ref():
    ast = form_parse("~Memory")
    assert isinstance(ast, TrivialRef)
    assert ast.name == "Memory"


def test_parse_bare_domain_ref():
    ast = form_parse("@memory")
    assert isinstance(ast, CellRef)
    assert ast.domain == "memory"
    assert ast.name is None


def test_parse_cell_ref_with_name():
    ast = form_parse('@memory("User biographical arc")')
    assert isinstance(ast, CellRef)
    assert ast.domain == "memory"
    assert ast.name == "User biographical arc"


def test_parse_cell_ref_with_ident_name():
    ast = form_parse("@memory(arrival_relational_ground)")
    assert isinstance(ast, CellRef)
    assert ast.name == "arrival_relational_ground"


def test_parse_projection():
    ast = form_parse("@memory(x) |> ~Presence")
    assert isinstance(ast, Projection)
    assert isinstance(ast.cell, CellRef)
    assert isinstance(ast.blueprint, TrivialRef)
    assert ast.blueprint.name == "Presence"


def test_parse_query_equivalent():
    ast = form_parse("?equivalent @memory(x)")
    assert isinstance(ast, Query)
    assert ast.kind == "equivalent"


def test_parse_query_cells_with_filter():
    ast = form_parse('?cells where domain == "memory"')
    assert isinstance(ast, Query)
    assert ast.kind == "cells"
    assert len(ast.filters) == 1
    assert ast.filters[0].field == "domain"
    assert ast.filters[0].value == "memory"


def test_parse_query_cells_projection():
    ast = form_parse("?cells |> ~Presence")
    assert isinstance(ast, Query)
    assert ast.kind == "cells"
    assert isinstance(ast.arg, TrivialRef)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


MEMORY_TPL = textwrap.dedent("""\
    ---
    name: {name}
    description: a description
    type: feedback
    ---
    Body content here.
    """)


def test_eval_node_id_literal(session):
    result = form_evaluate_text(session, "@1.2.3.4")
    assert result.kind == "node_id"
    assert result.value == NodeID(1, 2, 3, 4)


def test_eval_trivial_ref(session):
    result = form_evaluate_text(session, "~Memory")
    assert result.kind == "node_id"
    assert result.value.type_ == 4  # BBasic.DOMAIN


def test_eval_bare_domain_ref(session):
    result = form_evaluate_text(session, "@memory")
    assert result.kind == "node_id"
    assert result.value.type_ == 4  # same as ~Memory


def test_eval_cell_ref_lookup(session, tmp_path):
    p = tmp_path / "x.md"
    p.write_text(MEMORY_TPL.format(name="X"))
    ingest_memory_file(session, p)

    result = form_evaluate_text(session, '@memory("X")')
    assert result.kind == "cell"
    assert result.value.name == "X"


def test_eval_cell_ref_missing_raises(session):
    with pytest.raises(LookupError):
        form_evaluate_text(session, '@memory("does-not-exist")')


def test_eval_projection_compatible(session, tmp_path):
    p = tmp_path / "x.md"
    p.write_text(MEMORY_TPL.format(name="X"))
    ingest_memory_file(session, p)

    result = form_evaluate_text(session, '@memory("X") |> ~Memory')
    assert result.kind == "view"
    assert result.value.compatible is True


def test_eval_query_equivalent(session, tmp_path):
    for n in ["A", "B", "C"]:
        p = tmp_path / f"{n.lower()}.md"
        p.write_text(MEMORY_TPL.format(name=n))
        ingest_memory_file(session, p)

    result = form_evaluate_text(session, '?equivalent @memory("A")')
    assert result.kind == "cells"
    names = {c.name for c in result.value}
    # B and C are structurally equivalent to A; A is excluded
    assert "B" in names
    assert "C" in names
    assert "A" not in names


def test_eval_query_cells_with_filter(session, tmp_path):
    for n in ["X", "Y"]:
        p = tmp_path / f"{n.lower()}.md"
        p.write_text(MEMORY_TPL.format(name=n))
        ingest_memory_file(session, p)

    result = form_evaluate_text(session, '?cells where domain == "memory"')
    assert result.kind == "cells"
    assert len(result.value) == 2


def test_eval_query_cells_projection(session, tmp_path):
    for n in ["X", "Y"]:
        p = tmp_path / f"{n.lower()}.md"
        p.write_text(MEMORY_TPL.format(name=n))
        ingest_memory_file(session, p)

    result = form_evaluate_text(session, '?cells |> ~Memory')
    assert result.kind == "views"
    # All ingested memories should be compatible with ~Memory (their domain blueprint)
    for v in result.value:
        assert v.compatible is True


# ---------------------------------------------------------------------------
# Serialization (round-trip)
# ---------------------------------------------------------------------------


def test_serialize_node_id():
    assert form_serialize_node_id(NodeID(1, 5, 4, 11)) == "@1.5.4.11"


def test_serialize_then_parse_roundtrip():
    nid = NodeID(2, 7, 3, 42)
    text = form_serialize_node_id(nid)
    ast = form_parse(text)
    assert isinstance(ast, NodeIDLit)
    assert (ast.package, ast.level, ast.type_, ast.instance) == (2, 7, 3, 42)


# ---------------------------------------------------------------------------
# Recipe Form — code expressions that intern as Recipes
# ---------------------------------------------------------------------------


def test_eval_math_expression(session):
    """1 + 2 interns as a Math.PLUS recipe; result is a Recipe NodeID."""
    result = form_evaluate_text(session, "1 + 2")
    assert result.kind == "recipe"
    # Math is RBasic.MATH = 12; PLUS is instance 1
    assert result.value.type_ == 12
    assert result.value.instance == 1


def test_math_dedup_identical_expressions(session):
    """Two parses of '1 + 2' return the same Recipe NodeID."""
    a = form_evaluate_text(session, "1 + 2")
    b = form_evaluate_text(session, "1 + 2")
    assert a.value == b.value


def test_math_distinct_expressions_differ(session):
    """1 + 2 and 1 - 2 are distinct shapes."""
    a = form_evaluate_text(session, "1 + 2")
    b = form_evaluate_text(session, "1 - 2")
    assert a.value != b.value


def test_compare_expression(session):
    result = form_evaluate_text(session, "x > 5")
    assert result.kind == "recipe"
    assert result.value.type_ == 13  # RBasic.COMPARE


def test_logic_expression(session):
    result = form_evaluate_text(session, "a && b")
    assert result.kind == "recipe"
    assert result.value.type_ == 14  # RBasic.LOGIC


def test_unary_negation(session):
    result = form_evaluate_text(session, "!flag")
    assert result.kind == "recipe"
    assert result.value.type_ == 14  # RBasic.LOGIC


def test_if_then_else(session):
    result = form_evaluate_text(session, "if x > 5 then 10 else 20")
    assert result.kind == "recipe"
    assert result.value.type_ == 11  # RBasic.COND


def test_if_then_without_else(session):
    result = form_evaluate_text(session, "if x then y")
    assert result.kind == "recipe"
    assert result.value.type_ == 11  # RBasic.COND


def test_if_then_else_distinct_from_if_then(session):
    """if-with-else and if-without-else have distinct shapes (different category instance)."""
    a = form_evaluate_text(session, "if x then y")
    b = form_evaluate_text(session, "if x then y else z")
    assert a.value != b.value


def test_do_block(session):
    result = form_evaluate_text(session, "do { let x = 5; x + 1 }")
    assert result.kind == "recipe"
    # Block = RBasic 9, DO = instance 1
    assert result.value.type_ == 9
    assert result.value.instance == 1


def test_match_expression(session):
    result = form_evaluate_text(
        session, 'match x { 1 => "one", 2 => "two", _ => "other" }'
    )
    assert result.kind == "recipe"
    assert result.value.type_ == 19  # RBasic.MATCH


# ---------------------------------------------------------------------------
# Angelic nondeterminism — choose / fail / stop (BML lineage)
# ---------------------------------------------------------------------------


def test_choose_expression(session):
    """choose [a, b, c] is the speculation primitive."""
    result = form_evaluate_text(session, "choose [1, 2, 3]")
    assert result.kind == "recipe"
    # Choice = RBasic 20, CHOOSE = instance 1
    assert result.value.type_ == 20
    assert result.value.instance == 1


def test_fail_is_leaf_recipe(session):
    """fail is a trivial leaf — no children, level BASIC."""
    result = form_evaluate_text(session, "fail")
    assert result.kind == "recipe"
    assert result.value.type_ == 20  # CHOICE
    assert result.value.instance == 2  # FAIL


def test_stop_is_leaf_recipe(session):
    """stop commits speculation."""
    result = form_evaluate_text(session, "stop")
    assert result.kind == "recipe"
    assert result.value.type_ == 20  # CHOICE
    assert result.value.instance == 3  # STOP


def test_choose_with_fail_branches(session):
    """A realistic angelic-nondeterminism expression."""
    result = form_evaluate_text(session, "choose [a + 1, fail, b * 2]")
    assert result.kind == "recipe"
    assert result.value.type_ == 20  # CHOICE
    # The expression interns successfully — children are mixed (Math + leaf + Math)
    assert result.value.instance == 1  # CHOOSE

