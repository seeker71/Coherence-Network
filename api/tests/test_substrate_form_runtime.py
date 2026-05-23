"""Recipe-execution engine — Form expressions running, not just interning.

Each test exercises one faculty of the runtime. The shared shape:

- `form_execute_text(session, src)` parses + runs and returns a value
- `execute(session, ast, frame)` runs an already-parsed AST against a frame
- FailSignal / StopSignal flow through `choose` blocks at runtime, sharing
  the same exception types parser-level speculation uses

The runtime closes self-executing: Form is no longer just content-addressed
data, it's a living language whose recipes are runnable.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_execute_text
from app.services.substrate.category import BDomain
from app.services.substrate.form_runtime import Frame, execute
from app.services.substrate.form_speculation import FailSignal
from app.services.substrate.kernel import NodeID
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
# Literals + atoms
# ---------------------------------------------------------------------------


def test_int_literal(session):
    assert form_execute_text(session, "42") == 42


def test_bool_literals(session):
    assert form_execute_text(session, "true") is True
    assert form_execute_text(session, "false") is False


def test_string_literal(session):
    assert form_execute_text(session, '"hello"') == "hello"


def test_node_id_literal(session):
    result = form_execute_text(session, "@1.2.3.4")
    assert isinstance(result, NodeID)
    assert (result.package, result.level, result.type_, result.instance) == (1, 2, 3, 4)


# ---------------------------------------------------------------------------
# Arithmetic, comparison, logic
# ---------------------------------------------------------------------------


def test_arithmetic(session):
    assert form_execute_text(session, "1 + 2") == 3
    assert form_execute_text(session, "10 - 4") == 6
    assert form_execute_text(session, "3 * 4") == 12
    assert form_execute_text(session, "10 / 3") == 3      # integer division when both are ints
    assert form_execute_text(session, "10 % 3") == 1


def test_arithmetic_precedence(session):
    assert form_execute_text(session, "1 + 2 * 3") == 7
    assert form_execute_text(session, "2 * 3 + 1") == 7


def test_unary_negate(session):
    # form.py encodes `IntLit.value` as `value + 1` for the recipe NodeID,
    # and the bootstrap parser may not accept bare negative literals; use
    # the unary form which the parser supports.
    assert form_execute_text(session, "-5 + 10") == 5


def test_comparison(session):
    assert form_execute_text(session, "5 > 3") is True
    assert form_execute_text(session, "5 < 3") is False
    assert form_execute_text(session, "5 == 5") is True
    assert form_execute_text(session, "5 != 5") is False
    assert form_execute_text(session, "5 >= 5") is True
    assert form_execute_text(session, "5 <= 4") is False


def test_logic(session):
    assert form_execute_text(session, "true && true") is True
    assert form_execute_text(session, "true && false") is False
    assert form_execute_text(session, "false || true") is True
    assert form_execute_text(session, "!true") is False
    assert form_execute_text(session, "!false") is True


def test_logic_short_circuit(session):
    # `false && X` must not evaluate X — confirm by referencing an unbound
    # name as X. If short-circuit works, no NameError is raised.
    assert form_execute_text(session, "false && undefined_name") is False
    assert form_execute_text(session, "true || undefined_name") is True


# ---------------------------------------------------------------------------
# Conditionals, do/let
# ---------------------------------------------------------------------------


def test_if_then_else(session):
    assert form_execute_text(session, "if true then 1 else 2") == 1
    assert form_execute_text(session, "if false then 1 else 2") == 2


def test_if_then_no_else(session):
    assert form_execute_text(session, "if true then 1") == 1
    assert form_execute_text(session, "if false then 1") is None


def test_do_block_value_is_last_statement(session):
    assert form_execute_text(session, "do { 1; 2; 3 }") == 3


def test_let_binding(session):
    src = "do { let x = 5; let y = x + 3; y * 2 }"
    assert form_execute_text(session, src) == 16


def test_let_inner_scope_does_not_leak(session):
    # `do { let x = 1; x }` — fine. But `let x = 1` inside an inner do
    # block should not leak into an outer scope.
    src = "do { let outer = 1; do { let inner = 2; inner }; outer }"
    assert form_execute_text(session, src) == 1


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


def test_match_simple(session):
    src = 'match 2 { 1 => "one", 2 => "two", 3 => "three" }'
    assert form_execute_text(session, src) == "two"


def test_match_wildcard(session):
    src = 'match 99 { 1 => "one", 2 => "two", _ => "other" }'
    assert form_execute_text(session, src) == "other"


def test_match_no_arm_raises(session):
    """No arm matched and no `_` wildcard — the engine refuses to coerce
    to null. The expressive shape is `_ => ...` to name the fallback;
    silent null was the old behavior, and it hid the gap."""
    src = 'match 99 { 1 => "one", 2 => "two" }'
    with pytest.raises(LookupError) as exc_info:
        form_execute_text(session, src)
    assert "exhausted" in str(exc_info.value).lower()
    assert "scrutinee" in str(exc_info.value).lower()


def test_match_no_arm_with_explicit_wildcard_returns_null(session):
    """Explicit `_ => null` says what you mean; engine honors it."""
    src = 'match 99 { 1 => "one", 2 => "two", _ => null }'
    assert form_execute_text(session, src) is None


# ---------------------------------------------------------------------------
# Choose / fail / stop
# ---------------------------------------------------------------------------


def test_choose_first_success(session):
    # First candidate succeeds — its value is returned, others not tried.
    assert form_execute_text(session, "choose [1, 2, 3]") == 1


def test_choose_skips_failing_candidates(session):
    # First two fail, third succeeds.
    src = "choose [fail, fail, 42]"
    assert form_execute_text(session, src) == 42


def test_choose_all_fail_raises(session):
    with pytest.raises(FailSignal):
        form_execute_text(session, "choose [fail, fail, fail]")


def test_fail_outside_choose_raises(session):
    with pytest.raises(FailSignal):
        form_execute_text(session, "fail")


def test_choose_with_conditional_branches(session):
    src = """choose [
        do { let a = 5; if a > 10 then a else fail },
        do { let b = 5; if b > 3 then b else fail },
        do { let c = 5; c }
    ]"""
    assert form_execute_text(session, src) == 5


# ---------------------------------------------------------------------------
# with / .self
# ---------------------------------------------------------------------------


def test_with_self_resolves_to_subject(session):
    # `.self` inside a `with` block returns the subject value.
    src = "with 42 { .self }"
    assert form_execute_text(session, src) == 42


def test_with_self_in_expression(session):
    src = "with 10 { .self + 5 }"
    assert form_execute_text(session, src) == 15


def test_nested_with_innermost_subject_wins(session):
    src = "with 1 { with 2 { .self } }"
    assert form_execute_text(session, src) == 2


def test_self_outside_with_raises(session):
    with pytest.raises(NameError):
        form_execute_text(session, ".self")


# ---------------------------------------------------------------------------
# Identifiers + frame propagation
# ---------------------------------------------------------------------------


def test_identifier_lookup_via_frame(session):
    frame = Frame(bindings={"x": 7})
    from app.services.substrate.form import parse as form_parse
    ast = form_parse("x + 3")
    assert execute(session, ast, frame) == 10


def test_unbound_identifier_raises(session):
    with pytest.raises(NameError):
        form_execute_text(session, "nonexistent_name")


# ---------------------------------------------------------------------------
# Self-hosting closes the loop — registered templates run identically
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Function definitions + recursion — the backbone for engine-in-Form
# ---------------------------------------------------------------------------


def test_simple_function_definition_and_call(session):
    src = "do { defn double(x) = x * 2; double(7) }"
    assert form_execute_text(session, src) == 14


def test_function_with_multiple_params(session):
    src = "do { defn combine(a, b) = a * 10 + b; combine(3, 7) }"
    assert form_execute_text(session, src) == 37


def test_recursive_factorial(session):
    src = "do { defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6) }"
    assert form_execute_text(session, src) == 720


def test_recursive_fibonacci(session):
    src = "do { defn fib(n) = if n <= 1 then n else fib(n - 1) + fib(n - 2); fib(10) }"
    assert form_execute_text(session, src) == 55


def test_function_composition(session):
    src = """do {
        defn sumto(n) = if n == 0 then 0 else n + sumto(n - 1);
        defn double(x) = x * 2;
        double(sumto(10))
    }"""
    assert form_execute_text(session, src) == 110


def test_closure_captures_defining_frame(session):
    """Functions capture the frame they were defined in, not the caller's."""
    src = """do {
        let factor = 3;
        defn scale(x) = x * factor;
        do {
            let factor = 99;
            scale(5)
        }
    }"""
    # Inner `factor = 99` should NOT affect scale — closure captures
    # the outer frame where scale was defined.
    assert form_execute_text(session, src) == 15


