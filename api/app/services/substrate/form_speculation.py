"""Parser-level speculation — backtracking without sediment.

The previous match engine in form_rules.py used ad-hoc save/restore on
parser.pos. This module replaces it with a structured speculation
context: each parse attempt is a frame on a stack; on success the frame
is committed, on failure it's unwound cleanly. State accumulated during
a failed attempt — parser position AND any partially-populated
captures — is fully restored.

The architectural through-line back to BMF (Backtracking Model Form,
2000):

> "When the parser backs out, all the attributes already computed have
> to be undone as well." — master-thesis-2000/README.md

This is what "without sediment" means: failed branches leave no trace.
The same instinct underlies the body's `tend:` / `attune:` / `compost:`
/ `release:` commit verbs at the git layer.

What's exposed:

  FailSignal     — exception raised when a parse should backtrack
  StopSignal     — exception raised when a parse commits (no more backtrack)
  SpeculationFrame — record of state at the start of a speculation
  SpeculationContext — stack of frames + push/commit/unwind operations
  speculate(parser, pattern, captures, ctx) — the structured try
  choice(parser, alternatives, ctx) — try each alternative; first wins

The speculation engine here doesn't yet *execute* recipes containing
Choice.FAIL or Choice.STOP. That's a recipe-execution engine — its
own future breath. What this module ships: the structural primitives
the future engine will use, and the parser-level speculation that
produces clean rollback today.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Signals — exceptions used to drive speculation flow
# ---------------------------------------------------------------------------


class FailSignal(Exception):
    """Raised when a parse attempt should fail and trigger backtracking.

    Caught by `speculate` and the speculation context's unwind path.
    A future recipe-execution engine catches this when evaluating a
    Choice.FAIL recipe.
    """


class StopSignal(Exception):
    """Raised when a parse attempt should commit, preventing further
    backtracking. The current frame becomes immutable.

    A future recipe-execution engine catches this when evaluating a
    Choice.STOP recipe.
    """


# ---------------------------------------------------------------------------
# Frame + Context
# ---------------------------------------------------------------------------


@dataclass
class SpeculationFrame:
    """State snapshot at the start of a speculative attempt.

    On commit: the frame is discarded, changes accumulated during the
    attempt persist in the parser/captures.

    On unwind: the frame's saved state is restored to the parser and
    captures, and the frame is discarded. The attempt leaves no trace.
    """

    saved_pos: int
    captures_before: Dict[str, Any]
    committed: bool = False  # set True if StopSignal fires inside the attempt


@dataclass
class SpeculationContext:
    """Stack of speculation frames. Supports nested attempts."""

    frames: List[SpeculationFrame] = field(default_factory=list)

    def depth(self) -> int:
        return len(self.frames)

    def push(self, parser: Any, captures: Dict[str, Any]) -> SpeculationFrame:
        frame = SpeculationFrame(
            saved_pos=parser.pos,
            captures_before=dict(captures),
        )
        self.frames.append(frame)
        return frame

    def pop_commit(self) -> SpeculationFrame:
        """Successful attempt: pop the frame, keep accumulated changes."""
        if not self.frames:
            raise RuntimeError("SpeculationContext: pop_commit on empty stack")
        return self.frames.pop()

    def pop_unwind(self, parser: Any, captures: Dict[str, Any]) -> SpeculationFrame:
        """Failed attempt: restore state from the frame, then pop.

        The captures dict is mutated in-place to its pre-attempt state.
        Parser position is rewound. Anything the attempt accumulated is
        gone — without sediment.
        """
        if not self.frames:
            raise RuntimeError("SpeculationContext: pop_unwind on empty stack")
        frame = self.frames.pop()
        if frame.committed:
            # StopSignal fired inside the attempt — frame is locked,
            # state stays as-is.
            return frame
        parser.pos = frame.saved_pos
        captures.clear()
        captures.update(frame.captures_before)
        return frame


# ---------------------------------------------------------------------------
# speculate — structured try-with-rollback
# ---------------------------------------------------------------------------


@dataclass
class SpeculationResult:
    success: bool
    captures: Dict[str, Any] = field(default_factory=dict)


def speculate(
    parser: Any,
    pattern: Any,
    *,
    ctx: Optional[SpeculationContext] = None,
) -> SpeculationResult:
    """Try to match `pattern`; return the result with clean rollback on fail.

    A speculation frame is pushed before the match. On success, the
    frame commits and accumulated captures are returned. On failure
    (matcher returns False, raises FailSignal, or any other exception),
    the frame unwinds cleanly — parser.pos restored, captures dropped.
    """
    if ctx is None:
        ctx = _ensure_context(parser)

    captures: Dict[str, Any] = {}
    frame = ctx.push(parser, captures)

    try:
        from app.services.substrate.form_rules import _do_match
        if _do_match(parser, pattern, captures):
            ctx.pop_commit()
            return SpeculationResult(True, captures)
        ctx.pop_unwind(parser, captures)
        return SpeculationResult(False, {})

    except StopSignal:
        # Speculation committed — keep state as-is, return success
        frame.committed = True
        ctx.pop_commit()
        return SpeculationResult(True, captures)

    except FailSignal:
        ctx.pop_unwind(parser, captures)
        return SpeculationResult(False, {})

    except Exception:
        # Any other exception: unwind cleanly, then re-raise.
        ctx.pop_unwind(parser, captures)
        raise


# ---------------------------------------------------------------------------
# choice — try alternatives, first match wins
# ---------------------------------------------------------------------------


def choice(
    parser: Any,
    alternatives: List[Any],
    *,
    ctx: Optional[SpeculationContext] = None,
) -> SpeculationResult:
    """Try each alternative pattern in order; return the first success.

    All alternatives that fail leave no sediment — parser state is
    fully restored between attempts. Returns SpeculationResult with
    success=False if no alternative matches.

    This is the parser-level analog of the substrate's
    Choice.CHOOSE recipe — both express speculation over alternatives.
    A future recipe-execution engine will tie them together.
    """
    if ctx is None:
        ctx = _ensure_context(parser)

    for alt in alternatives:
        result = speculate(parser, alt, ctx=ctx)
        if result.success:
            return result

    return SpeculationResult(False, {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_context(parser: Any) -> SpeculationContext:
    """Lazy-attach a SpeculationContext to the parser. Reused across
    speculate() calls within the same parse session."""
    if not hasattr(parser, "_speculation_ctx"):
        parser._speculation_ctx = SpeculationContext()
    return parser._speculation_ctx
