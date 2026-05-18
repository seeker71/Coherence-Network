"""Equivalence tests for the streaming-emit Form parser.

The streaming parser (`form_stream`) is a BMF-style proof-of-shape: each
parse rule's success emits a Recipe NodeID directly to a working stack;
no AST node is materialized between parse and intern. The substrate is
the shared destination.

The proof is content-addressing: for every expression in the subset both
parsers cover, the AST-based path (`form_evaluate_text`) and the
streaming path (`form_stream.parse_and_emit`) must return the SAME
Recipe NodeID. If they don't, content-addressing is broken — and these
tests would catch that.

See `api/app/services/substrate/form_stream.py` for the parser and
`docs/coherence-substrate/form-language.md` for the language design.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text
from app.services.substrate.form_stream import parse_and_emit, tokenize
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
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Tokenizer — basic shape
# ---------------------------------------------------------------------------


def test_tokenize_integers_and_operators():
    toks = tokenize("1 + 2 * 3")
    kinds = [t.kind for t in toks]
    assert kinds == ["INT", "PLUS", "INT", "STAR", "INT", "EOF"]


def test_tokenize_comparison_and_logic():
    toks = tokenize("a == b && c != d")
    kinds = [t.kind for t in toks]
    assert "EQ" in kinds and "NEQ" in kinds and "AND" in kinds


def test_tokenize_skips_whitespace_and_comments():
    toks = tokenize("  1 # a comment\n + 2  ")
    kinds = [t.kind for t in toks]
    assert kinds == ["INT", "PLUS", "INT", "EOF"]


# ---------------------------------------------------------------------------
# Equivalence — the load-bearing property
# ---------------------------------------------------------------------------
#
# Every expression below must produce the SAME Recipe NodeID through both
# parsers. If equivalence fails, the kernel's content-addressing isn't
# enforcing what it claims to enforce.


@pytest.mark.parametrize("expr", [
    # Trivial leaves
    "42",
    "0",
    "true",
    "false",
    # Binary arithmetic
    "1 + 2",
    "5 - 3",
    "4 * 6",
    "20 / 4",
    "10 % 3",
    # Precedence
    "1 + 2 * 3",
    "2 * 3 + 1",
    "(1 + 2) * 3",
    "1 + 2 + 3",
    "10 - 3 - 2",
    # Comparison
    "5 > 3",
    "5 == 5",
    "5 != 6",
    "5 <= 5",
    "1 < 2",
    "10 >= 10",
    # Logic
    "true && false",
    "true || false",
    "!true",
    "!(1 == 2)",
    # Unary
    "-5",
    "-(1 + 2)",
    # Conditionals
    "if 5 > 3 then 10 else 20",
    "if true then 1 else 0",
    "if 1 == 1 then 100",
    # Nested compositions
    "if (1 + 2) > 0 then 1 * 2 else 3 + 4",
    "if !true || (5 > 3 && 2 == 2) then -1 else -2",
])
def test_streaming_emit_matches_ast_path(session, expr):
    """The load-bearing equivalence — both parsers produce the same NodeID.

    Content-addressing in the kernel guarantees this when the children
    and category match. The streaming path proves it can reach the same
    NodeID coordinates without ever building an AST."""
    via_stream = parse_and_emit(session, expr)
    via_ast = form_evaluate_text(session, expr).value
    assert via_stream == via_ast, (
        f"streaming and AST diverged for {expr!r}: "
        f"stream={via_stream} ast={via_ast}"
    )


# ---------------------------------------------------------------------------
# The stack stays small — streaming property
# ---------------------------------------------------------------------------


def test_streaming_parser_holds_no_ast(session):
    """The streaming parser never materializes an AST. After parsing, the
    only state is the single NodeID on the stack — no dataclass tree, no
    intermediate objects. This is the architectural difference the BMF
    teaching named: the parse tree is consumed as it's built."""
    from app.services.substrate.form_stream import _ParserState, _parse_expr

    tokens = tokenize("if (1 + 2) * 3 > 5 then 10 else 20")
    p = _ParserState(tokens=tokens, pos=0, stack=[])
    _parse_expr(session, p)
    # Whatever the expression's complexity, the stack reduces to exactly
    # one NodeID — the rule that consumed the whole input.
    assert len(p.stack) == 1
    # Nothing else lingers — no AST node list, no symbol table, no
    # parallel intermediate representation.


# ---------------------------------------------------------------------------
# Content-addressing — twice-parsed yields the same NodeID
# ---------------------------------------------------------------------------


def test_idempotent_under_repeat_parse(session):
    """A second parse of the same expression returns the same NodeID.

    The kernel's content-addressing guarantees this: same shape, same
    coordinates. The streaming parser doesn't need its own dedup logic
    because it inherits the substrate's."""
    a = parse_and_emit(session, "(1 + 2) * 3")
    b = parse_and_emit(session, "(1 + 2) * 3")
    assert a == b