def test_function_call_unknown_raises(session):
    with pytest.raises(NameError):
        form_execute_text(session, "no_such_fn(1, 2)")


def test_function_call_wrong_arity_raises(session):
    src = "do { defn pair(a, b) = a + b; pair(1) }"
    with pytest.raises(TypeError):
        form_execute_text(session, src)


# ---------------------------------------------------------------------------
# Tree navigation — the fractal/holographic seams
# ---------------------------------------------------------------------------
#
# Every entity in the substrate is composed bottom-up. A Memory cell's
# Blueprint isn't `{name: ~String, ...}` — it's a 4-level deep tree
# where each field-blueprint is itself a composition all the way down
# to numeric trivials. The dot is the seam between levels.


def _seed_memory_cell(session):
    """Create a memory cell with full Blueprint + CTOR tree."""
    from app.services.substrate.markdown_frontend import ingest_markdown_text
    import tempfile, os
    body = """---
name: test memory
description: a test cell for tree navigation
type: feedback
---

Body of the memory.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        path = f.name
    try:
        from app.services.substrate import ingest_memory_file
        from pathlib import Path
        ingest_memory_file(session, Path(path))
        session.flush()
    finally:
        os.unlink(path)


def test_cell_to_blueprint_navigation(session):
    """`.blueprint` reaches the cell's Blueprint NodeID."""
    _seed_memory_cell(session)
    result = form_execute_text(session, '@memory("test memory").blueprint')
    assert isinstance(result, NodeID)
    # Memory cells share Blueprint @1.5.4.1 (composite at level 5)
    assert result.level == 5
    assert result.type_ == 4  # B_Basic.DOMAIN


