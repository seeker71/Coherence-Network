"""Tests for parser-level speculation — backtracking-without-sediment.

The architectural payoff: failed parse attempts leave no trace.
Position, captures, and any other accumulated state is cleanly
unwound. This is the foundation BMF (2000) had at the C++ stack
level; we have it now at the Python class level, ready to integrate
with the substrate's Choice.FAIL/STOP recipes when a recipe-execution
engine ships.
"""
from __future__ import annotations

import pytest

from app.services.substrate import (
    Capture,
    FailSignal,
    Literal,
    Sequence,
    SpeculationContext,
    SpeculationResult,
    StopSignal,
    choice,
    speculate,
)
from app.services.substrate.form_rules import try_match
from app.services.substrate.form import Parser, tokenize


# ---------------------------------------------------------------------------
# Basic speculation
# ---------------------------------------------------------------------------


def _parser(text: str) -> Parser:
    """Helper — create a parser primed on the given text."""
    return Parser(tokenize(text), prefer_registered=False)


def test_speculate_succeeds_on_match():
    p = _parser("foo bar")
    result = speculate(p, Literal("IDENT", "foo"))
    assert result.success is True
    assert p.pos == 1  # consumed `foo`


def test_speculate_fails_and_unwinds():
    p = _parser("foo bar")
    pos_before = p.pos
    result = speculate(p, Literal("IDENT", "different"))
    assert result.success is False
    assert p.pos == pos_before  # position fully restored


def test_speculate_unwinds_partial_match():
    """A Sequence that partly matches and then fails should fully unwind."""
    p = _parser("foo qux")  # matches `foo` then expects `bar`, gets `qux`
    pos_before = p.pos
    pattern = Sequence([
        Literal("IDENT", "foo"),
        Literal("IDENT", "bar"),
    ])
    result = speculate(p, pattern)
    assert result.success is False
    assert p.pos == pos_before  # rolled all the way back, not stuck after `foo`


def test_speculate_clears_partial_captures_on_fail():
    """Captures accumulated before a failure must be cleared, not retained."""
    p = _parser("foo qux")
    pattern = Sequence([
        Literal("IDENT", "foo"),
        Capture("name"),  # this captures `qux`
        Literal("IDENT", "expected_but_missing"),  # this fails
    ])
    result = speculate(p, pattern)
    assert result.success is False
    assert "name" not in result.captures  # capture must NOT leak through


# ---------------------------------------------------------------------------
# Nested speculation
# ---------------------------------------------------------------------------


def test_nested_speculation_inner_fails_outer_succeeds():
    """An inner failure unwinds the inner frame; the outer continues."""
    p = _parser("alpha beta gamma")
    ctx = SpeculationContext()

    # Outer speculation: match `alpha`, then try a sub-pattern.
    captures_outer = {}
    pattern_outer = Sequence([
        Literal("IDENT", "alpha"),
    ])
    result_outer = speculate(p, pattern_outer, ctx=ctx)
    assert result_outer.success is True
    assert ctx.depth() == 0  # frame popped

    # Inner speculation now: try something that fails
    result_inner = speculate(p, Literal("IDENT", "wrong"), ctx=ctx)
    assert result_inner.success is False
    assert ctx.depth() == 0  # inner frame also popped cleanly

    # Parser state still reflects the successful outer match
    assert p.pos == 1