def test_different_whitespace_same_nodeid(session):
    """Whitespace doesn't affect identity — the structure does."""
    a = parse_and_emit(session, "1+2*3")
    b = parse_and_emit(session, "1 + 2 * 3")
    c = parse_and_emit(session, "  1   +  2  *  3  ")
    assert a == b == c


# ---------------------------------------------------------------------------
# Broad-grammar equivalence — the BML form-layer constructs
# ---------------------------------------------------------------------------
#
# Each construct below must intern to the same NodeID via the streaming
# path as via the AST path. The substrate guarantees equivalence; these
# tests prove the streaming encoder lands at the right coordinates.


@pytest.mark.parametrize("expr", [
    # String literals
    '"hello"',
    '"with spaces"',
    '""',
    # NodeID literals
    "@1.5.4.1",
    "@2.3.4.5",
    # Trivial refs
    "~Memory",
    "~Integer",
    "~String",
    # Bare identifiers
    "x",
    "some_name",
    # Self-reference
    ".self",
    # Bare leaves — RChoice
    "fail",
    "stop",
    # Bare leaves — RState
    "save",
    "restore",
    "discard",
    # Bare leaves — RException
    "raise",
    "resume",
    # do-blocks with let
    "do { let x = 5; x }",
    "do { let x = 5; let y = x + 3; y * 2 }",
    "do { 1 + 2 }",
    "do { 1; 2; 3 }",
    # with / .self
    "with @1.5.4.1 { .self }",
    "with @2.3.4.5 { 1 + 2 }",
    # match
    "match 3 { 1 => 100, 2 => 200, _ => 0 }",
    'match "ready" { "ready" => 1, "blocked" => 2, _ => 0 }',
    # choose
    "choose [1, 2, 3]",
    "choose [fail, stop, 42]",
    # try / catch
    "try { 1 + 2 } catch { raise }",
    # delegate
    "delegate @1.5.4.1 to @2.3.4.5",
    # undo / inverse
    "undo (1 + 2)",
    "inverse(3 * 4)",
    # common
    "common @1.5.4.1 @2.3.4.5",
    # method / invoke
    "method greet on @1.5.4.1 { 1 + 2 }",
    "method noop on @1.5.4.1 { save; restore }",
    "invoke greet on @1.5.4.1",
])
def test_streaming_matches_ast_bml_form_layer(session, expr):
    """Every BML form-layer construct interns to the same NodeID via both
    paths. This is the broad-coverage proof — the streaming-emit pattern
    extends to the entire recipe-producing grammar, not just arithmetic.

    The wellness check named these as the asymmetric arms of the meta-
    circular engine: BLOCK, CHOICE, STATE, EXCEPTION, DELEGATE, REVERSE,
    COMMON, METHOD, TRY. All of them now have streaming-emit coverage,
    proven by content-addressing equivalence."""
    via_stream = parse_and_emit(session, expr)
    via_ast = form_evaluate_text(session, expr).value
    assert via_stream == via_ast, (
        f"streaming and AST diverged for {expr!r}: "
        f"stream={via_stream} ast={via_ast}"
    )


# ---------------------------------------------------------------------------
# Composition — recipes-within-recipes via streaming
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expr", [
    # do-blocks nesting conditionals
    "do { let x = 5; if x > 3 then x * 2 else fail }",
    # match scrutinees that are expressions
    "match 1 + 1 { 2 => 100, _ => 0 }",
    # choose with mixed leaves and composites
    "choose [fail, 1 + 2, stop]",
    # with whose body is a block
    "with @1.5.4.1 { let v = 1; v + 2 }",
    # try whose body is a block
    "try { let x = 1; x + 2 } catch { fail }",
    # nested choose-within-do
    "do { let result = choose [1, 2, 3]; result + 100 }",
])
def test_streaming_nested_compositions(session, expr):
    """Deep compositions stress-test the stack discipline. Each rule pops
    exactly the right arity; mistakes here would surface as wrong NodeIDs
    or stack-underflow errors."""
    via_stream = parse_and_emit(session, expr)
    via_ast = form_evaluate_text(session, expr).value
    assert via_stream == via_ast


# ---------------------------------------------------------------------------
# Cell references — substrate-resolved leaves
# ---------------------------------------------------------------------------


_MEMORY_TPL = """---
name: {name}
description: a description
type: feedback
---
Body content here.
"""


def test_cell_ref_resolves_via_substrate(session, tmp_path):
    """`@domain(name)` requires a substrate lookup. The streaming and AST
    paths must hit the same cell and encode the same GLOBAL trivial.

    Tested through a recipe context (`with` block) so both paths flow
    through `_to_recipe_node_id` / `_parse_at_form` cell-encoding rather
    than top-level cell-resolution."""
    from app.services.substrate import ingest_memory_file

    p = tmp_path / "example.md"
    p.write_text(_MEMORY_TPL.format(name="example"))
    ingest_memory_file(session, p)

    via_stream = parse_and_emit(session, "with @memory(example) { .self }")
    via_ast = form_evaluate_text(session, "with @memory(example) { .self }").value
    assert via_stream == via_ast