def test_blueprint_category(session):
    """`.category` reaches the category NodeID — the type-of-the-type."""
    _seed_memory_cell(session)
    result = form_execute_text(session, '@memory("test memory").blueprint.category')
    assert isinstance(result, NodeID)
    # Memory category is @1.2.4.6 in the intentional domain band.
    assert (result.package, result.level, result.type_, result.instance) == (
        1, 2, 4, BDomain.MEMORY,
    )


def test_blueprint_nchildren(session):
    """A Memory Blueprint has one child per frontmatter field shape — the
    exact count depends on the frontmatter the cell was ingested with."""
    _seed_memory_cell(session)
    n = form_execute_text(session, '@memory("test memory").blueprint.nchildren')
    assert n >= 3  # at least name + description + type


def test_blueprint_child_navigation(session):
    """`.child(n)` reaches the n-th child Blueprint — itself a composite."""
    _seed_memory_cell(session)
    child0 = form_execute_text(session, '@memory("test memory").blueprint.child(0)')
    assert isinstance(child0, NodeID)
    # First field-blueprint sits at level 4
    assert child0.level == 4


def test_recursive_descent_to_leaf(session):
    """Walk all the way from cell → blueprint → field → sub-field → leaf."""
    _seed_memory_cell(session)
    # Memory bp [4 children] -> child(0) [field-bp, 2 children] -> child(1) [leaf]
    leaf = form_execute_text(
        session, '@memory("test memory").blueprint.child(0).child(1)'
    )
    assert isinstance(leaf, NodeID)
    # Leaf is a trivial — level 1, type STRING
    assert leaf.level == 1


def test_ctor_tree_navigation(session):
    """The CTOR recipe is also a tree — water phase, composed values."""
    _seed_memory_cell(session)
    ctor = form_execute_text(session, '@memory("test memory").ctor')
    assert isinstance(ctor, NodeID)
    n = form_execute_text(session, '@memory("test memory").ctor.nchildren')
    assert n >= 3  # one recipe-child per frontmatter value


def test_node_id_fields(session):
    """A NodeID exposes its 4-tuple as primitive integer fields."""
    _seed_memory_cell(session)
    pkg = form_execute_text(session, '@memory("test memory").blueprint.package')
    level = form_execute_text(session, '@memory("test memory").blueprint.level')
    type_ = form_execute_text(session, '@memory("test memory").blueprint.type')
    instance = form_execute_text(session, '@memory("test memory").blueprint.instance')
    assert (pkg, level, type_, instance) == (1, 5, 4, 1)