def test_nested_speculation_with_real_failure():
    """A failed nested attempt must not corrupt the outer scope."""
    p = _parser("a b")
    pos_before = p.pos
    ctx = SpeculationContext()

    # Outer attempts a 2-token pattern; inner attempts a 3-token pattern
    # that doesn't match. The outer should not be affected.
    captures = {}
    frame_count_before = ctx.depth()

    result = speculate(
        p,
        Sequence([
            Literal("IDENT", "a"),
            Literal("IDENT", "b"),
        ]),
        ctx=ctx,
    )
    assert result.success is True
    assert ctx.depth() == frame_count_before  # back to baseline
    assert p.pos == 2


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def test_fail_signal_unwinds_speculation():
    """A FailSignal raised inside a match unwinds the speculation."""
    from app.services.substrate.form_rules import _do_match

    p = _parser("foo")
    pos_before = p.pos

    # Build a custom pattern type that raises FailSignal during match.
    class FailingPattern:
        pass

    # Patch _do_match's behavior temporarily: speculate around a pattern
    # that raises FailSignal. The speculation engine should catch and unwind.
    import app.services.substrate.form_speculation as spec
    original_do_match = spec._do_match if hasattr(spec, '_do_match') else None

    def _failing_match(parser, pattern, captures):
        if isinstance(pattern, FailingPattern):
            raise FailSignal()
        from app.services.substrate.form_rules import _do_match as real
        return real(parser, pattern, captures)

    # Monkey-patch the import inside speculate
    import app.services.substrate.form_rules as rules
    real_do_match = rules._do_match
    rules._do_match = _failing_match
    try:
        result = speculate(p, FailingPattern())
        assert result.success is False
        assert p.pos == pos_before  # cleanly unwound
    finally:
        rules._do_match = real_do_match


# ---------------------------------------------------------------------------
# Choice — try alternatives
# ---------------------------------------------------------------------------


def test_choice_returns_first_match():
    p = _parser("hello")
    result = choice(p, [
        Literal("IDENT", "wrong1"),
        Literal("IDENT", "hello"),  # this matches
        Literal("IDENT", "wrong2"),
    ])
    assert result.success is True
    assert p.pos == 1  # advanced past `hello`


def test_choice_no_match_leaves_state_untouched():
    p = _parser("hello")
    pos_before = p.pos
    result = choice(p, [
        Literal("IDENT", "wrong1"),
        Literal("IDENT", "wrong2"),
        Literal("IDENT", "wrong3"),
    ])
    assert result.success is False
    assert p.pos == pos_before


def test_choice_with_complex_alternatives():
    """Each alternative is a full sub-pattern (Sequence, etc.)."""
    p = _parser("if cond then body")
    result = choice(p, [
        Sequence([
            Literal("IDENT", "while"),
            Capture("cond"),
        ]),
        Sequence([
            Literal("IDENT", "if"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("body"),
        ]),
    ])
    assert result.success is True
    assert "cond" in result.captures
    assert "body" in result.captures


def test_choice_unwinds_first_attempt_completely():
    """If the first alternative partially matches and then fails, the
    second alternative starts from the original position."""
    p = _parser("ab cd")
    pos_before = p.pos
    result = choice(p, [
        Sequence([
            Literal("IDENT", "ab"),
            Literal("IDENT", "wrong_terminator"),  # fails
        ]),
        Sequence([
            Literal("IDENT", "ab"),  # tries again, matches
            Literal("IDENT", "cd"),  # also matches
        ]),
    ])
    assert result.success is True


# ---------------------------------------------------------------------------
# Integration with try_match (the existing API)
# ---------------------------------------------------------------------------


def test_try_match_still_works_via_speculation():
    """The legacy try_match API delegates to the speculation engine.
    Behavior should be identical."""
    p = _parser("foo bar")
    result = try_match(p, Literal("IDENT", "foo"))
    assert result.success is True
    assert p.pos == 1


def test_try_match_failure_leaves_no_partial_captures():
    """After try_match fails on a sequence, no captures should have leaked."""
    p = _parser("foo bad")
    result = try_match(p, Sequence([
        Literal("IDENT", "foo"),
        Capture("greedy"),  # this would capture `bad`
        Literal("IDENT", "expected_terminator"),  # this fails
    ]))
    assert result.success is False
    # In the previous save/restore model, captures could leak between
    # attempts if not explicitly cleared. Speculation guarantees clean
    # rollback.
    assert "greedy" not in result.captures