def test_cell_other_fields(session):
    _seed_memory_cell(session)
    assert form_execute_text(session, '@memory("test memory").domain') == "memory"
    assert form_execute_text(session, '@memory("test memory").name') == "test memory"


def test_arithmetic_on_tree_walk_result(session):
    """Tree walks return values — they compose with the rest of the language."""
    _seed_memory_cell(session)
    src = '(@memory("test memory").blueprint.nchildren - 1) * 2'
    n = form_execute_text(session, '@memory("test memory").blueprint.nchildren')
    assert form_execute_text(session, src) == (n - 1) * 2


def test_unknown_field_raises(session):
    _seed_memory_cell(session)
    with pytest.raises(AttributeError):
        form_execute_text(session, '@memory("test memory").not_a_field')


def _seed_structured_memory_cell(session):
    """Create a memory cell with the structured-CTOR encoder so .field()
    fall-through can walk LET-bindings by key."""
    from app.services.substrate.markdown_frontend import ingest_markdown_text
    import tempfile, os
    body = """---
name: structured test memory
description: cell with structured-CTOR for field-by-name access
type: feedback
---

Body of the memory.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        path = f.name
    try:
        from app.services.substrate import ingest_memory_file
        from pathlib import Path
        ingest_memory_file(session, Path(path), structured=True)
        session.flush()
    finally:
        os.unlink(path)


def test_structured_ctor_field_by_name(session):
    """Frontmatter keys interned via structured-CTOR are reachable as
    cell fields directly. The human reads YAML, the substrate walks LET,
    the AI bridges — same value across all three voices.
    """
    _seed_structured_memory_cell(session)
    # `name` is a builtin cell field; `description` and `type` fall through
    # to the structured-CTOR LET-binding walk.
    assert form_execute_text(
        session, '@memory("structured test memory").description'
    ) == "cell with structured-CTOR for field-by-name access"
    assert form_execute_text(
        session, '@memory("structured test memory").type'
    ) == "feedback"


def test_structured_ctor_unknown_field_still_raises(session):
    """Field-by-name fall-through is additive: when no LET-binding matches,
    the AttributeError still fires (and now lists the structured-CTOR
    pathway in its hint)."""
    _seed_structured_memory_cell(session)
    with pytest.raises(AttributeError, match="frontmatter key"):
        form_execute_text(
            session, '@memory("structured test memory").not_a_real_field'
        )


def test_child_out_of_range_raises(session):
    _seed_memory_cell(session)
    with pytest.raises(IndexError):
        form_execute_text(session, '@memory("test memory").blueprint.child(99)')


def test_self_hosted_keywords_execute_identically(session):
    """The keyword self-hosting (bootstrap_self_host) already proves that
    registered (pattern, template) pairs intern to the same Recipe NodeIDs
    as the bootstrap. This test confirms they ALSO run identically through
    the recipe-execution engine.

    The full loop: substrate-resident pattern + template -> parser parses
    via registry -> AST built via template DSL -> runtime executes the AST.
    """
    from app.services.substrate import (
        bootstrap_self_host,
        bootstrap_self_host_operators,
    )

    bootstrap_self_host(session)
    bootstrap_self_host_operators(session)

    # Each pair: same expression via bootstrap path AND via registry path.
    pairs = [
        ("1 + 2 * 3", 7),
        ("if true then 10 else 20", 10),
        ("if false then 10 else 20", 20),
        ("do { let x = 5; x + 3 }", 8),
        ("unless false then 42", 42),
        ("whenever true do 99", 99),
        ("choose [fail, fail, 7]", 7),
        ("match 2 { 1 => 10, 2 => 20, _ => 30 }", 20),
    ]

    for src, expected in pairs:
        bootstrap_value = form_execute_text(session, src, prefer_registered=False)
        registered_value = form_execute_text(session, src, prefer_registered=True)
        assert bootstrap_value == expected, f"bootstrap path failed for {src!r}"
        assert registered_value == expected, f"registry path failed for {src!r}"
        assert bootstrap_value == registered_value, (
            f"paths diverge for {src!r}: "
            f"bootstrap={bootstrap_value} registered={registered_value}"
        )
